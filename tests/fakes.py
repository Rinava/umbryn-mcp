"""Test doubles.

The fast suite injects :class:`FakeEngine` so it exercises the *orchestration*
(fail-closed, round-trip, overlap resolution) rather than any real detector. The
detection quality of the real engines is measured separately by the eval harness.
"""

from __future__ import annotations

from phi_mcp.types import Entity


class FakeEngine:
    """A detection engine that returns exactly what it's told, or raises.

    Args:
        entities: entities to return from :meth:`detect`.
        exc: if set, :meth:`detect` raises it (to drive the error path).
    """

    name = "fake"

    def __init__(self, entities: list[Entity] | None = None, exc: Exception | None = None) -> None:
        self._entities = list(entities or [])
        self._exc = exc

    def detect(self, text: str) -> list[Entity]:
        if self._exc is not None:
            raise self._exc
        return list(self._entities)


def make_entities(text: str, *specs: tuple[str, int, int, float]) -> list[Entity]:
    """Build entities for ``text`` from ``(entity_type, start, end, score)`` tuples."""
    return [
        Entity(entity_type=t, start=s, end=e, score=score, text=text[s:e])
        for (t, s, e, score) in specs
    ]
