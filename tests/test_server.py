import json
from io import BytesIO

from gemini_web2api.config import CONFIG
from gemini_web2api.server import (
    GeminiHandler,
    _configured_api_keys,
    _json_object,
    _max_request_body_bytes,
    _max_upstream_prompt_bytes,
    _prepare_openai_file_refs,
    _prepare_file_refs,
    _use_cookie_for_upstream,
    _upstream_prompt_size_error,
)


def test_json_object_rejects_arrays():
    assert _json_object(b'["not", "an", "object"]') is None


def test_json_object_accepts_objects():
    assert _json_object(b'{"ok": true}') == {"ok": True}


def test_default_request_body_limit_is_documented_in_example():
    with open("config.example.json", encoding="utf-8") as f:
        data = json.load(f)

    assert data["max_request_body_bytes"] == CONFIG["max_request_body_bytes"]
    assert data["max_upstream_prompt_bytes"] == CONFIG["max_upstream_prompt_bytes"]
    assert data["current_input_file_enabled"] == CONFIG["current_input_file_enabled"]
    assert data["current_input_file_min_bytes"] == CONFIG["current_input_file_min_bytes"]
    assert data["current_input_file_name"] == CONFIG["current_input_file_name"]
    assert data["current_input_file_prompt"] == CONFIG["current_input_file_prompt"]
    assert data["analytics_enabled"] == CONFIG["analytics_enabled"]
    assert data["analytics_db_path"] == CONFIG["analytics_db_path"]


def test_invalid_configured_request_body_limit_uses_default(monkeypatch):
    monkeypatch.setitem(CONFIG, "max_request_body_bytes", "bad")

    assert _max_request_body_bytes() == 50 * 1024 * 1024


def test_non_positive_request_body_limit_disables_local_cap(monkeypatch):
    monkeypatch.setitem(CONFIG, "max_request_body_bytes", 0)

    assert _max_request_body_bytes() is None


def test_null_request_body_limit_disables_local_cap(monkeypatch):
    monkeypatch.setitem(CONFIG, "max_request_body_bytes", None)

    assert _max_request_body_bytes() is None


def test_string_api_key_is_not_treated_as_iterable(monkeypatch):
    monkeypatch.setitem(CONFIG, "api_keys", "secret")

    assert _configured_api_keys() == {"secret"}


def test_positive_request_body_limit_is_used(monkeypatch):
    monkeypatch.setitem(CONFIG, "max_request_body_bytes", 123)

    assert _max_request_body_bytes() == 123


def test_invalid_upstream_prompt_limit_disables_guard(monkeypatch):
    monkeypatch.setitem(CONFIG, "max_upstream_prompt_bytes", "bad")

    assert _max_upstream_prompt_bytes() is None


def test_upstream_prompt_size_error_reports_payload_bytes(monkeypatch):
    monkeypatch.setitem(CONFIG, "max_upstream_prompt_bytes", 100)

    error = _upstream_prompt_size_error("hello", 2, 0)

    assert error["message"] == "prompt too large for Gemini Web upstream"
    assert error["upstream_prompt_bytes"] > 100
    assert error["limit"] == 100


def test_upstream_prompt_size_error_allows_small_payload(monkeypatch):
    monkeypatch.setitem(CONFIG, "max_upstream_prompt_bytes", 10 * 1024)

    assert _upstream_prompt_size_error("hello", 2, 0) is None


def test_prepare_file_refs_does_not_upload_prompt_without_history_context(monkeypatch):
    monkeypatch.setitem(CONFIG, "current_input_file_enabled", True)
    monkeypatch.setitem(CONFIG, "current_input_file_min_bytes", 5)
    monkeypatch.setitem(CONFIG, "current_input_file_name", "message.txt")
    monkeypatch.setitem(CONFIG, "current_input_file_prompt", "Please analyze the attached file.")
    monkeypatch.setattr("gemini_web2api.server.has_cookie", lambda: True)
    prompt, file_refs = _prepare_file_refs("hello world")

    assert prompt == "hello world"
    assert file_refs is None


def test_prepare_file_refs_notes_missing_cookie_for_attachment(monkeypatch):
    monkeypatch.setattr("gemini_web2api.server.has_cookie", lambda: False)

    prompt, file_refs = _prepare_file_refs(
        "look",
        [{"data": b"hi", "mime_type": "image/png", "name": "image.png"}],
    )

    assert "requires cookie_file" in prompt
    assert file_refs is None


def test_prepare_openai_file_refs_uploads_history_and_keeps_latest(monkeypatch):
    uploads = []
    monkeypatch.setitem(CONFIG, "current_input_file_enabled", True)
    monkeypatch.setitem(CONFIG, "current_input_file_min_bytes", 5)
    monkeypatch.setitem(CONFIG, "current_input_file_name", "message.txt")
    monkeypatch.setitem(CONFIG, "current_input_file_prompt", "Please analyze the attached file.")
    monkeypatch.setattr("gemini_web2api.server.has_cookie", lambda: True)

    def fake_upload(text, filename):
        uploads.append((filename, text))
        return {"ref": f"/contrib_service/ttl_1d/{filename}", "name": filename}

    monkeypatch.setattr("gemini_web2api.server.upload_text_file", fake_upload)
    messages = [
        {"role": "system", "content": "be concise"},
        {"role": "user", "content": "old context " * 20},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "what is the summary?"},
    ]

    prompt, file_refs = _prepare_openai_file_refs(
        "old context " * 20 + "\n\nwhat is the summary?",
        [],
        messages,
        None,
        "auto",
    )

    assert uploads[0][0] == "message.txt"
    assert "old context" in uploads[0][1]
    assert "Latest user request" in prompt
    assert "what is the summary?" in prompt
    assert file_refs == [{"ref": "/contrib_service/ttl_1d/message.txt", "name": "message.txt"}]


def test_use_cookie_for_upstream_only_when_files_are_bound():
    assert _use_cookie_for_upstream(None) is False
    assert _use_cookie_for_upstream([]) is False
    assert _use_cookie_for_upstream([{"ref": "/contrib_service/ttl_1d/file", "name": "file.txt"}]) is True


class _DummyHandler(GeminiHandler):
    def __init__(self):
        self.headers = {}
        self.wfile = BytesIO()
        self.client_address = ("127.0.0.1", 12345)
        self._call_log = {}
        self._call_log_start = 0
        self._call_log_recorded = False
        self.responses = []

    def send_json(self, data, status=200):
        self.responses.append((status, data))

    def _update_call_log(self, **fields):
        self._call_log.update({k: v for k, v in fields.items() if v is not None})


def test_chat_small_text_uses_anonymous_upstream(monkeypatch):
    calls = []
    handler = _DummyHandler()
    body = json.dumps({
        "model": "gemini-3.5-flash",
        "messages": [{"role": "user", "content": "hello"}],
    }).encode()

    def fake_generate(prompt, model_id, think_mode, file_refs=None, extra_fields=None, use_cookie=True):
        calls.append({"prompt": prompt, "file_refs": file_refs, "use_cookie": use_cookie})
        return "hi"

    monkeypatch.setattr("gemini_web2api.server.generate", fake_generate)

    handler._handle_chat(body, "req")

    assert calls[0]["file_refs"] is None
    assert calls[0]["use_cookie"] is False
    assert handler.responses[0][0] == 200


def test_chat_large_context_uses_cookie_upstream(monkeypatch):
    calls = []
    handler = _DummyHandler()
    body = json.dumps({
        "model": "gemini-3.5-flash",
        "messages": [
            {"role": "user", "content": "old context " * 20},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "summarize"},
        ],
    }).encode()

    monkeypatch.setitem(CONFIG, "current_input_file_enabled", True)
    monkeypatch.setitem(CONFIG, "current_input_file_min_bytes", 5)
    monkeypatch.setattr("gemini_web2api.server.has_cookie", lambda: True)
    monkeypatch.setattr(
        "gemini_web2api.server.upload_text_file",
        lambda text, filename: {"ref": f"/contrib_service/ttl_1d/{filename}", "name": filename},
    )

    def fake_generate(prompt, model_id, think_mode, file_refs=None, extra_fields=None, use_cookie=True):
        calls.append({"prompt": prompt, "file_refs": file_refs, "use_cookie": use_cookie})
        return "done"

    monkeypatch.setattr("gemini_web2api.server.generate", fake_generate)

    handler._handle_chat(body, "req")

    assert calls[0]["file_refs"]
    assert calls[0]["use_cookie"] is True
    assert handler.responses[0][0] == 200
