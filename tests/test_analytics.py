import http.client
import json
import threading
import time

from gemini_web2api import analytics
from gemini_web2api.config import CONFIG
from gemini_web2api.server import GeminiHandler, ThreadedServer


def _use_temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "usage.sqlite3"
    monkeypatch.setitem(CONFIG, "analytics_enabled", True)
    monkeypatch.setitem(CONFIG, "analytics_db_path", str(db_path))
    analytics._INITIALIZED_PATHS.discard(str(db_path))
    return db_path


def _get_json(host, port, path):
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.request("GET", path)
    response = conn.getresponse()
    data = json.loads(response.read())
    status = response.status
    conn.close()
    return status, data


def _get_text(host, port, path, headers=None):
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.request("GET", path, headers=headers or {})
    response = conn.getresponse()
    data = response.read().decode("utf-8")
    status = response.status
    conn.close()
    return status, data


def test_record_call_and_query_logs(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)

    assert analytics.record_call({
        "request_id": "req-1",
        "method": "POST",
        "endpoint": "/v1/chat/completions",
        "api_type": "chat",
        "model": "gemini-3.5-flash",
        "stream": False,
        "status_code": 200,
        "response_ms": 123,
        "prompt_chars": 20,
        "response_chars": 40,
        "prompt_tokens": 5,
        "completion_tokens": 10,
        "total_tokens": 15,
        "image_count": 0,
        "tool_count": 0,
    })

    result = analytics.query_logs({"limit": "10"})

    assert result["enabled"] is True
    assert result["total"] == 1
    assert result["logs"][0]["request_id"] == "req-1"
    assert result["logs"][0]["model"] == "gemini-3.5-flash"
    assert result["logs"][0]["success"] is True
    assert result["logs"][0]["response_ms"] == 123


def test_usage_stats_groups_by_day_model_and_endpoint(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    analytics.record_call({
        "request_id": "ok",
        "endpoint": "/v1/chat/completions",
        "api_type": "chat",
        "model": "gemini-3.5-flash",
        "status_code": 200,
        "response_ms": 100,
        "total_tokens": 12,
    })
    analytics.record_call({
        "request_id": "fail",
        "endpoint": "/v1/responses",
        "api_type": "responses",
        "model": "gemini-3.5-flash",
        "status_code": 502,
        "success": False,
        "response_ms": 300,
        "error_type": "upstream_error",
        "total_tokens": 0,
    })

    stats = analytics.usage_stats({"days": "1"})

    assert stats["summary"]["total_calls"] == 2
    assert stats["summary"]["success_calls"] == 1
    assert stats["summary"]["error_calls"] == 1
    assert stats["summary"]["avg_response_ms"] == 200
    assert stats["summary"]["total_tokens"] == 12
    assert stats["by_day"][0]["calls"] == 2
    assert stats["by_model"][0]["model"] == "gemini-3.5-flash"
    assert {item["endpoint"] for item in stats["by_endpoint"]} == {
        "/v1/chat/completions",
        "/v1/responses",
    }


def test_analytics_disabled_does_not_record(monkeypatch, tmp_path):
    db_path = tmp_path / "disabled.sqlite3"
    monkeypatch.setitem(CONFIG, "analytics_enabled", False)
    monkeypatch.setitem(CONFIG, "analytics_db_path", str(db_path))

    assert analytics.record_call({"request_id": "skip"}) is False
    assert analytics.query_logs({})["enabled"] is False
    assert not db_path.exists()


def test_chat_completion_writes_usage_log_and_stats(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    monkeypatch.setitem(CONFIG, "api_keys", [])
    monkeypatch.setattr("gemini_web2api.server.generate", lambda *args, **kwargs: "mock reply")

    server = ThreadedServer(("127.0.0.1", 0), GeminiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        body = json.dumps({
            "model": "gemini-3.5-flash",
            "messages": [{"role": "user", "content": "hello"}],
        }).encode()
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/v1/chat/completions", body=body, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        assert response.status == 200
        response.read()
        conn.close()

        for _ in range(20):
            stats_status, stats = _get_json(host, port, "/v1/usage/stats?days=1")
            logs_status, logs = _get_json(host, port, "/v1/usage/logs?limit=1")
            if stats["summary"]["total_calls"] == 1 and logs["total"] == 1:
                break
            time.sleep(0.05)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert stats_status == 200
    assert stats["summary"]["total_calls"] == 1
    assert stats["by_day"][0]["calls"] == 1
    assert stats["by_model"][0]["model"] == "gemini-3.5-flash"
    assert logs_status == 200
    assert logs["total"] == 1
    assert logs["logs"][0]["endpoint"] == "/v1/chat/completions"
    assert logs["logs"][0]["response_chars"] == len("mock reply")


def test_dashboard_page_is_served_without_api_key(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    monkeypatch.setitem(CONFIG, "api_keys", ["secret"])

    server = ThreadedServer(("127.0.0.1", 0), GeminiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        status, html = _get_text(host, port, "/dashboard")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert status == 200
    assert "gemini-web2api 调用看板" in html
    assert "/v1/usage/stats" in html
    assert "/v1/usage/logs" in html


def test_usage_api_still_requires_configured_api_key(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    monkeypatch.setitem(CONFIG, "api_keys", ["secret"])

    server = ThreadedServer(("127.0.0.1", 0), GeminiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        no_key_status, _ = _get_text(host, port, "/v1/usage/stats?days=1")
        ok_status, data = _get_json_with_headers(host, port, "/v1/usage/stats?days=1", {"Authorization": "Bearer secret"})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert no_key_status == 401
    assert ok_status == 200
    assert data["enabled"] is True


def _get_json_with_headers(host, port, path, headers):
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.request("GET", path, headers=headers)
    response = conn.getresponse()
    data = json.loads(response.read())
    status = response.status
    conn.close()
    return status, data
