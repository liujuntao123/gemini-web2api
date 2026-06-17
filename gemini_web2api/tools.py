"""Tool calling and multimodal message parsing."""
import json
import re
import uuid
import base64
import binascii
import mimetypes
from urllib.parse import urlparse


def _build_tool_choice_instruction(tool_choice, tool_defs: list) -> str:
    """Build tool_choice constraint instruction.

    tool_choice values:
      - "none": do not call any tool
      - "auto": decide whether to call tools (default)
      - "required": must call at least one tool
      - {"type": "function", "function": {"name": "xxx"}}: must call specific tool
    """
    if tool_choice == "none":
        return "\n\nIMPORTANT: Do NOT call any tools. Respond with text only."
    if tool_choice == "required":
        return "\n\nIMPORTANT: You MUST call at least one tool. Do not respond with text only."
    if isinstance(tool_choice, dict):
        fn_name = tool_choice.get("function", {}).get("name", "")
        if fn_name:
            return f'\n\nIMPORTANT: You MUST call the tool "{fn_name}". Do not call other tools.'
    return ""


def openai_tool_defs(tools: list) -> list:
    """Return compact OpenAI function tool definitions."""
    out = []
    for tool in tools or []:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function", tool) if tool.get("type") == "function" else tool
        name = fn.get("name") or tool.get("name") or ""
        if not name:
            continue
        out.append({
            "name": name,
            "description": fn.get("description", tool.get("description", "")),
            "parameters": fn.get("parameters", tool.get("parameters", {})),
        })
    return out


def google_tool_defs(req: dict) -> list:
    """Return compact Google native function tool definitions."""
    out = []
    for group in (req or {}).get("tools") or []:
        if not isinstance(group, dict):
            continue
        for fn in group.get("functionDeclarations") or group.get("function_declarations") or []:
            if not isinstance(fn, dict) or not fn.get("name"):
                continue
            out.append({
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters") or fn.get("parametersJsonSchema") or fn.get("parameters_json_schema") or {},
            })
    return out


def build_tools_context_transcript(tool_defs: list, choice_instruction: str = "", filename: str = "tools.txt") -> str:
    if not tool_defs:
        return ""
    policy = f"\n\nTool choice policy:\n{choice_instruction.strip()}\n" if choice_instruction else "\n"
    return (
        f"# {filename or 'tools.txt'}\n"
        "Available tool descriptions and parameter schemas.\n\n"
        f"{json.dumps(tool_defs, indent=2, ensure_ascii=False)}"
        f"{policy}"
    )


def normalize_history_role(role) -> str:
    role = str(role or "").strip().lower()
    if role == "function":
        return "tool"
    if role == "developer":
        return "system"
    return role or "user"


def _role_label(role) -> str:
    return (normalize_history_role(role) or "unknown").upper()


def _content_text_for_history(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (int, float, bool)):
        return str(content)
    if isinstance(content, list):
        parts = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(item.get("input_text"), str):
                parts.append(item["input_text"])
            elif item.get("type") in ("input_file", "file"):
                suffix = f" {item.get('file_id')}" if item.get("file_id") else ""
                parts.append(f"[file input{suffix}]")
            elif item.get("type") in ("image_url", "input_image", "image") or item.get("image_url") or item.get("inlineData"):
                parts.append("[image input]")
        return "\n".join(parts)
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"]
        if isinstance(content.get("output"), str):
            return content["output"]
        return json.dumps(content, ensure_ascii=False)
    return str(content)


def _parse_json_object(value) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_openai_history_transcript(messages: list, filename: str = "message.txt") -> str:
    entries = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        role = normalize_history_role(msg.get("role"))
        content = _content_text_for_history(msg.get("content"))
        if role == "assistant" and msg.get("tool_calls"):
            blocks = []
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                blocks.append(
                    "```tool_call\n"
                    + json.dumps({"name": fn.get("name", ""), "arguments": _parse_json_object(fn.get("arguments", "{}"))}, ensure_ascii=False)
                    + "\n```"
                )
            content = "\n\n".join([content, *blocks]).strip()
        elif role == "tool":
            meta = []
            if msg.get("name"):
                meta.append(f"name={msg.get('name')}")
            if msg.get("tool_call_id"):
                meta.append(f"tool_call_id={msg.get('tool_call_id')}")
            prefix = f"[{' '.join(meta)}]\n" if meta else ""
            content = prefix + (content.strip() or "null")
        content = str(content or "").strip()
        if content:
            entries.append({"role": role, "content": content})
    if not entries:
        return ""
    sections = [f"=== {i}. {_role_label(e['role'])} ===\n{e['content']}" for i, e in enumerate(entries, 1)]
    return f"# {filename or 'message.txt'}\nPrior conversation history and tool progress.\n\n" + "\n\n".join(sections) + "\n"


def build_google_history_transcript(req: dict, filename: str = "message.txt") -> str:
    messages = []
    sys_inst = (req or {}).get("systemInstruction")
    if isinstance(sys_inst, dict):
        text = "\n".join(p.get("text", "") for p in sys_inst.get("parts", []) if isinstance(p, dict) and p.get("text"))
        if text:
            messages.append({"role": "system", "content": text})
    for content in (req or {}).get("contents") or []:
        if not isinstance(content, dict):
            continue
        parts = []
        for p in content.get("parts") or []:
            if not isinstance(p, dict):
                continue
            if p.get("text"):
                parts.append(p["text"])
            elif p.get("inlineData"):
                parts.append("[image input]")
            elif p.get("fileData"):
                uri = p["fileData"].get("fileUri") or p["fileData"].get("uri") or ""
                parts.append(f"[file input {uri}]".strip())
            elif p.get("functionCall"):
                fc = p["functionCall"]
                parts.append(
                    "```function_call\n"
                    + json.dumps({"name": fc.get("name", ""), "args": fc.get("args", {})}, ensure_ascii=False)
                    + "\n```"
                )
            elif p.get("functionResponse"):
                fr = p["functionResponse"]
                parts.append(f"[Tool result for {fr.get('name', '')}]: {json.dumps(fr.get('response', {}), ensure_ascii=False)}")
        messages.append({"role": "assistant" if content.get("role") == "model" else "user", "content": "\n".join(parts)})
    return build_openai_history_transcript(messages, filename)


def latest_openai_user_input_text(messages: list) -> str:
    for msg in reversed(messages or []):
        if not isinstance(msg, dict):
            continue
        if normalize_history_role(msg.get("role")) != "user":
            continue
        text = _content_text_for_history(msg.get("content")).strip()
        if text:
            return text
    return ""


def latest_google_user_input_text(req: dict) -> str:
    contents = (req or {}).get("contents") or []
    for content in reversed(contents):
        if not isinstance(content, dict) or content.get("role") == "model":
            continue
        parts = []
        for p in content.get("parts") or []:
            if not isinstance(p, dict):
                continue
            if p.get("text"):
                parts.append(p["text"])
            elif p.get("inlineData"):
                parts.append("[image input]")
            elif p.get("fileData"):
                uri = p["fileData"].get("fileUri") or p["fileData"].get("uri") or ""
                parts.append(f"[file input {uri}]".strip())
        text = "\n".join(parts).strip()
        if text:
            return text
    return ""


def parse_data_url(url: str) -> dict:
    """Parse a data: URL into attachment metadata."""
    if not url or not isinstance(url, str):
        return None
    m = re.match(r"^data:([^,]*?);base64,([\s\S]*)$", url, re.IGNORECASE)
    if not m:
        return None
    mime_type = (m.group(1).split(";")[0] or "application/octet-stream").lower()
    try:
        return {"data": base64.b64decode(m.group(2), validate=True), "mime_type": mime_type}
    except (binascii.Error, ValueError):
        return None


def parse_image_url(url: str) -> dict:
    """Parse an OpenAI image_url value into attachment metadata."""
    parsed = parse_data_url(url)
    if parsed:
        parsed["name"] = _filename_for_mime(parsed["mime_type"], "image.png")
        return parsed
    if isinstance(url, str) and re.match(r"^https?://", url, re.IGNORECASE):
        return {"url": url, "mime_type": "image/png", "name": _filename_from_url(url, "image.png")}
    return None


def _filename_for_mime(mime_type: str, default: str) -> str:
    mime_type = (mime_type or "").split(";")[0].lower()
    if mime_type.startswith("image/"):
        ext = mime_type.split("/", 1)[1] or "png"
        return f"image.{ext}"
    ext = mimetypes.guess_extension(mime_type)
    return f"file{ext}" if ext else default


def _filename_from_url(url: str, default: str) -> str:
    path = urlparse(url).path
    name = path.rsplit("/", 1)[-1] if path else ""
    return name or default


def _append_input_file(attachments: list, item: dict, text_parts: list):
    file_value = item.get("file") if isinstance(item.get("file"), dict) else item
    attachments.append({
        "type": "file",
        "mime_type": file_value.get("mime_type") or file_value.get("mimeType") or "application/octet-stream",
        "name": file_value.get("filename") or file_value.get("name") or "file",
    })


def _content_list_to_text_and_attachments(content: list, image_note: bool = False) -> tuple:
    text_parts = []
    attachments = []
    for c in content:
        if not isinstance(c, dict):
            continue
        ctype = c.get("type")
        if ctype in ("text", "input_text"):
            text_parts.append(c.get("text", ""))
        elif ctype in ("image_url", "input_image"):
            attachments.append({"type": "image", "mime_type": "image/png", "name": "image.png"})
        elif ctype in ("image", "input_file", "file"):
            if ctype == "image":
                attachments.append({
                    "type": "image",
                    "mime_type": c.get("mime_type") or c.get("mimeType") or "image/png",
                    "name": "image.png",
                })
            else:
                _append_input_file(attachments, c, text_parts)
    return "\n".join(text_parts), attachments


def messages_to_prompt(messages: list, tools: list = None, tool_choice=None) -> tuple:
    """Convert OpenAI messages to (prompt_str, attachments_list).

    Returns (prompt, attachments) where attachments contains file upload specs.
    """
    parts = []
    attachments = []

    if tools and tool_choice != "none":
        tool_defs = []
        for tool in tools:
            fn = tool.get("function", tool) if tool.get("type") == "function" else tool
            tool_defs.append({
                "name": fn.get("name", tool.get("name", "")),
                "description": fn.get("description", tool.get("description", "")),
                "parameters": fn.get("parameters", tool.get("parameters", {})),
            })
        if tool_defs:
            constraint = _build_tool_choice_instruction(tool_choice, tool_defs)
            parts.append(
                "# Tool Use\n\n"
                "You can call the following tools. Call format:\n"
                '```tool_call\n{"name": "func_name", "arguments": {...}}\n```\n'
                "When calling tools, output ONLY the tool_call block(s).\n\n"
                f"Available tools:\n{json.dumps(tool_defs, indent=2)}"
                f"{constraint}"
            )

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, list):
            content, found = _content_list_to_text_and_attachments(content, image_note=True)
            attachments.extend(found)

        if role == "system":
            parts.append(f"[System instruction]: {content}")
        elif role == "assistant":
            if msg.get("tool_calls"):
                tc_strs = []
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    tc_strs.append(
                        f'```tool_call\n{{"name": "{fn.get("name")}", '
                        f'"arguments": {fn.get("arguments", "{}")}}}\n```'
                    )
                parts.append(f"[Assistant]: {content or ''}\n" + "\n".join(tc_strs))
            else:
                parts.append(f"[Assistant]: {content}")
        elif role == "tool":
            parts.append(f"[Tool result for {msg.get('name', '')}]: {content}")
        else:
            parts.append(content if content else "")

    prompt = "\n\n".join(p for p in parts if p)
    return prompt, attachments


def parse_tool_calls(text: str) -> tuple:
    """Extract tool_call blocks. Returns (clean_text, tool_calls_list)."""
    tool_calls = []
    pattern = r'```tool_call\s*\n(.*?)\n```'
    clean_parts = []
    last_end = 0
    for m in re.finditer(pattern, text, re.DOTALL):
        try:
            data = json.loads(m.group(1).strip())
            tool_calls.append({
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": {
                    "name": data["name"],
                    "arguments": json.dumps(data.get("arguments", {}), ensure_ascii=False),
                },
            })
            clean_parts.append(text[last_end:m.start()])
            last_end = m.end()
        except (json.JSONDecodeError, KeyError):
            pass
    clean_parts.append(text[last_end:])
    clean = "".join(clean_parts)
    return clean, tool_calls


# ─── Google Native API helpers ─────────────────────────────────────────────────


def build_tool_prompt(tool_defs: list) -> str:
    """Build natural tool-use prompt for Gemini Web that avoids prompt-injection detection."""
    tool_spec = json.dumps(tool_defs, indent=2, ensure_ascii=False)
    return (
        "# Tool Use\n\n"
        "You can call the following tools to help accomplish tasks. "
        "These tools connect to the user's local environment and will execute when called.\n\n"
        "Call format (use this exact format):\n"
        "```function_call\n"
        '{"name": "<tool_name>", "args": {<arguments>}}\n'
        "```\n\n"
        "When calling tools:\n"
        "- Output ONLY the function_call block(s), nothing else\n"
        "- You may call multiple tools with multiple blocks\n"
        "- After receiving a [Tool result for ...], use that data to answer the user\n\n"
        f"Available tools:\n{tool_spec}"
    )


def _google_tool_choice_instruction(req: dict) -> str:
    """Extract tool_choice constraint from Google API toolConfig."""
    tool_config = req.get("toolConfig", {})
    fc_config = tool_config.get("functionCallingConfig", {})
    mode = fc_config.get("mode", "AUTO")
    allowed = fc_config.get("allowedFunctionNames", [])

    if mode == "NONE":
        return "\n\nIMPORTANT: Do NOT call any tools. Respond with text only."
    if mode == "ANY":
        if allowed:
            names = ", ".join(f'"{n}"' for n in allowed)
            return f"\n\nIMPORTANT: You MUST call one of these tools: {names}. Do not respond with text only."
        return "\n\nIMPORTANT: You MUST call at least one tool. Do not respond with text only."
    return ""


def google_contents_to_prompt(req: dict) -> tuple:
    """Convert Google API contents/tools/systemInstruction to (prompt_str, attachments_list).

    Returns (prompt, attachments) where attachments contains file upload specs.
    """
    parts = []
    attachments = []

    tool_config = req.get("toolConfig", {})
    fc_mode = tool_config.get("functionCallingConfig", {}).get("mode", "AUTO")

    tools = req.get("tools")
    tool_defs = []
    if tools and fc_mode != "NONE":
        for tool_group in tools:
            for fn in tool_group.get("functionDeclarations", []):
                td = {"name": fn.get("name", ""), "description": fn.get("description", "")}
                params = fn.get("parameters") or fn.get("parametersJsonSchema")
                if params:
                    td["parameters"] = params
                tool_defs.append(td)

    sys_inst = req.get("systemInstruction")
    if sys_inst:
        sys_parts = sys_inst.get("parts", [])
        sys_text = "\n".join(p.get("text", "") for p in sys_parts if p.get("text"))
        if sys_text:
            if tool_defs:
                constraint = _google_tool_choice_instruction(req)
                parts.append(sys_text + "\n\n" + build_tool_prompt(tool_defs) + constraint)
            else:
                parts.append(sys_text)
    elif tool_defs:
        constraint = _google_tool_choice_instruction(req)
        parts.append(build_tool_prompt(tool_defs) + constraint)

    for content in req.get("contents", []):
        if not isinstance(content, dict):
            continue
        role = content.get("role", "user")
        msg_parts = []
        for p in content.get("parts", []):
            if not isinstance(p, dict):
                continue
            if p.get("text"):
                msg_parts.append(p["text"])
            elif p.get("inlineData"):
                data = p["inlineData"]
                mime = data.get("mimeType", "image/png") if isinstance(data, dict) else "image/png"
                attachments.append({
                    "type": "image" if mime.startswith("image/") else "file",
                    "mime_type": mime,
                    "name": "image.png" if mime.startswith("image/") else "file",
                })
            elif p.get("fileData"):
                file_data = p["fileData"] if isinstance(p["fileData"], dict) else {}
                mime = file_data.get("mimeType") or "application/octet-stream"
                attachments.append({"type": "file", "mime_type": mime, "name": file_data.get("displayName") or "file"})
            elif p.get("functionCall"):
                fc = p["functionCall"]
                msg_parts.append(
                    f'```function_call\n{json.dumps({"name": fc["name"], "args": fc.get("args", {})}, ensure_ascii=False)}\n```'
                )
            elif p.get("functionResponse"):
                fr = p["functionResponse"]
                msg_parts.append(
                    f'[Tool result for {fr.get("name", "")}]: {json.dumps(fr.get("response", {}), ensure_ascii=False)}'
                )
        text = "\n".join(msg_parts)
        if role == "model":
            parts.append(f"[Assistant]: {text}")
        else:
            parts.append(text)

    return "\n\n".join(p for p in parts if p), attachments


def google_tool_names(req: dict) -> set:
    """Return declared Google native function names from a request."""
    names = set()
    for tool_group in req.get("tools") or []:
        for fn in tool_group.get("functionDeclarations", []):
            name = fn.get("name")
            if name:
                names.add(name)
    return names


def parse_google_function_calls(text: str, allowed_names: set = None) -> tuple:
    """Extract function_call blocks from model output.

    Handles 3 formats:
    1. ```function_call\\n{...}\\n``` (standard)
    2. function_call\\n{...} (without backticks)
    3. Raw JSON with "name" + "args" keys, only when the name matches a
       declared tool. This avoids treating ordinary JSON answers as tool calls.

    Returns (clean_text, [{"name": ..., "args": ...}])
    """
    function_calls = []
    pattern1 = r'```function_call\s*\n(.*?)\n```'
    pattern2 = r'(?:^|\n)function_call\s*\n(\{[^`]*?\})'
    clean = text
    for pattern in [pattern1, pattern2]:
        clean_parts = []
        last_end = 0
        for match in re.finditer(pattern, clean, re.DOTALL):
            try:
                data = json.loads(match.group(1).strip())
                if "name" in data:
                    function_calls.append({
                        "name": data["name"],
                        "args": data.get("args", data.get("arguments", {})),
                    })
                    clean_parts.append(clean[last_end:match.start()])
                    last_end = match.end()
            except (json.JSONDecodeError, KeyError):
                pass
        clean_parts.append(clean[last_end:])
        clean = "".join(clean_parts)
    if not function_calls and allowed_names and clean.strip().startswith("{"):
        try:
            data = json.loads(clean.strip())
            if data.get("name") in allowed_names and ("args" in data or "arguments" in data):
                function_calls.append({
                    "name": data["name"],
                    "args": data.get("args", data.get("arguments", {})),
                })
                clean = ""
        except (json.JSONDecodeError, KeyError):
            pass
    return clean, function_calls
