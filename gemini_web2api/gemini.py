"""Gemini StreamGenerate protocol implementation with httpx streaming."""
import json
import time
import uuid
import re
import urllib.request
import urllib.parse
import urllib.error
import ssl

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from .config import CONFIG

_ssl_ctx = None
_httpx_client = None
_fresh_bl_cache = {"value": "", "ts": 0}


class EmptyGeminiResponse(RuntimeError):
    """Raised when Gemini returns no parseable text fragments."""


class GeminiUpstreamError(RuntimeError):
    """Raised when Gemini returns a structured upstream error payload."""


def log(msg: str):
    if CONFIG["log_requests"]:
        import sys
        sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        sys.stderr.flush()


def _get_ssl_ctx():
    global _ssl_ctx
    if _ssl_ctx is None:
        _ssl_ctx = ssl.create_default_context()
    return _ssl_ctx


def _get_httpx_client():
    global _httpx_client
    if _httpx_client is None and HAS_HTTPX:
        proxy = CONFIG.get("proxy")
        transport = httpx.HTTPTransport(proxy=proxy) if proxy else None
        _httpx_client = httpx.Client(transport=transport, timeout=CONFIG["request_timeout_sec"], verify=True)
    return _httpx_client


def _build_headers() -> dict:
    return {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://gemini.google.com",
        "Referer": "https://gemini.google.com/app",
        "X-Same-Domain": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _build_payload(prompt: str, model_id: int, think_mode: int, extra_fields: dict = None) -> str:
    inner = [None] * 102
    inner[0] = [prompt, 0, None, None, None, None, 0]
    inner[1] = ["en"]
    inner[2] = ["", "", "", None, None, None, None, None, None, ""]
    inner[6] = [0]
    inner[7] = 1
    inner[10] = 1
    inner[11] = 0
    inner[17] = [[think_mode]]
    inner[18] = 0
    inner[27] = 1
    inner[30] = [4]
    inner[41] = [2]
    inner[53] = 0
    inner[59] = str(uuid.uuid4())
    inner[61] = []
    inner[68] = 1
    inner[79] = model_id
    if extra_fields:
        for k, v in extra_fields.items():
            inner[k] = v
    inner_json = json.dumps(inner, separators=(",", ":"))
    outer = [None, inner_json]
    return urllib.parse.urlencode({"f.req": json.dumps(outer, separators=(",", ":"))})


def _get_url() -> str:
    reqid = int(time.time()) % 1000000
    return (
        "https://gemini.google.com/_/BardChatUi/data/"
        "assistant.lamda.BardFrontendService/StreamGenerate"
        f"?bl={CONFIG['gemini_bl']}&hl=en&_reqid={reqid}&rt=c"
    )


def refresh_gemini_bl(force: bool = False) -> str:
    """Refresh Gemini Web build label from /app and update CONFIG when found."""
    now = time.time()
    if not force and _fresh_bl_cache["value"] and now - _fresh_bl_cache["ts"] < 600:
        return _fresh_bl_cache["value"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    req = urllib.request.Request("https://gemini.google.com/app", headers=headers)
    ctx = _get_ssl_ctx()
    proxy = CONFIG.get("proxy")
    try:
        if proxy:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
                urllib.request.HTTPSHandler(context=ctx)
            )
            resp = opener.open(req, timeout=30)
        else:
            resp = urllib.request.urlopen(req, context=ctx, timeout=30)
        html = resp.read().decode("utf-8", errors="replace")
        m = re.search(r'"cfb2h":"([^"]+)"', html) or re.search(r'boq_assistant-bard-web-server_[0-9A-Za-z_.-]+', html)
        fresh = (m.group(1) if m and m.lastindex else (m.group(0) if m else "")) or ""
        if fresh:
            CONFIG["gemini_bl"] = fresh
            _fresh_bl_cache.update({"value": fresh, "ts": now})
        return fresh
    except Exception as e:
        log(f"failed to refresh Gemini BL: {e}")
        return ""


def clean_text(text: str, strip_edges: bool = False) -> str:
    text = re.sub(
        r'```(?:python|javascript|text)\?code_(?:reference|stdout)&code_event_index=\d+\n.*?```\n?',
        '', text, flags=re.DOTALL
    )
    text = re.sub(r'http://googleusercontent\.com/card_content/\d+\n?', '', text)
    return text.strip() if strip_edges else text


def _extract_texts_from_line(line: str) -> list:
    """Parse a single wrb.fr line and return list of text strings found."""
    if '"wrb.fr"' not in line:
        return []
    try:
        arr = json.loads(line)
        inner_str = arr[0][2]
        if not inner_str:
            return []
        inner = json.loads(inner_str)
        if not (isinstance(inner, list) and len(inner) > 4 and inner[4]):
            return []
        texts = []
        for part in inner[4]:
            if isinstance(part, list) and len(part) > 1 and part[1] and isinstance(part[1], list):
                for t in part[1]:
                    if isinstance(t, str) and t:
                        texts.append(t)
        return texts
    except (json.JSONDecodeError, IndexError, TypeError):
        return []


def _response_diagnostics(raw: str) -> str:
    error_codes = _extract_bard_error_codes(raw)
    error_part = f" bard_error_codes={error_codes}" if error_codes else ""
    return (
        f"raw_len={len(raw)} lines={raw.count(chr(10)) + 1 if raw else 0} "
        f"wrb_count={raw.count('wrb.fr')} has_af_init={'AF_initDataCallback' in raw}"
        f"{error_part}"
    )


def _extract_bard_error_codes(raw: str) -> list:
    codes = []
    for line in raw.split("\n"):
        if "BardErrorInfo" not in line:
            continue
        try:
            arr = json.loads(line)
        except json.JSONDecodeError:
            continue
        stack = [arr]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                if item and item[0] == "type.googleapis.com/assistant.boq.bard.application.BardErrorInfo":
                    payload = item[1] if len(item) > 1 else None
                    if isinstance(payload, list) and payload and isinstance(payload[0], int):
                        codes.append(payload[0])
                stack.extend(item)
            elif isinstance(item, dict):
                stack.extend(item.values())
    return codes


def _raise_for_upstream_error(raw: str):
    codes = _extract_bard_error_codes(raw)
    if not codes:
        return
    hint = ""
    if any(code in codes for code in (1099, 1152)):
        hint = " (Gemini rejected the request; prompt is likely too large or otherwise not accepted by the Web upstream)"
    elif 1100 in codes:
        hint = " (Gemini rejected the request; attachment binding is not supported in anonymous mode.)"
    raise GeminiUpstreamError(f"Gemini BardErrorInfo codes={codes}{hint}")


def extract_response_text(raw: str) -> str:
    """Parse full response to get final text."""
    _raise_for_upstream_error(raw)
    last_text = ""
    text_count = 0
    for line in raw.split("\n"):
        for t in _extract_texts_from_line(line):
            text_count += 1
            if len(t) > len(last_text):
                last_text = t
    cleaned = clean_text(last_text)
    log(f"Gemini parse: raw_len={len(raw)} text_fragments={text_count} text_len={len(cleaned)}")
    if text_count == 0:
        raise EmptyGeminiResponse(f"no parseable text fragments ({_response_diagnostics(raw)})")
    return cleaned


def generate(
    prompt: str,
    model_id: int,
    think_mode: int,
    extra_fields: dict = None,
) -> str:
    """Non-streaming generation with retry."""
    body = _build_payload(prompt, model_id, think_mode, extra_fields).encode()
    url = _get_url()
    headers = _build_headers()
    ctx = _get_ssl_ctx()
    proxy = CONFIG.get("proxy")

    last_err = None
    for attempt in range(CONFIG["retry_attempts"]):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            if proxy:
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
                    urllib.request.HTTPSHandler(context=ctx)
                )
                resp = opener.open(req, timeout=CONFIG["request_timeout_sec"])
            else:
                resp = urllib.request.urlopen(req, context=ctx, timeout=CONFIG["request_timeout_sec"])
            raw = resp.read().decode("utf-8", errors="replace")
            status = getattr(resp, "status", None) or getattr(resp, "code", None)
            log(f"Gemini HTTP: status={status} raw_len={len(raw)}")
            return extract_response_text(raw)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            last_err = RuntimeError(f"Gemini HTTP {e.code}: {body}")
            if attempt < CONFIG["retry_attempts"] - 1:
                log(f"Retry {attempt+1}/{CONFIG['retry_attempts']}: {last_err}")
                time.sleep(CONFIG["retry_delay_sec"])
        except Exception as e:
            last_err = e
            if attempt < CONFIG["retry_attempts"] - 1:
                log(f"Retry {attempt+1}/{CONFIG['retry_attempts']}: {e}")
                time.sleep(CONFIG["retry_delay_sec"])
    raise last_err


def generate_stream(
    prompt: str,
    model_id: int,
    think_mode: int,
    extra_fields: dict = None,
):
    """Streaming generation via httpx with retry on connection failure."""
    if not HAS_HTTPX:
        text = generate(prompt, model_id, think_mode, extra_fields)
        if text:
            yield text
        return

    body = _build_payload(prompt, model_id, think_mode, extra_fields)
    url = _get_url()
    headers = _build_headers()
    client = _get_httpx_client()

    last_err = None
    for attempt in range(CONFIG["retry_attempts"]):
        try:
            prev_text = ""
            chunks = 0
            text_fragments = 0
            raw_parts = []
            with client.stream("POST", url, content=body, headers=headers) as resp:
                log(f"Gemini stream HTTP: status={resp.status_code}")
                resp.raise_for_status()
                buf = ""
                for chunk in resp.iter_text():
                    chunks += 1
                    raw_parts.append(chunk)
                    buf += chunk
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        for t in _extract_texts_from_line(line):
                            text_fragments += 1
                            cleaned_text = clean_text(t)
                            if len(cleaned_text) > len(prev_text):
                                delta = cleaned_text[len(prev_text):]
                                if delta:
                                    yield delta
                                prev_text = cleaned_text
                if buf:
                    for t in _extract_texts_from_line(buf):
                        text_fragments += 1
                        cleaned_text = clean_text(t)
                        if len(cleaned_text) > len(prev_text):
                            delta = cleaned_text[len(prev_text):]
                            if delta:
                                yield delta
                            prev_text = cleaned_text
            log(
                f"Gemini stream parse: chunks={chunks} "
                f"text_fragments={text_fragments} text_len={len(prev_text)}"
            )
            if text_fragments == 0:
                raw = "".join(raw_parts)
                _raise_for_upstream_error(raw)
                raise EmptyGeminiResponse(f"no parseable text fragments ({_response_diagnostics(raw)})")
            return
        except Exception as e:
            last_err = e
            if attempt < CONFIG["retry_attempts"] - 1:
                log(f"Stream retry {attempt+1}/{CONFIG['retry_attempts']}: {e}")
                time.sleep(CONFIG["retry_delay_sec"])
    raise last_err
