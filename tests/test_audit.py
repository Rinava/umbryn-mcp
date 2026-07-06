"""Structured audit logging: counts and reasons are recorded; values never are."""

from __future__ import annotations

import json
import logging

import pytest

from tests.fakes import FakeEngine, make_entities
from umbryn_mcp.audit import logging_sink
from umbryn_mcp.errors import DetectionError, LowConfidenceError
from umbryn_mcp.redactor import Redactor


class _Capture:
    """An audit sink that records every (event, fields) it receives."""

    def __init__(self) -> None:
        self.records: list[tuple[str, dict[str, object]]] = []

    def __call__(self, event: str, fields: dict[str, object]) -> None:
        self.records.append((event, fields))


def test_successful_redaction_is_audited_with_counts() -> None:
    text = "a@b.co and c@d.io"
    engine = FakeEngine(
        make_entities(text, ("EMAIL_ADDRESS", 0, 4, 0.9), ("EMAIL_ADDRESS", 9, 13, 0.9))
    )
    sink = _Capture()
    Redactor(engine, audit=sink).redact(text)

    assert len(sink.records) == 1
    event, fields = sink.records[0]
    assert event == "redact"
    assert fields["entity_counts"] == {"EMAIL_ADDRESS": 2}
    assert fields["total"] == 2
    assert fields["input_chars"] == len(text)


def test_low_confidence_block_is_audited() -> None:
    text = "ssn 078051120"
    engine = FakeEngine(make_entities(text, ("US_SSN", 4, 13, 0.4)))  # above floor, below trust
    sink = _Capture()
    with pytest.raises(LowConfidenceError):
        Redactor(engine, audit=sink).redact(text)

    event, fields = sink.records[0]
    assert event == "redact_blocked"
    assert fields["reason"] == "LOW_CONFIDENCE"
    assert fields["entity_counts"] == {"US_SSN": 1}


def test_detection_error_block_is_audited() -> None:
    sink = _Capture()
    redactor = Redactor(FakeEngine(exc=RuntimeError("boom")), audit=sink)
    with pytest.raises(DetectionError):
        redactor.redact("anything")
    assert sink.records[0] == ("redact_blocked", {"reason": "DETECTION_ERROR"})


def test_audit_records_never_contain_raw_values() -> None:
    text = "email secret@hospital.org"
    engine = FakeEngine(make_entities(text, ("EMAIL_ADDRESS", 6, 25, 0.9)))
    sink = _Capture()
    Redactor(engine, audit=sink).redact(text)
    blob = json.dumps(sink.records, default=str)
    assert "secret@hospital.org" not in blob
    assert "secret" not in blob


def test_no_sink_means_no_auditing() -> None:
    text = "a@b.co"
    engine = FakeEngine(make_entities(text, ("EMAIL_ADDRESS", 0, 4, 0.9)))
    # Just needs to not raise with audit unset (the default).
    result = Redactor(engine).redact(text)
    assert "[EMAIL_ADDRESS_1]" in result.redacted_text


def test_failing_sink_does_not_break_redaction(caplog: pytest.LogCaptureFixture) -> None:
    text = "a@b.co"
    engine = FakeEngine(make_entities(text, ("EMAIL_ADDRESS", 0, 4, 0.9)))

    def boom(event: str, fields: dict[str, object]) -> None:
        raise RuntimeError("sink is broken")

    with caplog.at_level(logging.WARNING, logger="umbryn_mcp"):
        result = Redactor(engine, audit=boom).redact(text)
    assert "[EMAIL_ADDRESS_1]" in result.redacted_text  # redaction still succeeded
    assert any("audit sink raised" in r.message for r in caplog.records)


def test_logging_sink_emits_json_line(caplog: pytest.LogCaptureFixture) -> None:
    sink = logging_sink()
    with caplog.at_level(logging.INFO, logger="umbryn_mcp.audit"):
        sink("redact", {"total": 3, "entity_counts": {"NPI": 3}})
    (record,) = caplog.records
    payload = json.loads(record.message)
    assert payload == {"event": "redact", "total": 3, "entity_counts": {"NPI": 3}}
