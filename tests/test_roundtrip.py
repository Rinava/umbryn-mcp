"""Round-trip guarantee — property-based.

The core promise: for *any* input, ``restore(redact(text)) == text``. Hypothesis
generates arbitrary text and arbitrary (possibly overlapping, possibly
placeholder-colliding) spans and tries to break it. This property is what drove
the collision-proof placeholder design.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from phi_mcp import Redactor
from phi_mcp.types import Entity
from tests.fakes import FakeEngine, make_entities


def _redactor(entities: list[Entity]) -> Redactor:
    # High scores so nothing blocks; low floor so nothing is dropped as noise.
    return Redactor(FakeEngine(entities), min_confidence=0.5, detection_floor=0.1)


@given(text=st.text(), data=st.data())
def test_redact_restore_is_identity(text: str, data: st.DataObject) -> None:
    n = len(text)
    raw_spans = data.draw(st.lists(st.tuples(st.integers(0, n), st.integers(0, n)), max_size=6))
    entities: list[Entity] = []
    for i, (a, b) in enumerate(raw_spans):
        start, end = min(a, b), max(a, b)
        if start == end:
            continue
        entities.append(Entity(f"TYPE{i % 3}", start, end, 0.99, text[start:end]))

    redactor = _redactor(entities)
    result = redactor.redact(text)
    assert redactor.restore(result.redacted_text, result.token_map) == text


@given(text=st.text())
def test_no_phi_passthrough_roundtrips(text: str) -> None:
    redactor = Redactor(FakeEngine([]))
    result = redactor.redact(text)
    assert result.redacted_text == text
    assert result.token_map == {}
    assert redactor.restore(result.redacted_text, result.token_map) == text


@given(filler=st.text(alphabet="ab[]_PERSON0123 ", max_size=40))
def test_roundtrips_even_when_text_contains_placeholder_lookalikes(filler: str) -> None:
    # Text that already contains strings like "[PERSON_1]" must still round-trip:
    # the allocator has to pick a placeholder that doesn't collide.
    text = f"{filler} [PERSON_1] Jane Doe [PERSON_1]"
    start = text.index("Jane Doe")
    entities = make_entities(text, ("PERSON", start, start + len("Jane Doe"), 0.99))
    redactor = Redactor(FakeEngine(entities), detection_floor=0.1)
    result = redactor.redact(text)
    # The chosen placeholder must not have collided with the pre-existing token.
    assert redactor.restore(result.redacted_text, result.token_map) == text
