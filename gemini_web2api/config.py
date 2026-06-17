"""Configuration management."""
import json
import os

DEFAULT_CONFIG = {
    "port": 8081,
    "host": "0.0.0.0",
    "retry_attempts": 3,
    "retry_delay_sec": 2,
    "request_timeout_sec": 180,
    "max_request_body_bytes": 50 * 1024 * 1024,
    "max_upstream_prompt_bytes": 180 * 1024,
    "current_input_file_enabled": True,
    "current_input_file_min_bytes": 95000,
    "current_input_file_name": "message.txt",
    "current_input_file_prompt": "",
    "current_tools_file_name": "tools.txt",
    "gemini_bl": "boq_assistant-bard-web-server_20260610.04_p0",
    "default_model": "gemini-3.5-flash",
    "log_requests": True,
    "analytics_enabled": True,
    "analytics_db_path": "data/gemini_web2api_usage.sqlite3",
    "cookie_file": None,
    "proxy": None,
    "api_keys": [],
}

CONFIG = dict(DEFAULT_CONFIG)


def load_config(path: str = None):
    """Load config from JSON file."""
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("config file must contain a JSON object")
        CONFIG.update(data)
    return CONFIG


def find_config():
    """Search for config file in standard locations."""
    for p in ["./config.json", os.path.expanduser("~/.config/gemini-web2api/config.json")]:
        if os.path.exists(p):
            return p
    return None
