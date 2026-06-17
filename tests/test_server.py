import json
from io import BytesIO

from gemini_web2api.config import CONFIG
from gemini_web2api.server import (
    GeminiHandler,
    UNSUPPORTED_ATTACHMENT_MESSAGE,
    _configured_api_keys,
    _json_object,
    _max_request_body_bytes,
    _max_upstream_prompt_bytes,
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

    def fake_generate(prompt, model_id, think_mode, extra_fields=None):
        calls.append({"prompt": prompt})
        return "hi"

    monkeypatch.setattr("gemini_web2api.server.generate", fake_generate)

    handler._handle_chat(body, "req")

    assert handler._call_log["upstream_mode"] == "anonymous"
    assert handler.responses[0][0] == 200


def test_chat_rejects_attachment(monkeypatch):
    calls = []
    handler = _DummyHandler()
    body = json.dumps({
        "model": "gemini-3.5-flash",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "look"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,aGk="}},
                ],
            },
        ],
    }).encode()

    def fake_generate(prompt, model_id, think_mode, extra_fields=None):
        calls.append(prompt)
        return "done"

    monkeypatch.setattr("gemini_web2api.server.generate", fake_generate)

    handler._handle_chat(body, "req")

    assert calls == []
    assert handler.responses[0][0] == 400
    assert handler.responses[0][1]["error"]["message"] == UNSUPPORTED_ATTACHMENT_MESSAGE


def test_chat_large_prompt_returns_413_before_upstream(monkeypatch):
    calls = []
    handler = _DummyHandler()
    body = json.dumps({
        "model": "gemini-3.5-flash",
        "messages": [{"role": "user", "content": "hello"}],
    }).encode()
    monkeypatch.setitem(CONFIG, "max_upstream_prompt_bytes", 100)

    def fake_generate(prompt, model_id, think_mode, extra_fields=None):
        calls.append(prompt)
        return "done"

    monkeypatch.setattr("gemini_web2api.server.generate", fake_generate)

    handler._handle_chat(body, "req")

    assert calls == []
    assert handler.responses[0][0] == 413
    assert handler.responses[0][1]["error"]["message"] == "prompt too large for Gemini Web upstream"
