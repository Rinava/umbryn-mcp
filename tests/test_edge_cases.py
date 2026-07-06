"""Edge and error cases: empty input, overlaps, size limits, malformed input."""

from __future__ import annotations

import pytest

from tests.fakes import FakeEngine, make_entities
from umbryn_mcp import (
    InputTooLargeError,
    InvalidInputError,
    Redactor,
    RestoreError,
)
from umbryn_mcp.types import Entity


def test_empty_string_roundtrips() -> None:
    redactor = Redactor(FakeEngine([]))
    result = redactor.redact("")
    assert result.redacted_text == ""
    assert result.token_map == {}
    assert redactor.restore("", {}) == ""


def test_no_phi_returns_input_unchanged() -> None:
    redactor = Redactor(FakeEngine([]))
    result = redactor.redact("nothing to see here")
    assert result.redacted_text == "nothing to see here"
    assert result.entities == ()


def test_repeated_value_reuses_one_placeholder() -> None:
    text = "Smith paged Smith"
    entities = make_entities(text, ("PERSON", 0, 5, 0.9), ("PERSON", 12, 17, 0.9))
    result = Redactor(FakeEngine(entities), detection_floor=0.1).redact(text)
    assert len(result.token_map) == 1
    assert result.redacted_text == "[PERSON_1] paged [PERSON_1]"


def test_overlapping_detections_are_deterministic() -> None:
    text = "123 Main Street, Springfield"
    # A LOCATION spanning the whole address, with a nested "Springfield".
    overlap = make_entities(text, ("LOCATION", 0, 28, 0.8), ("LOCATION", 17, 28, 0.9))
    # Feed the two spans in both orders; output must be identical.
    a = Redactor(FakeEngine(overlap), detection_floor=0.1).redact(text)
    b = Redactor(FakeEngine(list(reversed(overlap))), detection_floor=0.1).redact(text)
    assert a.redacted_text == b.redacted_text
    # Higher score / longer span wins deterministically; exactly one span kept.
    assert len(a.token_map) == 1


def test_nested_detection_keeps_higher_priority_span() -> None:
    text = "Dr. Jane Doe"
    entities = make_entities(text, ("PERSON", 4, 12, 0.95), ("PERSON", 4, 8, 0.6))
    result = Redactor(FakeEngine(entities), detection_floor=0.1).redact(text)
    assert result.redacted_text == "Dr. [PERSON_1]"
    assert result.token_map["[PERSON_1]"] == "Jane Doe"


def test_partial_overlap_redacts_union_and_leaks_no_flagged_bytes() -> None:
    # Regression for a PHI-leak: two CONFIDENT detections that PARTIALLY overlap.
    # The naive "drop the lower-priority span" resolution kept only the winner and
    # emitted the loser's non-overlapping bytes in cleartext. A greedy EMAIL match
    # abutting a CREDIT_CARD is the canonical trigger.
    text = "Charge 4111 1111 1111 1111-receipts@store.io now"
    card_start = text.index("4111")
    card_end = text.index("-receipts")  # end of the 16-digit PAN
    email_start = text.index("1111-receipts")  # greedy email absorbs the last group
    email_end = text.index(" now")
    entities = make_entities(
        text,
        ("CREDIT_CARD", card_start, card_end, 0.85),  # extends LEFT of the winner
        ("EMAIL_ADDRESS", email_start, email_end, 0.90),  # higher score, wins the label
    )
    redactor = Redactor(FakeEngine(entities), detection_floor=0.35, min_confidence=0.5)
    result = redactor.redact(text)
    # Every flagged byte is covered by the union: no fragment of the card (which
    # used to leak) or the email survives in the text sent downstream.
    for leak in ("4111", "1111", "receipts", "store.io"):
        assert leak not in result.redacted_text
    # The overlapping cluster collapses to a single reversible placeholder.
    assert len(result.token_map) == 1
    assert redactor.restore(result.redacted_text, result.token_map) == text


def test_input_over_limit_raises_typed_error() -> None:
    redactor = Redactor(FakeEngine([]), max_input_chars=10)
    with pytest.raises(InputTooLargeError) as excinfo:
        redactor.redact("x" * 11)
    assert excinfo.value.details["limit"] == 10


def test_non_string_input_raises() -> None:
    redactor = Redactor(FakeEngine([]))
    with pytest.raises(InvalidInputError):
        redactor.redact(1234)  # type: ignore[arg-type]


def test_restore_rejects_non_mapping() -> None:
    redactor = Redactor(FakeEngine([]))
    with pytest.raises(InvalidInputError):
        redactor.restore("x", ["not", "a", "dict"])  # type: ignore[arg-type]


def test_restore_rejects_non_string_values() -> None:
    redactor = Redactor(FakeEngine([]))
    with pytest.raises(RestoreError):
        redactor.restore("[X_1]", {"[X_1]": 5})  # type: ignore[dict-item]


def test_restore_is_single_pass_no_double_expansion() -> None:
    # A value that contains another placeholder must not be re-expanded.
    redactor = Redactor(FakeEngine([]))
    out = redactor.restore("[A_1]", {"[A_1]": "x[B_1]y", "[B_1]": "SECRET"})
    assert out == "x[B_1]y"


def test_restore_rejects_empty_placeholder_key() -> None:
    # An empty key would otherwise be inserted between every character.
    redactor = Redactor(FakeEngine([]))
    with pytest.raises(RestoreError):
        redactor.restore("ab", {"": "Z"})


def test_unicode_offsets_preserved() -> None:
    text = "🔒 patient José 1234567 done"
    start = text.index("José")
    entities = make_entities(text, ("PERSON", start, start + len("José"), 0.9))
    redactor = Redactor(FakeEngine(entities), detection_floor=0.1)
    result = redactor.redact(text)
    assert result.token_map["[PERSON_1]"] == "José"
    assert redactor.restore(result.redacted_text, result.token_map) == text


def test_placeholder_collision_is_avoided() -> None:
    text = "[PERSON_1] real name is Bob"
    start = text.index("Bob")
    entities = make_entities(text, ("PERSON", start, start + 3, 0.9))
    result = Redactor(FakeEngine(entities), detection_floor=0.1).redact(text)
    # "[PERSON_1]" already exists in the text, so Bob must get a different token.
    (placeholder,) = result.token_map
    assert placeholder != "[PERSON_1]"
    assert (
        Redactor(FakeEngine(entities), detection_floor=0.1).restore(
            result.redacted_text, result.token_map
        )
        == text
    )


@pytest.mark.parametrize(
    ("floor", "min_conf"),
    [(0.6, 0.5), (-0.1, 0.5), (0.3, 1.5)],
)
def test_invalid_thresholds_rejected(floor: float, min_conf: float) -> None:
    with pytest.raises(ValueError):
        Redactor(FakeEngine([]), detection_floor=floor, min_confidence=min_conf)


def test_entity_rejects_bad_span() -> None:
    with pytest.raises(ValueError):
        Entity("X", 5, 3, 0.5, "")
