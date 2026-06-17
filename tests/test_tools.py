from gemini_web2api.tools import (
    google_contents_to_prompt,
    messages_to_prompt,
    parse_google_function_calls,
    parse_tool_calls,
)


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


def test_invalid_tool_call_block_preserves_text():
    text = 'before\n```tool_call\n{"name":\n```\nafter'

    clean, calls = parse_tool_calls(text)

    assert clean == text
    assert calls == []


def test_invalid_google_function_call_block_preserves_text():
    text = 'before\n```function_call\n{"name":\n```\nafter'

    clean, calls = parse_google_function_calls(text, {"status"})

    assert clean == text
    assert calls == []


def test_invalid_inline_data_becomes_attachment_marker():
    prompt, images = google_contents_to_prompt({
        "contents": [{
            "role": "user",
            "parts": [{"inlineData": {"mimeType": "image/png", "data": "not-base64"}}],
        }],
    })

    assert prompt == ""
    assert images == [{"type": "image", "mime_type": "image/png", "name": "image.png"}]


def test_non_dict_content_parts_are_ignored():
    prompt, images = google_contents_to_prompt({
        "contents": [{
            "role": "user",
            "parts": ["bad", {"text": "hello"}],
        }],
    })

    assert prompt == "hello"
    assert images == []


def test_non_dict_messages_are_ignored():
    prompt, images = google_contents_to_prompt({
        "contents": ["bad", {"role": "user", "parts": [{"text": "hello"}]}],
    })

    assert prompt == "hello"
    assert images == []


def test_openai_image_url_data_becomes_attachment_marker():
    prompt, attachments = messages_to_prompt([{
        "role": "user",
        "content": [
            {"type": "text", "text": "describe it"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,aGk="}},
        ],
    }])

    assert prompt == "describe it"
    assert attachments == [{"type": "image", "mime_type": "image/png", "name": "image.png"}]


def test_openai_input_file_data_becomes_attachment_marker():
    prompt, attachments = messages_to_prompt([{
        "role": "user",
        "content": [{
            "type": "input_file",
            "filename": "notes.txt",
            "mime_type": "text/plain",
            "file_data": "data:text/plain;base64,aGVsbG8=",
        }],
    }])

    assert prompt == ""
    assert attachments == [{"type": "file", "mime_type": "text/plain", "name": "notes.txt"}]


def test_openai_input_file_nested_file_object_becomes_attachment_marker():
    prompt, attachments = messages_to_prompt([{
        "role": "user",
        "content": [{
            "type": "input_file",
            "file": {
                "filename": "notes.txt",
                "mime_type": "text/plain",
                "file_data": "aGVsbG8=",
            },
        }],
    }])

    assert prompt == ""
    assert attachments == [{"type": "file", "mime_type": "text/plain", "name": "notes.txt"}]
