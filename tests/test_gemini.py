import json
import pytest

from gemini_web2api.gemini import (
    EmptyGeminiResponse,
    GeminiUpstreamError,
    _build_headers,
    _build_payload,
    extract_response_text,
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


def test_build_payload_is_text_only():
    import urllib.parse

    body = _build_payload("plain text only", 2, 0)
    outer = json.loads(urllib.parse.parse_qs(body)["f.req"][0])
    inner = json.loads(outer[1])

    assert inner[0] == ["plain text only", 0, None, None, None, None, 0]


def test_build_headers_never_include_cookie_auth():
    headers = _build_headers()

    assert "Cookie" not in headers
    assert "Authorization" not in headers
