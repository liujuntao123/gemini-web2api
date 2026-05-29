from gemini_web2api.tools import parse_google_function_calls


def test_plain_json_answer_is_not_function_call_without_allowed_tool_name():
    text = '{"name": "status", "args": {"ok": true}}'

    clean, calls = parse_google_function_calls(text, {"get_weather"})

    assert clean == text
    assert calls == []


def test_plain_json_matching_allowed_tool_name_is_function_call():
    clean, calls = parse_google_function_calls(
        '{"name": "get_weather", "args": {"city": "Tokyo"}}',
        {"get_weather"},
    )

    assert clean == ""
    assert calls == [{"name": "get_weather", "args": {"city": "Tokyo"}}]


def test_explicit_function_call_block_is_function_call():
    clean, calls = parse_google_function_calls(
        '```function_call\n{"name": "status", "args": {"ok": true}}\n```',
        {"get_weather"},
    )

    assert clean == ""
    assert calls == [{"name": "status", "args": {"ok": True}}]
