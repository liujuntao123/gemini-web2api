"""Persistent API call logging and aggregate usage statistics."""
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .config import CONFIG

_INIT_LOCK = threading.Lock()
_INITIALIZED_PATHS = set()
_REQUIRED_COLUMNS = {
    "upstream_mode": "TEXT",
    "upstream_cookie": "INTEGER",
    "file_ref_count": "INTEGER",
}


def analytics_enabled() -> bool:
    """Return whether persistent usage analytics are enabled."""
    return bool(CONFIG.get("analytics_enabled", True))


def analytics_db_path() -> str:
    return str(CONFIG.get("analytics_db_path") or "gemini_web2api_usage.sqlite3")


def _utc_now() -> Tuple[str, float]:
    now = datetime.now(timezone.utc)
    return now.isoformat().replace("+00:00", "Z"), now.timestamp()


def _connect() -> sqlite3.Connection:
    path = analytics_db_path()
    if path != ":memory:":
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the analytics database schema if needed."""
    if not analytics_enabled():
        return
    path = analytics_db_path()
    if path in _INITIALIZED_PATHS:
        with _connect() as conn:
            if _table_exists(conn, "api_call_logs"):
                _ensure_columns(conn, "api_call_logs", _REQUIRED_COLUMNS)
                return
        _INITIALIZED_PATHS.discard(path)
    with _INIT_LOCK:
        if path in _INITIALIZED_PATHS:
            return
        with _connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_call_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_at_ts REAL NOT NULL,
                    method TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    api_type TEXT NOT NULL,
                    model TEXT,
                    stream INTEGER NOT NULL DEFAULT 0,
                    status_code INTEGER,
                    success INTEGER NOT NULL,
                    response_ms INTEGER NOT NULL,
                    request_bytes INTEGER,
                    prompt_chars INTEGER,
                    response_chars INTEGER,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    image_count INTEGER,
                    tool_count INTEGER,
                    upstream_mode TEXT,
                    upstream_cookie INTEGER,
                    file_ref_count INTEGER,
                    error_type TEXT,
                    error_message TEXT,
                    client_host TEXT,
                    user_agent TEXT
                )
                """
            )
            _ensure_columns(conn, "api_call_logs", _REQUIRED_COLUMNS)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_call_logs_created ON api_call_logs(created_at_ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_call_logs_model ON api_call_logs(model)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_call_logs_endpoint ON api_call_logs(endpoint)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_call_logs_success ON api_call_logs(success)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_call_logs_upstream_mode ON api_call_logs(upstream_mode)")
        _INITIALIZED_PATHS.add(path)


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: Dict[str, str]) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, ddl_type in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return bool(row)


def _truncate(value: Any, max_len: int = 500) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def record_call(data: Dict[str, Any]) -> bool:
    """Persist one API call metadata record.

    Analytics must never break normal request handling, so callers can ignore a
    false return value.
    """
    if not analytics_enabled():
        return False
    try:
        init_db()
        created_at, created_at_ts = _utc_now()
        status_code = data.get("status_code")
        if data.get("success") is None:
            success = bool(status_code is not None and 200 <= int(status_code) < 400)
        else:
            success = bool(data.get("success"))
        upstream_cookie = data.get("upstream_cookie")
        if upstream_cookie is None:
            upstream_mode = data.get("upstream_mode")
        else:
            upstream_mode = "cookie" if upstream_cookie else "anonymous"
        row = {
            "request_id": str(data.get("request_id") or ""),
            "created_at": created_at,
            "created_at_ts": created_at_ts,
            "method": str(data.get("method") or "POST"),
            "endpoint": str(data.get("endpoint") or ""),
            "api_type": str(data.get("api_type") or "unknown"),
            "model": _truncate(data.get("model"), 120),
            "stream": 1 if data.get("stream") else 0,
            "status_code": status_code,
            "success": 1 if success else 0,
            "response_ms": int(data.get("response_ms") or 0),
            "request_bytes": data.get("request_bytes"),
            "prompt_chars": data.get("prompt_chars"),
            "response_chars": data.get("response_chars"),
            "prompt_tokens": data.get("prompt_tokens"),
            "completion_tokens": data.get("completion_tokens"),
            "total_tokens": data.get("total_tokens"),
            "image_count": data.get("image_count"),
            "tool_count": data.get("tool_count"),
            "upstream_mode": _truncate(upstream_mode, 40),
            "upstream_cookie": None if upstream_cookie is None else (1 if upstream_cookie else 0),
            "file_ref_count": data.get("file_ref_count"),
            "error_type": _truncate(data.get("error_type"), 120),
            "error_message": _truncate(data.get("error_message"), 500),
            "client_host": _truncate(data.get("client_host"), 120),
            "user_agent": _truncate(data.get("user_agent"), 300),
        }
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO api_call_logs (
                    request_id, created_at, created_at_ts, method, endpoint, api_type,
                    model, stream, status_code, success, response_ms, request_bytes,
                    prompt_chars, response_chars, prompt_tokens, completion_tokens,
                    total_tokens, image_count, tool_count, upstream_mode, upstream_cookie,
                    file_ref_count, error_type, error_message,
                    client_host, user_agent
                ) VALUES (
                    :request_id, :created_at, :created_at_ts, :method, :endpoint, :api_type,
                    :model, :stream, :status_code, :success, :response_ms, :request_bytes,
                    :prompt_chars, :response_chars, :prompt_tokens, :completion_tokens,
                    :total_tokens, :image_count, :tool_count, :upstream_mode, :upstream_cookie,
                    :file_ref_count, :error_type, :error_message,
                    :client_host, :user_agent
                )
                """,
                row,
            )
        return True
    except Exception:
        return False


def _parse_positive_int(value: Any, default: int, max_value: int = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if parsed < 1:
        parsed = default
    if max_value is not None:
        parsed = min(parsed, max_value)
    return parsed


def _parse_nonnegative_int(value: Any, default: int, max_value: int = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if parsed < 0:
        parsed = default
    if max_value is not None:
        parsed = min(parsed, max_value)
    return parsed


def _parse_time(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        pass
    try:
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            text = text + "T00:00:00+00:00"
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def _query_filters(params: Dict[str, Any]) -> Tuple[str, List[Any]]:
    clauses = []
    args = []
    from_ts = _parse_time(params.get("from") or params.get("start"))
    to_ts = _parse_time(params.get("to") or params.get("end"))
    if from_ts is not None:
        clauses.append("created_at_ts >= ?")
        args.append(from_ts)
    if to_ts is not None:
        clauses.append("created_at_ts <= ?")
        args.append(to_ts)
    for key in ("model", "endpoint", "api_type", "upstream_mode"):
        if params.get(key):
            clauses.append(f"{key} = ?")
            args.append(str(params[key]))
    if params.get("success") not in (None, ""):
        clauses.append("success = ?")
        args.append(1 if str(params["success"]).lower() in ("1", "true", "yes") else 0)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return where, args


def query_logs(params: Dict[str, Any]) -> Dict[str, Any]:
    """Return paginated API call logs."""
    if not analytics_enabled():
        return {"enabled": False, "logs": [], "limit": 0, "offset": 0, "total": 0}
    init_db()
    limit = _parse_positive_int(params.get("limit"), 100, 1000)
    offset = _parse_nonnegative_int(params.get("offset"), 0)
    where, args = _query_filters(params)
    with _connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM api_call_logs{where}", args).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, request_id, created_at, method, endpoint, api_type, model, stream,
                   status_code, success, response_ms, request_bytes, prompt_chars,
                   response_chars, prompt_tokens, completion_tokens, total_tokens,
                   image_count, tool_count, upstream_mode, upstream_cookie, file_ref_count,
                   error_type, error_message, client_host, user_agent
            FROM api_call_logs
            {where}
            ORDER BY created_at_ts DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            args + [limit, offset],
        ).fetchall()
    logs = []
    for row in rows:
        item = dict(row)
        item["stream"] = bool(item["stream"])
        item["success"] = bool(item["success"])
        if item.get("upstream_cookie") is not None:
            item["upstream_cookie"] = bool(item["upstream_cookie"])
        logs.append(item)
    return {"enabled": True, "logs": logs, "limit": limit, "offset": offset, "total": total}


def usage_stats(params: Dict[str, Any]) -> Dict[str, Any]:
    """Return aggregate usage statistics for recent API calls."""
    if not analytics_enabled():
        return {"enabled": False, "summary": {}, "by_day": [], "by_model": [], "by_endpoint": [], "by_upstream_mode": []}
    init_db()
    days = _parse_positive_int(params.get("days"), 1, 366)
    since_ts = time_window_start(days)
    where, args = _query_filters({**params, "from": params.get("from") or since_ts})
    with _connect() as conn:
        summary = dict(
            conn.execute(
                f"""
                SELECT COUNT(*) AS total_calls,
                       COALESCE(SUM(success), 0) AS success_calls,
                       COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0) AS error_calls,
                       COALESCE(ROUND(AVG(response_ms), 2), 0) AS avg_response_ms,
                       COALESCE(SUM(total_tokens), 0) AS total_tokens,
                       COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                       COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                       COALESCE(SUM(CASE WHEN upstream_mode = 'cookie' THEN 1 ELSE 0 END), 0) AS cookie_calls,
                       COALESCE(SUM(CASE WHEN upstream_mode = 'anonymous' THEN 1 ELSE 0 END), 0) AS anonymous_calls,
                       COALESCE(SUM(CASE WHEN COALESCE(file_ref_count, 0) > 0 THEN 1 ELSE 0 END), 0) AS file_ref_calls,
                       COALESCE(SUM(file_ref_count), 0) AS total_file_refs
                FROM api_call_logs
                {where}
                """,
                args,
            ).fetchone()
        )
        by_day = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT substr(created_at, 1, 10) AS date,
                       COUNT(*) AS calls,
                       COALESCE(SUM(success), 0) AS success_calls,
                       COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0) AS error_calls,
                       COALESCE(ROUND(AVG(response_ms), 2), 0) AS avg_response_ms,
                       COALESCE(SUM(total_tokens), 0) AS total_tokens
                FROM api_call_logs
                {where}
                GROUP BY substr(created_at, 1, 10)
                ORDER BY date
                """,
                args,
            ).fetchall()
        ]
        by_model = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT COALESCE(model, 'unknown') AS model,
                       COUNT(*) AS calls,
                       COALESCE(SUM(success), 0) AS success_calls,
                       COALESCE(SUM(total_tokens), 0) AS total_tokens,
                       COALESCE(ROUND(AVG(response_ms), 2), 0) AS avg_response_ms
                FROM api_call_logs
                {where}
                GROUP BY COALESCE(model, 'unknown')
                ORDER BY calls DESC, model
                """,
                args,
            ).fetchall()
        ]
        by_endpoint = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT endpoint,
                       COUNT(*) AS calls,
                       COALESCE(SUM(success), 0) AS success_calls,
                       COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0) AS error_calls,
                       COALESCE(ROUND(AVG(response_ms), 2), 0) AS avg_response_ms
                FROM api_call_logs
                {where}
                GROUP BY endpoint
                ORDER BY calls DESC, endpoint
                """,
                args,
            ).fetchall()
        ]
        by_upstream_mode = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT COALESCE(upstream_mode, 'not_sent') AS upstream_mode,
                       COUNT(*) AS calls,
                       COALESCE(SUM(success), 0) AS success_calls,
                       COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0) AS error_calls,
                       COALESCE(SUM(file_ref_count), 0) AS file_refs,
                       COALESCE(ROUND(AVG(response_ms), 2), 0) AS avg_response_ms
                FROM api_call_logs
                {where}
                GROUP BY COALESCE(upstream_mode, 'not_sent')
                ORDER BY calls DESC, upstream_mode
                """,
                args,
            ).fetchall()
        ]
    return {
        "enabled": True,
        "days": days,
        "summary": summary,
        "by_day": by_day,
        "by_model": by_model,
        "by_endpoint": by_endpoint,
        "by_upstream_mode": by_upstream_mode,
    }


def time_window_start(days: int) -> float:
    return datetime.now(timezone.utc).timestamp() - (days * 86400)
