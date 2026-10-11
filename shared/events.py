from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

TOPICS = ("orders", "payments", "notifications")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"event_id": str(uuid4()), "event_type": event_type, "occurred_at": utc_now(), "payload": payload}
