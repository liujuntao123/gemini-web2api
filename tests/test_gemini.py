import json

import pytest

from gemini_web2api.gemini import (
    EmptyGeminiResponse,
    GeminiUpstreamError,
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
