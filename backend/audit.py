"""Structured security audit events that deliberately exclude SQL and credentials."""

import hashlib
import json
import logging

logger = logging.getLogger("sqlrefine.audit")


def opaque_fingerprint(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def audit(event: str, *, session_id: str | None = None, outcome: str = "success", **details) -> None:
    safe_details = {
        key: value for key, value in details.items()
        if key.lower() not in {"password", "query", "sql", "connection_string", "ssl_ca"}
    }
    logger.info(json.dumps({
        "event": event,
        "outcome": outcome,
        "session": opaque_fingerprint(session_id),
        **safe_details,
    }, separators=(",", ":"), default=str))

