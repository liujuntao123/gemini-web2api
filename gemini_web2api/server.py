"""HTTP server: OpenAI-compatible API endpoints."""
import json
import time
import uuid
import re
import urllib.parse
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

from .config import CONFIG
from .analytics import query_logs, usage_stats, record_call
from .dashboard import dashboard_html
from .models import MODELS, resolve_model
from .gemini import generate, generate_stream, log
from .tools import (
    _build_tool_choice_instruction,
    build_google_history_transcript,
    build_openai_history_transcript,
    build_tools_context_transcript,
    google_tool_defs,
    messages_to_prompt,
    latest_google_user_input_text,
    latest_openai_user_input_text,
    openai_tool_defs,
    parse_tool_calls,
    google_contents_to_prompt,
    parse_google_function_calls,
    google_tool_names,
)
from .multimodal import has_cookie, prompt_byte_length, resolve_upload_files, upload_text_file
from . import __version__


def _usage(prompt: str, text: str) -> dict:
    p = len(prompt) // 4
    c = len(text or "") // 4
    return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c}


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _json_object(body: bytes):
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _max_request_body_bytes() -> Optional[int]:
    """Return configured request body limit in bytes.

    Positive integers enable a limit. None, 0, or a negative value disable the
    local server-side cap, leaving upstream/model limits to decide whether a
    prompt is acceptable.
    """
    default_limit = 50 * 1024 * 1024
    raw_value = CONFIG.get("max_request_body_bytes", default_limit)
    if raw_value is None:
        return None
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default_limit
    return value if value > 0 else None


def _max_upstream_prompt_bytes() -> Optional[int]:
    """Return optional guardrail for the Gemini Web form payload size."""
    raw_value = CONFIG.get("max_upstream_prompt_bytes")
    if raw_value is None:
        return None
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _upstream_prompt_size_error(
    prompt: str,
    model_id: int,
    think_mode: int,
    file_refs: list = None,
    extra_fields: dict = None,
) -> Optional[dict]:
    max_prompt = _max_upstream_prompt_bytes()
    if max_prompt is None:
        return None

    from .gemini import _build_payload

    upstream_bytes = len(_build_payload(prompt, model_id, think_mode, file_refs, extra_fields).encode())
    if upstream_bytes <= max_prompt:
        return None
    return {
        "message": "prompt too large for Gemini Web upstream",
        "upstream_prompt_bytes": upstream_bytes,
        "limit": max_prompt,
    }


def _use_cookie_for_upstream(file_refs: list = None) -> bool:
    """Use Gemini cookie mode only when the upstream request binds uploaded files."""
    return bool(file_refs)


def _upstream_mode(use_cookie: bool) -> str:
    return "cookie" if use_cookie else "anonymous"


def _configured_api_keys() -> set:
    keys = CONFIG.get("api_keys") or []
    if isinstance(keys, str):
        keys = [keys]
    if not isinstance(keys, (list, tuple, set)):
        return set()
    return {str(key) for key in keys if key}


def _attachment_prompt() -> str:
    configured = CONFIG.get("current_input_file_prompt")
    if configured:
        return configured
    history_name = CONFIG.get("current_input_file_name") or "message.txt"
    return (
        f"Context is attached in `{history_name}`. Acknowledge it briefly, "
        "then treat it as the primary user input for this turn and answer based on it."
    )


def _single_context_file_prompt() -> str:
    history_name = CONFIG.get("current_input_file_name") or "message.txt"
    return (
        f"Context is attached in `{history_name}`. Treat the file as the complete user input "
        "for this turn. Read the instructions and any question inside it, then answer directly."
    )


def _context_file_threshold() -> int:
    try:
        return max(0, int(CONFIG.get("current_input_file_min_bytes") or 0))
    except (TypeError, ValueError):
        return 95000


def _should_consider_context_files(prompt: str) -> bool:
    return (
        bool(CONFIG.get("current_input_file_enabled"))
        and has_cookie()
        and _context_file_threshold() > 0
        and prompt_byte_length(prompt) > _context_file_threshold()
    )


def _latest_input_inline_limit() -> int:
    threshold = _context_file_threshold() or 95000
    return max(4000, min(16000, threshold // 6))


def _latest_input_prompt_for_context_file(latest_input: str) -> str:
    latest = str(latest_input or "").strip()
    if not latest:
        return ""
    if prompt_byte_length(latest) <= _latest_input_inline_limit():
        return "Latest user request:\n" + latest
    history_name = CONFIG.get("current_input_file_name") or "message.txt"
    return (
        f"The latest user request is at the end of `{history_name}`; do not duplicate it inline.\n"
        "Read it from the txt file and answer directly."
    )


def _context_upload_failure(kind: str, prompt: str, cause: Exception) -> RuntimeError:
    err = RuntimeError(
        f"failed to upload {kind or 'context'} text file for large prompt; "
        "refusing to fall back to oversized inline context"
    )
    err.code = "large_context_file_upload_failed"
    err.prompt_bytes = prompt_byte_length(prompt)
    err.__cause__ = cause
    return err


def _prepare_context_files(
    history_text: str,
    tool_defs: list,
    choice_instruction: str,
    latest_input: str,
    prompt: str,
) -> Optional[dict]:
    if not _should_consider_context_files(prompt or history_text):
        return None
    if not str(history_text or "").strip() or not str(latest_input or "").strip():
        return None

    refs = []
    history_name = CONFIG.get("current_input_file_name") or "message.txt"
    tools_name = CONFIG.get("current_tools_file_name") or "tools.txt"
    tools_text = build_tools_context_transcript(tool_defs, choice_instruction, tools_name)
    tools_attached = False

    try:
        refs.append(upload_text_file(history_text, history_name))
    except Exception as e:
        log(f"history context file upload failed for large prompt: {e}")
        raise _context_upload_failure("history context", prompt, e)

    if tools_text.strip():
        try:
            refs.append(upload_text_file(tools_text, tools_name))
            tools_attached = True
        except Exception as e:
            log(f"tools context file upload failed for large prompt: {e}")
            raise _context_upload_failure("tools context", prompt, e)

    live_prompt_parts = [
        choice_instruction,
        _attachment_prompt(),
        _latest_input_prompt_for_context_file(latest_input),
        tools_text if tools_text.strip() and not tools_attached else "",
    ]
    live_prompt = "\n\n".join(p.strip() for p in live_prompt_parts if str(p or "").strip())
    prompt_token_text = "\n".join(p for p in [history_text, tools_text, live_prompt] if p)
    log(
        "context files enabled: "
        f"refs={len(refs)} history_bytes={prompt_byte_length(history_text)} "
        f"tools_bytes={prompt_byte_length(tools_text)} latest_bytes={prompt_byte_length(latest_input)} "
        f"live_prompt_bytes={prompt_byte_length(live_prompt)}"
    )
    return {"prompt": live_prompt, "file_refs": refs, "prompt_token_text": prompt_token_text}


def _prepare_file_refs(
    prompt: str,
    attachments: list = None,
    history_text: str = None,
    tool_defs: list = None,
    choice_instruction: str = "",
    latest_input: str = "",
) -> tuple:
    """Upload request attachments and large prompt text, returning (prompt, file_refs)."""
    file_refs = []
    attachments = attachments or []
    if attachments:
        uploaded, note = resolve_upload_files(attachments)
        if uploaded:
            file_refs.extend(uploaded)
        if note:
            prompt = (prompt + "\n\n" if prompt else "") + note

    context_files = _prepare_context_files(
        history_text,
        tool_defs or [],
        choice_instruction,
        latest_input,
        prompt,
    )
    if context_files:
        file_refs.extend(context_files["file_refs"])
        prompt = context_files["prompt"]

    if file_refs and not prompt.strip():
        prompt = _attachment_prompt()

    return prompt, file_refs or None


def _prepare_openai_file_refs(prompt: str, attachments: list, messages: list, tools: list, tool_choice) -> tuple:
    tool_defs = openai_tool_defs(tools)
    choice_instruction = _build_tool_choice_instruction(tool_choice, tool_defs) if tool_defs and tool_choice != "none" else ""
    history_text = build_openai_history_transcript(messages, CONFIG.get("current_input_file_name") or "message.txt")
    return _prepare_file_refs(
        prompt,
        attachments,
        history_text=history_text,
        tool_defs=tool_defs,
        choice_instruction=choice_instruction,
        latest_input=latest_openai_user_input_text(messages),
    )


def _prepare_google_file_refs(prompt: str, attachments: list, req: dict) -> tuple:
    tool_defs = google_tool_defs(req)
    choice_instruction = ""
    tool_config = req.get("toolConfig", {})
    fc_config = tool_config.get("functionCallingConfig", {})
    mode = fc_config.get("mode", "AUTO")
    allowed = fc_config.get("allowedFunctionNames", [])
    if mode == "NONE":
        choice_instruction = "\n\nIMPORTANT: Do NOT call any tools. Respond with text only."
    elif mode == "ANY":
        if allowed:
            names = ", ".join(f'"{n}"' for n in allowed)
            choice_instruction = f"\n\nIMPORTANT: You MUST call one of these tools: {names}. Do not respond with text only."
        else:
            choice_instruction = "\n\nIMPORTANT: You MUST call at least one tool. Do not respond with text only."
    history_text = build_google_history_transcript(req, CONFIG.get("current_input_file_name") or "message.txt")
    return _prepare_file_refs(
        prompt,
        attachments,
        history_text=history_text,
        tool_defs=tool_defs,
        choice_instruction=choice_instruction,
        latest_input=latest_google_user_input_text(req),
    )


class GeminiHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log(fmt % args)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self._last_status = status
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html: str, status=200):
        body = html.encode("utf-8")
        self._last_status = status
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _start_sse(self):
        self._last_status = 200
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def _write_sse_error(self, message: str):
        self._update_call_log(success=False, status_code=502, error_type="upstream_error", error_message=message)
        payload = {"error": {"message": message}}
        self.wfile.write(f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _begin_call_log(self, req_id: str, path: str, request_bytes: int = None):
        self._call_log_start = time.perf_counter()
        self._call_log_recorded = False
        self._last_status = None
        self._call_log = {
            "request_id": req_id,
            "method": getattr(self, "command", "POST"),
            "endpoint": path,
            "request_bytes": request_bytes,
            "client_host": self.client_address[0] if self.client_address else None,
            "user_agent": self.headers.get("User-Agent"),
        }

    def _update_call_log(self, **fields):
        if getattr(self, "_call_log", None) is not None:
            self._call_log.update({k: v for k, v in fields.items() if v is not None})

    def _finish_call_log(self, status_code: int = None, success: bool = None, error: Exception = None):
        if getattr(self, "_call_log_recorded", True) or getattr(self, "_call_log", None) is None:
            return
        self._call_log_recorded = True
        status = status_code or self._call_log.get("status_code") or getattr(self, "_last_status", None)
        if status is None:
            status = 499 if isinstance(error, (BrokenPipeError, ConnectionResetError)) else 500
        self._call_log["status_code"] = status
        if success is None:
            success = self._call_log.get("success")
        if success is None:
            success = 200 <= int(status) < 400 and self._call_log.get("error_type") is None
        if error is not None:
            self._call_log.setdefault("error_type", error.__class__.__name__)
            self._call_log.setdefault("error_message", str(error))
        self._call_log["success"] = success
        self._call_log["response_ms"] = int((time.perf_counter() - self._call_log_start) * 1000)
        record_call(self._call_log)

    def _parse_body(self, body: bytes) -> dict:
        return _json_object(body)

    def _authorized(self):
        keys = _configured_api_keys()
        if not keys:
            return True
        auth = self.headers.get("Authorization", "")
        key = auth[7:] if auth.startswith("Bearer ") else self.headers.get("x-api-key", "")
        return key in keys

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        try:
            parsed = urllib.parse.urlsplit(self.path)
            path = parsed.path
            if path.startswith("/v1/") and not self._authorized():
                self.send_json({"error": {"message": "invalid api key"}}, 401)
                return
            if path == "/v1/models":
                self.send_json({"object": "list", "data": [
                    {"id": n, "object": "model", "created": 1700000000,
                     "owned_by": "google", "description": c["desc"]}
                    for n, c in MODELS.items()
                ]})
            elif path.startswith("/v1beta/models"):
                self.send_json({"models": [
                    {"name": f"models/{n}", "displayName": n, "description": c["desc"],
                     "supportedGenerationMethods": ["generateContent", "streamGenerateContent"]}
                    for n, c in MODELS.items()
                ]})
            elif path == "/v1/usage/logs":
                params = {k: v[-1] for k, v in urllib.parse.parse_qs(parsed.query).items()}
                self.send_json(query_logs(params))
            elif path == "/v1/usage/stats":
                params = {k: v[-1] for k, v in urllib.parse.parse_qs(parsed.query).items()}
                self.send_json(usage_stats(params))
            elif path in ("/dashboard", "/dashboard/"):
                self.send_html(dashboard_html())
            elif path == "/":
                self.send_json({
                    "status": "ok",
                    "version": __version__,
                    "models": list(MODELS.keys()),
                    "dashboard": "/dashboard",
                })
            else:
                self.send_json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        req_id = _short_id()
        path = ""
        try:
            path = urllib.parse.urlsplit(self.path).path
            self._begin_call_log(req_id, path)
            if path.startswith("/v1/") and not self._authorized():
                self._update_call_log(api_type="auth", error_type="auth_error", error_message="invalid api key")
                self.send_json({"error": {"message": "invalid api key"}}, 401)
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
            except ValueError:
                self._update_call_log(api_type="http", error_type="bad_request", error_message="invalid Content-Length")
                self.send_json({"error": {"message": "invalid Content-Length"}}, 400)
                return
            if length < 0:
                self._update_call_log(api_type="http", error_type="bad_request", error_message="invalid Content-Length")
                self.send_json({"error": {"message": "invalid Content-Length"}}, 400)
                return
            self._update_call_log(request_bytes=length)
            max_body = _max_request_body_bytes()
            if max_body is not None and length > max_body:
                log(f"request {req_id}: payload too large bytes={length} limit={max_body}")
                self._update_call_log(api_type="http", error_type="payload_too_large", error_message="request body too large")
                self.send_json({"error": {"message": "request body too large"}}, 413)
                return
            body = self.rfile.read(length) if length else b""
            log(f"request {req_id}: POST {path} bytes={length}")
            if path == "/v1/chat/completions":
                self._handle_chat(body, req_id)
            elif path == "/v1/responses":
                self._handle_responses(body, req_id)
            elif ":generateContent" in path:
                self._handle_google_generate(body, stream=False, req_id=req_id)
            elif ":streamGenerateContent" in path:
                self._handle_google_generate(body, stream=True, req_id=req_id)
            else:
                self._update_call_log(api_type="http", error_type="not_found", error_message="not found")
                self.send_json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError) as e:
            self._finish_call_log(status_code=499, success=False, error=e)
        except Exception as e:
            log(f"request {req_id}: POST error: {e}")
            self._update_call_log(api_type="http", error_type=e.__class__.__name__, error_message=str(e))
            try:
                self.send_json({"error": {"message": str(e)}}, 500)
            except (BrokenPipeError, ConnectionResetError):
                pass
        finally:
            self._finish_call_log()

    # ─── /v1/chat/completions ─────────────────────────────────────────────────

    def _handle_chat(self, body: bytes, req_id: str):
        req = self._parse_body(body)
        if req is None:
            self._update_call_log(api_type="chat", error_type="bad_request", error_message="invalid JSON")
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        model_name, model_id, think_mode, err, extra_fields = resolve_model(
            req.get("model", CONFIG["default_model"]))
        self._update_call_log(api_type="chat", model=model_name, stream=bool(req.get("stream", False)))
        if err:
            self._update_call_log(error_type="bad_request", error_message=err)
            self.send_json({"error": {"message": err}}, 400)
            return

        tools = req.get("tools")
        tool_choice = req.get("tool_choice", "auto")
        prompt, attachments = messages_to_prompt(req.get("messages", []), tools, tool_choice)
        if not prompt.strip() and not attachments:
            self._update_call_log(
                prompt_chars=len(prompt),
                image_count=len(attachments),
                tool_count=len(tools or []),
                error_type="bad_request",
                error_message="empty prompt",
            )
            self.send_json({"error": {"message": "empty prompt"}}, 400)
            return

        stream = req.get("stream", False)
        self._update_call_log(
            stream=bool(stream),
            prompt_chars=len(prompt),
            prompt_tokens=len(prompt) // 4,
            image_count=len(attachments),
            tool_count=len(tools or []),
        )
        cid = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        log(
            f"request {req_id}: chat model={model_name} stream={stream} "
            f"tools={bool(tools)} prompt_len={len(prompt)} attachments={len(attachments)}"
        )
        try:
            prompt, file_refs = _prepare_openai_file_refs(prompt, attachments, req.get("messages", []), tools, tool_choice)
        except Exception as e:
            self._update_call_log(error_type=e.__class__.__name__, error_message=f"upload error: {e}")
            self.send_json({"error": {"message": f"upload error: {e}"}}, 502)
            return
        use_cookie = _use_cookie_for_upstream(file_refs)
        upstream_mode = _upstream_mode(use_cookie)
        self._update_call_log(upstream_mode=upstream_mode, upstream_cookie=use_cookie, file_ref_count=len(file_refs or []))
        log(f"request {req_id}: chat upstream_mode={upstream_mode} file_refs={len(file_refs or [])}")
        size_error = _upstream_prompt_size_error(prompt, model_id, think_mode, file_refs, extra_fields)
        if size_error:
            log(
                f"request {req_id}: upstream prompt too large "
                f"bytes={size_error['upstream_prompt_bytes']} limit={size_error['limit']}"
            )
            self._update_call_log(error_type="prompt_too_large", error_message=size_error["message"])
            self.send_json({"error": size_error}, 413)
            return

        if stream and (not tools or tool_choice == "none"):
            try:
                chunks = 0
                total_chars = 0
                stream_iter = generate_stream(prompt, model_id, think_mode, file_refs, extra_fields, use_cookie=use_cookie)
                try:
                    first_delta = next(stream_iter)
                except StopIteration:
                    log(f"request {req_id}: chat stream empty before headers")
                    self._update_call_log(error_type="empty_upstream_response", error_message="empty upstream response")
                    self.send_json({"error": {"message": "empty upstream response"}}, 502)
                    return
                except Exception as e:
                    log(f"request {req_id}: chat stream upstream error before headers: {e}")
                    self._update_call_log(error_type=e.__class__.__name__, error_message=f"upstream error: {e}")
                    self.send_json({"error": {"message": f"upstream error: {e}"}}, 502)
                    return

                self._start_sse()
                for delta in [first_delta]:
                    chunk = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                             "model": model_name, "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}]}
                    self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
                    self.wfile.flush()
                    chunks += 1
                    total_chars += len(delta)
                for delta in stream_iter:
                    chunk = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                             "model": model_name, "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}]}
                    self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
                    self.wfile.flush()
                    chunks += 1
                    total_chars += len(delta)
                end = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                       "model": model_name, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
                self.wfile.write(f"data: {json.dumps(end)}\n\n".encode())
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                self._update_call_log(
                    response_chars=total_chars,
                    completion_tokens=total_chars // 4,
                    total_tokens=(len(prompt) + total_chars) // 4,
                )
                log(f"request {req_id}: chat stream done chunks={chunks} chars={total_chars}")
            except (BrokenPipeError, ConnectionResetError) as e:
                self._finish_call_log(status_code=499, success=False, error=e)
            except Exception as e:
                log(f"request {req_id}: chat stream upstream error after headers: {e}")
                self._write_sse_error(f"upstream error: {e}")
            return

        try:
            text = generate(prompt, model_id, think_mode, file_refs, extra_fields, use_cookie=use_cookie)
        except Exception as e:
            self._update_call_log(error_type=e.__class__.__name__, error_message=f"upstream error: {e}")
            self.send_json({"error": {"message": f"upstream error: {e}"}}, 502)
            return
        log(f"request {req_id}: chat upstream text_len={len(text or '')}")

        tool_calls = None
        if tools and text and tool_choice != "none":
            text, tool_calls = parse_tool_calls(text)
            log(
                f"request {req_id}: chat parsed tool_calls={len(tool_calls or [])} "
                f"text_len={len(text or '')}"
            )
        msg = {"role": "assistant", "content": text or None}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        finish = "tool_calls" if tool_calls else "stop"
        self._update_call_log(
            response_chars=len(text or ""),
            completion_tokens=len(text or "") // 4,
            total_tokens=(len(prompt) + len(text or "")) // 4,
        )

        if stream:
            self._start_sse()
            chunk = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                     "model": model_name, "choices": [{"index": 0, "delta": msg, "finish_reason": finish}]}
            self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        else:
            self.send_json({
                "id": cid, "object": "chat.completion", "created": int(time.time()),
                "model": model_name,
                "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
                "usage": {"prompt_tokens": len(prompt)//4, "completion_tokens": len(text or "")//4,
                          "total_tokens": (len(prompt)+len(text or ""))//4},
            })

    # ─── /v1/responses (Codex CLI) ───────────────────────────────────────────

    def _handle_responses(self, body: bytes, req_id: str):
        req = self._parse_body(body)
        if req is None:
            self._update_call_log(api_type="responses", error_type="bad_request", error_message="invalid JSON")
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        model_name, model_id, think_mode, err, extra_fields = resolve_model(
            req.get("model", CONFIG["default_model"]))
        self._update_call_log(api_type="responses", model=model_name, stream=bool(req.get("stream")))
        if err:
            self._update_call_log(error_type="bad_request", error_message=err)
            self.send_json({"error": {"message": err}}, 400)
            return

        input_items = req.get("input", [])
        tools = req.get("tools")
        messages = []
        if req.get("instructions"):
            messages.append({"role": "system", "content": req["instructions"]})
        if isinstance(input_items, str):
            messages.append({"role": "user", "content": input_items})
        elif isinstance(input_items, list):
            fallback_content = []

            def flush_fallback_content():
                if fallback_content:
                    messages.append({"role": "user", "content": list(fallback_content)})
                    fallback_content.clear()

            for item in input_items:
                if isinstance(item, str):
                    fallback_content.append({"type": "input_text", "text": item})
                elif isinstance(item, dict):
                    if item.get("type") == "function_call_output":
                        flush_fallback_content()
                        messages.append({"role": "tool", "tool_call_id": item.get("call_id", ""),
                                         "name": item.get("name", ""), "content": item.get("output", "")})
                    elif item.get("role") == "assistant" or (item.get("type") == "message" and item.get("role") == "assistant"):
                        flush_fallback_content()
                        cp = item.get("content", [])
                        text_acc, tc_list = "", []
                        if isinstance(cp, list):
                            for c in cp:
                                if isinstance(c, dict):
                                    if c.get("type") == "output_text": text_acc += c.get("text", "")
                                    elif c.get("type") == "function_call": tc_list.append(c)
                        elif isinstance(cp, str):
                            text_acc = cp
                        m = {"role": "assistant", "content": text_acc or None}
                        if tc_list:
                            m["tool_calls"] = [{"id": tc.get("call_id", f"call_{i}"), "type": "function",
                                                "function": {"name": tc.get("name",""), "arguments": tc.get("arguments","{}")}}
                                               for i, tc in enumerate(tc_list)]
                        messages.append(m)
                    elif item.get("type") in ("input_text", "text", "input_file", "file", "input_image", "image_url", "image"):
                        fallback_content.append(item)
                    else:
                        flush_fallback_content()
                        role = item.get("role", "user")
                        content = item.get("content", "")
                        messages.append({"role": role, "content": content})
            flush_fallback_content()

        if tools:
            tools = [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t.get("parameters", {})}}
                     if t.get("type") == "function" and "function" not in t else t for t in tools]

        tool_choice = req.get("tool_choice", "auto")
        prompt, attachments = messages_to_prompt(messages, tools, tool_choice)
        if not prompt.strip() and not attachments:
            self._update_call_log(
                prompt_chars=len(prompt),
                image_count=len(attachments),
                tool_count=len(tools or []),
                error_type="bad_request",
                error_message="empty input",
            )
            self.send_json({"error": {"message": "empty input"}}, 400)
            return
        self._update_call_log(
            prompt_chars=len(prompt),
            prompt_tokens=len(prompt) // 4,
            image_count=len(attachments),
            tool_count=len(tools or []),
        )
        log(
            f"request {req_id}: responses model={model_name} stream={bool(req.get('stream'))} "
            f"tools={bool(tools)} prompt_len={len(prompt)} attachments={len(attachments)}"
        )
        try:
            prompt, file_refs = _prepare_openai_file_refs(prompt, attachments, messages, tools, tool_choice)
        except Exception as e:
            self._update_call_log(error_type=e.__class__.__name__, error_message=f"upload error: {e}")
            self.send_json({"error": {"message": f"upload error: {e}"}}, 502)
            return
        use_cookie = _use_cookie_for_upstream(file_refs)
        upstream_mode = _upstream_mode(use_cookie)
        self._update_call_log(upstream_mode=upstream_mode, upstream_cookie=use_cookie, file_ref_count=len(file_refs or []))
        log(f"request {req_id}: responses upstream_mode={upstream_mode} file_refs={len(file_refs or [])}")
        size_error = _upstream_prompt_size_error(prompt, model_id, think_mode, file_refs, extra_fields)
        if size_error:
            log(
                f"request {req_id}: upstream prompt too large "
                f"bytes={size_error['upstream_prompt_bytes']} limit={size_error['limit']}"
            )
            self._update_call_log(error_type="prompt_too_large", error_message=size_error["message"])
            self.send_json({"error": size_error}, 413)
            return

        try:
            text = generate(prompt, model_id, think_mode, file_refs, extra_fields, use_cookie=use_cookie)
        except Exception as e:
            self._update_call_log(error_type=e.__class__.__name__, error_message=f"upstream error: {e}")
            self.send_json({"error": {"message": f"upstream error: {e}"}}, 502)
            return
        log(f"request {req_id}: responses upstream text_len={len(text or '')}")

        tool_calls = None
        if tools and text and tool_choice != "none":
            text, tool_calls = parse_tool_calls(text)
            log(
                f"request {req_id}: responses parsed tool_calls={len(tool_calls or [])} "
                f"text_len={len(text or '')}"
            )

        rid = f"resp_{uuid.uuid4().hex[:16]}"
        mid = f"msg_{uuid.uuid4().hex[:12]}"
        output = []
        if tool_calls:
            for tc in tool_calls:
                output.append({"type": "function_call", "id": tc["id"], "call_id": tc["id"],
                               "name": tc["function"]["name"], "arguments": tc["function"]["arguments"], "status": "completed"})
        if text or not tool_calls:
            output.append({"type": "message", "id": mid, "role": "assistant", "status": "completed",
                           "content": [{"type": "output_text", "text": text or "", "annotations": []}]})
        self._update_call_log(
            response_chars=len(text or ""),
            completion_tokens=len(text or "") // 4,
            total_tokens=(len(prompt) + len(text or "")) // 4,
        )

        if req.get("stream"):
            self._last_status = 200
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            ev = {"type": "response.created", "response": {"id": rid, "object": "response", "status": "in_progress", "model": model_name, "output": []}}
            self.wfile.write(f"event: response.created\ndata: {json.dumps(ev)}\n\n".encode())
            for item in output:
                if item["type"] == "function_call":
                    ev = {"type": "response.function_call_arguments.done", "item_id": item["id"], "call_id": item["call_id"], "name": item["name"], "arguments": item["arguments"]}
                    self.wfile.write(f"event: response.function_call_arguments.done\ndata: {json.dumps(ev)}\n\n".encode())
                elif item["type"] == "message":
                    for ci, cp in enumerate(item["content"]):
                        ev = {"type": "response.output_text.done", "item_id": item["id"], "content_index": ci, "text": cp["text"]}
                        self.wfile.write(f"event: response.output_text.done\ndata: {json.dumps(ev)}\n\n".encode())
            resp_obj = {"id": rid, "object": "response", "status": "completed", "model": model_name, "output": output,
                        "usage": {"input_tokens": len(prompt)//4, "output_tokens": len(text or "")//4, "total_tokens": (len(prompt)+len(text or ""))//4}}
            self.wfile.write(f"event: response.completed\ndata: {json.dumps({'type': 'response.completed', 'response': resp_obj})}\n\n".encode())
            self.wfile.flush()
        else:
            self.send_json({"id": rid, "object": "response", "created_at": int(time.time()), "status": "completed",
                            "model": model_name, "output": output,
                            "usage": {"input_tokens": len(prompt)//4, "output_tokens": len(text or "")//4, "total_tokens": (len(prompt)+len(text or ""))//4}})

    # ─── /v1beta/models (Google Gemini CLI) ──────────────────────────────────

    def _handle_google_generate(self, body: bytes, stream: bool, req_id: str):
        req = self._parse_body(body)
        if req is None:
            self._update_call_log(api_type="google", stream=stream, error_type="bad_request", error_message="invalid JSON")
            self.send_json({"error": {"message": "invalid JSON"}}, 400)
            return
        path = urllib.parse.urlsplit(self.path).path
        m = re.match(r'/v1beta/models/([^:?]+)', path)
        model_name = m.group(1) if m else CONFIG["default_model"]
        model_name, model_id, think_mode, err, extra_fields = resolve_model(model_name)
        self._update_call_log(api_type="google", model=model_name, stream=stream)
        if err:
            self._update_call_log(error_type="bad_request", error_message=err)
            self.send_json({"error": {"message": err}}, 400)
            return

        tool_config = req.get("toolConfig", {})
        fc_mode = tool_config.get("functionCallingConfig", {}).get("mode", "AUTO")
        has_tools = bool(req.get("tools")) and fc_mode != "NONE"
        prompt, attachments = google_contents_to_prompt(req)
        if not prompt.strip() and not attachments:
            self._update_call_log(
                prompt_chars=len(prompt),
                image_count=len(attachments),
                tool_count=len(req.get("tools") or []),
                error_type="bad_request",
                error_message="empty content",
            )
            self.send_json({"error": {"message": "empty content"}}, 400)
            return

        allowed_tool_names = google_tool_names(req)
        self._update_call_log(
            prompt_chars=len(prompt),
            prompt_tokens=len(prompt) // 4,
            image_count=len(attachments),
            tool_count=len(req.get("tools") or []),
        )
        log(
            f"request {req_id}: google model={model_name} stream={stream} tools={has_tools} "
            f"tool_names={len(allowed_tool_names)} prompt_len={len(prompt)} attachments={len(attachments)}"
        )
        try:
            prompt, file_refs = _prepare_google_file_refs(prompt, attachments, req)
        except Exception as e:
            self._update_call_log(error_type=e.__class__.__name__, error_message=f"upload error: {e}")
            self.send_json({"error": {"message": f"upload error: {e}"}}, 502)
            return
        use_cookie = _use_cookie_for_upstream(file_refs)
        upstream_mode = _upstream_mode(use_cookie)
        self._update_call_log(upstream_mode=upstream_mode, upstream_cookie=use_cookie, file_ref_count=len(file_refs or []))
        log(f"request {req_id}: google upstream_mode={upstream_mode} file_refs={len(file_refs or [])}")
        size_error = _upstream_prompt_size_error(prompt, model_id, think_mode, file_refs, extra_fields)
        if size_error:
            log(
                f"request {req_id}: upstream prompt too large "
                f"bytes={size_error['upstream_prompt_bytes']} limit={size_error['limit']}"
            )
            self._update_call_log(error_type="prompt_too_large", error_message=size_error["message"])
            self.send_json({"error": size_error}, 413)
            return

        if stream and not has_tools:
            try:
                full_text = ""
                chunks = 0
                stream_iter = generate_stream(prompt, model_id, think_mode, file_refs, extra_fields, use_cookie=use_cookie)
                try:
                    first_delta = next(stream_iter)
                except StopIteration:
                    log(f"request {req_id}: google stream empty before headers")
                    self._update_call_log(error_type="empty_upstream_response", error_message="empty upstream response")
                    self.send_json({"error": {"message": "empty upstream response"}}, 502)
                    return
                except Exception as e:
                    log(f"request {req_id}: google stream upstream error before headers: {e}")
                    self._update_call_log(error_type=e.__class__.__name__, error_message=f"upstream error: {e}")
                    self.send_json({"error": {"message": f"upstream error: {e}"}}, 502)
                    return

                self._start_sse()
                for delta in [first_delta]:
                    if not delta:
                        continue
                    full_text += delta
                    chunks += 1
                    chunk_obj = {
                        "candidates": [{"content": {"parts": [{"text": delta}], "role": "model"}, "index": 0}],
                        "modelVersion": model_name,
                    }
                    self.wfile.write(f"data: {json.dumps(chunk_obj, ensure_ascii=False)}\n\n".encode())
                    self.wfile.flush()
                for delta in stream_iter:
                    if not delta:
                        continue
                    full_text += delta
                    chunks += 1
                    chunk_obj = {
                        "candidates": [{"content": {"parts": [{"text": delta}], "role": "model"}, "index": 0}],
                        "modelVersion": model_name,
                    }
                    self.wfile.write(f"data: {json.dumps(chunk_obj, ensure_ascii=False)}\n\n".encode())
                    self.wfile.flush()
                final_chunk = {
                    "candidates": [{"finishReason": "STOP", "index": 0}],
                    "usageMetadata": {
                        "promptTokenCount": len(prompt) // 4,
                        "candidatesTokenCount": len(full_text) // 4,
                        "totalTokenCount": (len(prompt) + len(full_text)) // 4,
                    },
                    "modelVersion": model_name,
                }
                self.wfile.write(f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
                self._update_call_log(
                    response_chars=len(full_text),
                    completion_tokens=len(full_text) // 4,
                    total_tokens=(len(prompt) + len(full_text)) // 4,
                )
                log(f"request {req_id}: google stream done chunks={chunks} chars={len(full_text)}")
            except (BrokenPipeError, ConnectionResetError) as e:
                self._finish_call_log(status_code=499, success=False, error=e)
            except Exception as e:
                log(f"request {req_id}: google stream upstream error after headers: {e}")
                self._write_sse_error(f"upstream error: {e}")
            return

        try:
            text = generate(prompt, model_id, think_mode, file_refs, extra_fields, use_cookie=use_cookie)
        except Exception as e:
            self._update_call_log(error_type=e.__class__.__name__, error_message=f"upstream error: {e}")
            self.send_json({"error": {"message": f"upstream error: {e}"}}, 502)
            return
        log(f"request {req_id}: google upstream text_len={len(text or '')}")

        if not text:
            log(f"request {req_id}: warning empty response from Gemini")

        response_parts = []
        if has_tools and text:
            clean_text, function_calls = parse_google_function_calls(text, allowed_tool_names)
            log(
                f"request {req_id}: google parsed function_calls={len(function_calls)} "
                f"text_len={len(clean_text or '')}"
            )
            if function_calls:
                if clean_text:
                    response_parts.append({"text": clean_text})
                for fc in function_calls:
                    response_parts.append({"functionCall": {"name": fc["name"], "args": fc["args"]}})
            else:
                response_parts.append({"text": text})
        else:
            response_parts.append({"text": text or "I apologize, but I was unable to generate a response. Please try again."})

        candidate = {
            "content": {"parts": response_parts, "role": "model"},
            "finishReason": "STOP",
            "index": 0,
        }
        usage = {
            "promptTokenCount": len(prompt) // 4,
            "candidatesTokenCount": len(text or "") // 4,
            "totalTokenCount": (len(prompt) + len(text or "")) // 4,
        }
        self._update_call_log(
            response_chars=len(text or ""),
            completion_tokens=usage["candidatesTokenCount"],
            total_tokens=usage["totalTokenCount"],
        )
        response_obj = {
            "candidates": [candidate],
            "usageMetadata": usage,
            "modelVersion": model_name,
        }

        if stream:
            self._start_sse()
            self.wfile.write(f"data: {json.dumps(response_obj, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()
        else:
            self.send_json(response_obj)


class ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
