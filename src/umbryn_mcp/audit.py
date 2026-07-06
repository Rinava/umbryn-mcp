"""Structured audit logging for the redaction boundary.

Emits one structured record per ``redact`` call — what *types* were redacted, or
why a call was blocked — and **never the raw values**. That makes the log safe to
ship to ordinary observability tooling: it answers "how much PHI is this boundary
catching, and how often is it blocking?" without itself becoming a place PHI can
leak.

The :class:`~umbryn_mcp.redactor.Redactor` takes an :data:`AuditSink` (a plain
callable), so the core stays free of logging specifics and tests can capture
records with a list. :func:`logging_sink` adapts Python's ``logging`` into that
shape, emitting one compact JSON line per record.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

#: An audit sink receives an event name and a JSON-serializable field mapping.
#: It must never raise into the caller — the Redactor guards the call — and must
#: never be handed raw detected values.
AuditSink = Callable[[str, "dict[str, object]"], None]

#: Name of the logger :func:`logging_sink` writes to by default.
AUDIT_LOGGER = "umbryn_mcp.audit"


def logging_sink(logger: logging.Logger | None = None) -> AuditSink:
    """Return an :data:`AuditSink` that emits each record as a compact JSON line
    at ``INFO`` on the ``umbryn_mcp.audit`` logger."""
    log = logger or logging.getLogger(AUDIT_LOGGER)

    def sink(event: str, fields: dict[str, object]) -> None:
        log.info(json.dumps({"event": event, **fields}, sort_keys=True, default=str))

    return sink
