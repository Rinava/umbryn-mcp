"""Fail-closed behaviour — written first, before any happy path.

The whole thesis of this project is here: when detection is uncertain or errors,
the boundary blocks rather than leaking data. Every test asserts *both* that the
right typed error is raised *and* that no redacted text is produced.
"""

from __future__ import annotations

import pytest

from tests.fakes import FakeEngine, make_entities
from umbryn_mcp import DetectionError, LowConfidenceError, Redactor
from umbryn_mcp.types import Entity

TEXT = "call me at 555-0100 about record 1234567"


def test_engine_error_blocks_with_typed_error() -> None:
    redactor = Redactor(FakeEngine(exc=RuntimeError("model exploded")))
    with pytest.raises(DetectionError) as excinfo:
        redactor.redact(TEXT)
    assert excinfo.value.code == "DETECTION_ERROR"
    # The typed code survives stringification (this is what an MCP client sees).
    assert "[DETECTION_ERROR]" in str(excinfo.value)


def test_low_confidence_detection_blocks() -> None:
    # A single entity in the uncertain band [floor, min_confidence) must block.
    entities = make_entities(TEXT, ("US_SSN", 32, 39, 0.45))
    redactor = Redactor(FakeEngine(entities), detection_floor=0.35, min_confidence=0.5)
    with pytest.raises(LowConfidenceError) as excinfo:
        redactor.redact(TEXT)
    assert excinfo.value.code == "LOW_CONFIDENCE"


def test_uncertainty_blocks_the_whole_call_not_just_the_weak_span() -> None:
    # One confident span + one uncertain span: the sharp rule is that we do NOT
    # redact-what-we-can and pass the rest — the entire call blocks.
    entities = make_entities(
        TEXT,
        ("PHONE_NUMBER", 11, 19, 0.95),  # confident
        ("US_SSN", 32, 39, 0.40),  # uncertain
    )
    redactor = Redactor(FakeEngine(entities), detection_floor=0.35, min_confidence=0.5)
    with pytest.raises(LowConfidenceError):
        redactor.redact(TEXT)


def test_out_of_range_span_blocks() -> None:
    bad = [Entity("US_SSN", 0, len(TEXT) + 10, 0.99, "x")]
    redactor = Redactor(FakeEngine(bad))
    with pytest.raises(DetectionError):
        redactor.redact(TEXT)


def test_non_entity_result_blocks() -> None:
    class NotAnEntity:
        start, end, score = 0, 3, 0.9

    redactor = Redactor(FakeEngine([NotAnEntity()]))  # type: ignore[list-item]
    with pytest.raises(DetectionError):
        redactor.redact(TEXT)


def test_uncertain_span_overlapping_a_confident_span_still_blocks() -> None:
    # Regression for a fail-closed bypass: overlap resolution must not run before
    # the confidence gate, or an uncertain span that overlaps a confident one gets
    # dropped and its non-overlapping bytes leak in cleartext.
    text = "Patient SSN 123-45-6789 phone"
    entities = make_entities(
        text,
        ("PHONE_NUMBER", 8, 18, 0.90),  # confident, overlaps the SSN
        ("US_SSN", 12, 23, 0.40),  # uncertain; overlap res would drop it
    )
    redactor = Redactor(FakeEngine(entities), detection_floor=0.35, min_confidence=0.5)
    with pytest.raises(LowConfidenceError):
        redactor.redact(text)


def test_detect_surfaces_overlapped_uncertain_candidate() -> None:
    # detect must report the full candidate set, including a lower-scored span
    # nested in / overlapping a higher-scored one.
    text = "Patient SSN 123-45-6789 phone"
    entities = make_entities(text, ("PHONE_NUMBER", 8, 18, 0.90), ("US_SSN", 12, 23, 0.40))
    redactor = Redactor(FakeEngine(entities), detection_floor=0.35, min_confidence=0.5)
    result = redactor.detect(text)
    assert sorted(e.entity_type for e in result.entities) == ["PHONE_NUMBER", "US_SSN"]


def test_detect_does_not_block_on_low_confidence() -> None:
    # detect is for inspection: it must SURFACE uncertain hits, never block.
    entities = make_entities(TEXT, ("US_SSN", 32, 39, 0.40))
    redactor = Redactor(FakeEngine(entities), detection_floor=0.35, min_confidence=0.5)
    result = redactor.detect(TEXT)
    assert [e.entity_type for e in result.entities] == ["US_SSN"]
    assert result.entities[0].score == pytest.approx(0.40)


def test_engine_error_also_blocks_detect() -> None:
    redactor = Redactor(FakeEngine(exc=ValueError("boom")))
    with pytest.raises(DetectionError):
        redactor.detect(TEXT)
