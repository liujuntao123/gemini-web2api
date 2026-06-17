"""Multimodal: Scotty resumable upload for Gemini file input."""
import urllib.request
import time
import re
from dataclasses import dataclass
from typing import Optional

from .config import CONFIG
from .gemini import load_cookie, make_sapisidhash, _get_ssl_ctx, log


@dataclass
class UploadFile:
    data: bytes = None
    mime_type: str = "application/octet-stream"
    name: str = "file"
    url: str = None


def _get_page_tokens() -> dict:
    """Fetch WIZ_global_data tokens from Gemini page (Push-ID, X-Client-Pctx)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    cookie_str, sapisid = load_cookie()
    if cookie_str:
        headers["Cookie"] = cookie_str
    try:
        req = urllib.request.Request("https://gemini.google.com/app", headers=headers)
        resp = _open_request(req, timeout=30)
        html = resp.read().decode()
        tokens = {}
        for key, patterns in [
            ("push_id", [r'"qKIAYe":"([^"]+)"']),
            ("pctx", [r'"Ylro7b":"([^"]+)"']),
            ("at", [r'"SNlM0e":"([^"]+)"', r'"thykhd":"([^"]+)"']),
        ]:
            for pattern in patterns:
                m = re.search(pattern, html)
                if m:
                    tokens[key] = m.group(1)
                    break
        return tokens
    except Exception as e:
        log(f"Page token fetch failed: {e}")
        return {}


_page_tokens_cache = {"tokens": {}, "ts": 0}


def _cached_page_tokens() -> dict:
    now = time.time()
    if now - _page_tokens_cache["ts"] > 600:
        _page_tokens_cache["tokens"] = _get_page_tokens()
        _page_tokens_cache["ts"] = now
    return _page_tokens_cache["tokens"]


def has_cookie() -> bool:
    cookie_str, _ = load_cookie()
    return bool(cookie_str)


def prompt_byte_length(value) -> int:
    return len(str(value or "").encode("utf-8"))


def sanitize_upload_filename(name) -> str:
    name = str(name or "").strip()
    if not name:
        return "file"
    name = re.sub(r"[\x00-\x1f\x7f\r\n\t]", " ", name).strip()
    name = re.split(r"[\\/]", name)[-1].strip()
    if not name or name in (".", ".."):
        return "file"
    return name[:180]


def normalize_mime_type(mime_type: str) -> str:
    mime_type = str(mime_type or "application/octet-stream").strip()
    if not mime_type:
        return "application/octet-stream"
    if ";" in mime_type and not mime_type.lower().startswith("text/plain;"):
        mime_type = mime_type.split(";", 1)[0].strip()
    return mime_type or "application/octet-stream"


def _open_request(req, timeout: int):
    ctx = _get_ssl_ctx()
    proxy = CONFIG.get("proxy")
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
            urllib.request.HTTPSHandler(context=ctx)
        )
        return opener.open(req, timeout=timeout)
    return urllib.request.urlopen(req, context=ctx, timeout=timeout)


def upload_file(data: bytes, filename: str = "file", mime_type: str = "application/octet-stream") -> str:
    """Upload file via Scotty resumable upload. Returns file reference path."""
    if not data:
        raise ValueError("cannot upload empty file")
    filename = sanitize_upload_filename(filename)
    mime_type = normalize_mime_type(mime_type)

    tokens = _cached_page_tokens()
    push_id = tokens.get("push_id", "feeds/mcudyrk2a4khkz")
    pctx = tokens.get("pctx", "CgcSBWjK7pYx")

    cookie_str, sapisid = load_cookie()
    if not cookie_str:
        raise RuntimeError("file upload requires cookie_file")

    # Step 1: Initiate resumable upload
    start_headers = {
        "Push-ID": push_id,
        "X-Tenant-Id": "bard-storage",
        "X-Client-Pctx": pctx,
        "X-Goog-Upload-Header-Content-Length": str(len(data)),
        "X-Goog-Upload-Header-Content-Type": mime_type,
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    if cookie_str:
        start_headers["Cookie"] = cookie_str
    if sapisid:
        start_headers["Authorization"] = make_sapisidhash(sapisid)

    start_url = "https://content-push.googleapis.com/upload/"
    req = urllib.request.Request(start_url, data=b"", headers=start_headers, method="POST")
    resp = _open_request(req, timeout=30)

    upload_url = resp.headers.get("X-Goog-Upload-URL") or resp.headers.get("x-goog-upload-url")
    if not upload_url:
        raise RuntimeError(f"No upload URL in response headers: {dict(resp.headers)}")

    log(f"Upload session started: {upload_url[:80]}...")

    # Step 2: Upload file data + finalize
    upload_headers = {
        "X-Goog-Upload-Command": "upload, finalize",
        "X-Goog-Upload-Offset": "0",
        "Content-Type": "application/octet-stream",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    req2 = urllib.request.Request(upload_url, data=data, headers=upload_headers, method="POST")
    resp2 = _open_request(req2, timeout=60)

    file_ref = resp2.read().decode().strip()
    if not file_ref or not file_ref.startswith("/"):
        raise RuntimeError(f"Invalid file reference: {file_ref[:100]}")

    log(f"File uploaded: {filename} ({mime_type}, {len(data)} bytes) -> {file_ref[:50]}...")
    return file_ref


def upload_image(image_bytes: bytes, filename: str = "image.png", mime_type: str = "image/png") -> str:
    """Upload image via Scotty resumable upload. Returns file reference path."""
    return upload_file(image_bytes, filename, mime_type)


def upload_text_file(text: str, filename: str = None) -> dict:
    """Upload UTF-8 text as a Gemini file attachment."""
    filename = filename or CONFIG.get("current_input_file_name") or "message.txt"
    mime_type = "text/plain; charset=utf-8"
    data = str(text or "").encode("utf-8")
    ref = upload_file(data, filename, mime_type)
    return {"ref": ref, "name": filename, "mime_type": mime_type}


def resolve_upload_files(files: list) -> tuple:
    """Upload file descriptors and return (file_refs, dropped_note)."""
    if not files:
        return None, ""
    if not has_cookie():
        return None, "[Note: file and image input requires cookie_file]"

    refs = []
    failed = 0
    for item in files:
        try:
            upload = normalize_upload_file(item)
            if not upload:
                continue
            data = upload.data
            mime = normalize_mime_type(upload.mime_type)
            name = sanitize_upload_filename(upload.name)
            if upload.url:
                data, fetched_mime = fetch_url_bytes(upload.url)
                mime = normalize_mime_type(fetched_mime or mime)
            if not data:
                failed += 1
                continue
            ref = upload_file(data, name, mime)
            refs.append({"ref": ref, "name": name, "mime_type": mime})
        except Exception as e:
            failed += 1
            log(f"File upload failed: {e}")

    if failed and not refs:
        return None, "[Note: file input upload failed]"
    if failed:
        return refs or None, f"[Note: {failed} file input(s) failed to upload]"
    return refs or None, ""


def normalize_upload_file(item) -> Optional[UploadFile]:
    if isinstance(item, UploadFile):
        return item
    if isinstance(item, tuple) and len(item) >= 2:
        data, mime = item[:2]
        name = item[2] if len(item) > 2 else _default_name_for_mime(mime)
        if isinstance(data, str):
            return UploadFile(url=data, mime_type=mime or "application/octet-stream", name=name)
        return UploadFile(data=data, mime_type=mime or "application/octet-stream", name=name)
    if isinstance(item, dict):
        return UploadFile(
            data=item.get("data"),
            mime_type=item.get("mime_type") or item.get("mime") or "application/octet-stream",
            name=sanitize_upload_filename(item.get("name") or item.get("filename") or "file"),
            url=item.get("url"),
        )
    return None


def _default_name_for_mime(mime: str) -> str:
    mime = (mime or "").split(";")[0].lower()
    if mime.startswith("image/"):
        ext = mime.split("/", 1)[1] or "png"
        return f"image.{ext}"
    if mime == "text/plain":
        return "file.txt"
    if mime == "application/pdf":
        return "file.pdf"
    return "file"


def fetch_url_bytes(url: str) -> tuple:
    """Fetch a URL and return (bytes, content_type)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = _open_request(req, timeout=30)
        return resp.read(), resp.headers.get("Content-Type")
    except Exception as e:
        log(f"URL fetch failed: {e}")
        return b"", None


def fetch_image_bytes(url: str) -> bytes:
    """Fetch image from URL."""
    data, _ = fetch_url_bytes(url)
    return data
