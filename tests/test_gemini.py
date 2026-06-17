import json
import urllib.parse

import pytest

from gemini_web2api.gemini import (
    EmptyGeminiResponse,
    GeminiUpstreamError,
    _append_page_token,
    _build_headers,
    _build_payload,
    extract_response_text,
    parse_cookie_content,
)


def _wrb_line(text: str) -> str:
    inner = [None] * 5
    inner[4] = [[None, [text]]]
    return json.dumps([["wrb.fr", None, json.dumps(inner)]])


def test_extract_response_text_raises_on_unparseable_payload():
    with pytest.raises(EmptyGeminiResponse):
        extract_response_text(")]}'\n[]")


def test_extract_response_text_parses_wrb_line_without_trailing_newline():
    assert extract_response_text(_wrb_line("hello")) == "hello"


def test_extract_response_text_raises_structured_bard_error():
    raw = (
        '[["wrb.fr",null,null,null,null,[13,null,'
        '[["type.googleapis.com/assistant.boq.bard.application.BardErrorInfo",[1099]]]]]]'
    )

    with pytest.raises(GeminiUpstreamError, match="1099"):
        extract_response_text(raw)


def test_extract_response_text_marks_1152_as_prompt_rejection():
    raw = (
        '[["wrb.fr",null,null,null,null,[13,null,'
        '[["type.googleapis.com/assistant.boq.bard.application.BardErrorInfo",[1152]]]]]]'
    )

    with pytest.raises(GeminiUpstreamError, match="prompt is likely too large"):
        extract_response_text(raw)


def test_build_payload_uses_gemini_file_ref_shape():
    body = _build_payload(
        "please analyze attachment",
        2,
        0,
        [{"ref": "/contrib_service/ttl_1d/abc", "name": "message.txt", "mime_type": "text/plain; charset=utf-8"}],
    )
    outer = json.loads(urllib.parse.parse_qs(body)["f.req"][0])
    inner = json.loads(outer[1])

    assert inner[0][3] == [[["/contrib_service/ttl_1d/abc", 1], "message.txt"]]


def test_parse_cookie_content_accepts_raw_cookie_header_value():
    cookie, sapisid = parse_cookie_content("SAPISID=abc/def; NID=123")

    assert cookie == "SAPISID=abc/def; NID=123"
    assert sapisid == "abc/def"


def test_parse_cookie_content_accepts_cookie_header_line():
    cookie, sapisid = parse_cookie_content("Cookie: __Secure-3PAPISID=secure; NID=123")

    assert cookie == "__Secure-3PAPISID=secure; NID=123"
    assert sapisid == "secure"


def test_parse_cookie_content_accepts_full_header_block():
    cookie, sapisid = parse_cookie_content(
        "User-Agent: Mozilla/5.0\n"
        "Accept: */*\n"
        "Cookie: AEC=x; SAPISID=header_sapisid; SID=s\n"
        "Authorization: SAPISIDHASH 1_deadbeef\n"
    )

    assert cookie == "AEC=x; SAPISID=header_sapisid; SID=s"
    assert sapisid == "header_sapisid"


def test_parse_cookie_content_accepts_json_headers_string():
    cookie, sapisid = parse_cookie_content(
        json.dumps({"headers": "Cookie: __Secure-1PAPISID=json_secure; SID=s"})
    )

    assert cookie == "__Secure-1PAPISID=json_secure; SID=s"
    assert sapisid == "json_secure"


def test_build_headers_can_skip_cookie(monkeypatch):
    monkeypatch.setattr("gemini_web2api.gemini.load_cookie", lambda: ("SAPISID=secret", "secret"))

    headers = _build_headers(use_cookie=False)

    assert "Cookie" not in headers
    assert "Authorization" not in headers


def test_append_page_token_can_skip_cookie(monkeypatch):
    def fail_load_cookie():
        raise AssertionError("load_cookie should not be called")

    monkeypatch.setattr("gemini_web2api.gemini.load_cookie", fail_load_cookie)

    assert _append_page_token("f.req=x", use_cookie=False) == "f.req=x"
