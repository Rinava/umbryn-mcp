"""Plain, serialization-friendly value types shared across the core.

These are deliberately free of any MCP or Presidio dependency so the detection
core stays embeddable. The server layer maps them to its own wire models.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Entity:
    """A single detected PHI/PII span in the *original* text.

    ``start``/``end`` are Python string offsets into the original text such that
    ``text[start:end] == text`` for the matched substring. ``score`` is the
    engine's confidence in ``[0.0, 1.0]``.
    """

    entity_type: str
    start: int
    end: int
    score: float
    text: str

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid span: start={self.start} end={self.end}")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score out of range: {self.score}")


@dataclass(frozen=True, slots=True)
class DetectionResult:
    """Result of :meth:`Redactor.detect` — what was found, nothing mutated."""

    entities: tuple[Entity, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class RedactionResult:
    """Result of :meth:`Redactor.redact`.

    ``token_map`` maps each typed placeholder (e.g. ``"[MRN_1]"``) back to the
    original value it replaced. Pass it to :meth:`Redactor.restore` to recover
    the original text exactly.
    """

    redacted_text: str
    token_map: dict[str, str] = field(default_factory=dict)
    entities: tuple[Entity, ...] = field(default_factory=tuple)
