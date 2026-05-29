import json

from gemini_web2api.config import CONFIG
from gemini_web2api.server import (
    _configured_api_keys,
    _json_object,
    _max_request_body_bytes,
)


def test_json_object_rejects_arrays():
    assert _json_object(b'["not", "an", "object"]') is None


def test_json_object_accepts_objects():
    assert _json_object(b'{"ok": true}') == {"ok": True}


def test_default_request_body_limit_is_documented_in_example():
    with open("config.example.json", encoding="utf-8") as f:
        data = json.load(f)

    assert data["max_request_body_bytes"] == CONFIG["max_request_body_bytes"]


def test_invalid_configured_request_body_limit_uses_default(monkeypatch):
    monkeypatch.setitem(CONFIG, "max_request_body_bytes", "bad")

    assert _max_request_body_bytes() == 10 * 1024 * 1024


def test_non_positive_request_body_limit_uses_default(monkeypatch):
    monkeypatch.setitem(CONFIG, "max_request_body_bytes", 0)

    assert _max_request_body_bytes() == 10 * 1024 * 1024


def test_string_api_key_is_not_treated_as_iterable(monkeypatch):
    monkeypatch.setitem(CONFIG, "api_keys", "secret")

    assert _configured_api_keys() == {"secret"}
