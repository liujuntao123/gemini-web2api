"""Multimodal compatibility helpers.

This build intentionally supports anonymous text-only Gemini Web requests.
Image/file upload helpers are kept as explicit rejection points for callers
that import them directly.
"""
import re
from dataclasses import dataclass
from typing import Optional


UNSUPPORTED_UPLOAD_MESSAGE = "image and file inputs are not supported"


@dataclass
class UploadFile:
    data: bytes = None
    mime_type: str = "application/octet-stream"
    name: str = "file"
    url: str = None


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


def upload_file(data: bytes, filename: str = "file", mime_type: str = "application/octet-stream") -> str:
    raise RuntimeError(UNSUPPORTED_UPLOAD_MESSAGE)


def upload_image(image_bytes: bytes, filename: str = "image.png", mime_type: str = "image/png") -> str:
    raise RuntimeError(UNSUPPORTED_UPLOAD_MESSAGE)


def upload_text_file(text: str, filename: str = None) -> dict:
    raise RuntimeError(UNSUPPORTED_UPLOAD_MESSAGE)


def resolve_upload_files(files: list) -> tuple:
    if not files:
        return None, ""
    raise RuntimeError(UNSUPPORTED_UPLOAD_MESSAGE)


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
    raise RuntimeError(UNSUPPORTED_UPLOAD_MESSAGE)


def fetch_image_bytes(url: str) -> bytes:
    raise RuntimeError(UNSUPPORTED_UPLOAD_MESSAGE)
