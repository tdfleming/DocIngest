"""Explicit async log writer for application events.

Writes structured log entries to the `app_logs` MongoDB collection.
Called explicitly at key points — not hooked into structlog.
"""

from datetime import UTC, datetime
from typing import Any

from docingest.db.mongodb import get_db


async def log_event(
    level: str,
    event: str,
    component: str,
    *,
    trace_id: str = "",
    doc_id: str = "",
    tenant_id: str = "",
    user_id: str = "",
    details: dict[str, Any] | None = None,
    error: str = "",
) -> None:
    """Write a structured log entry to app_logs collection."""
    db = await get_db()
    entry: dict[str, Any] = {
        "level": level,
        "event": event,
        "component": component,
        "created_at": datetime.now(UTC),
    }
    if trace_id:
        entry["trace_id"] = trace_id
    if doc_id:
        entry["doc_id"] = doc_id
    if tenant_id:
        entry["tenant_id"] = tenant_id
    if user_id:
        entry["user_id"] = user_id
    if details:
        entry["details"] = details
    if error:
        entry["error"] = error

    await db.app_logs.insert_one(entry)
