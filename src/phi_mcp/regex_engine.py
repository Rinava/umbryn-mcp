"""The default detection engine: pure regex + checksums, zero heavy deps.

This engine installs and runs anywhere Python does — no spaCy, no model
download, no network, ever. It covers pattern-based PII (email, phone, SSN,
credit card, IP, URL) and the checksum/structure-based clinical identifiers
(NPI, DEA, MBI, MRN, CLIA).

What it deliberately does *not* do is name and address (``PERSON``/``LOCATION``)
detection, which needs statistical NER — install the optional Presidio engine
(``pip install "phi-redact-mcp[presidio]"``) for that. Keeping the default engine
dependency-free is what makes the "runs fully inside your infrastructure, no
egress" guarantee trivial to audit.
"""

from __future__ import annotations

import re

from phi_mcp.recognizers import (
    CONTEXT_BOOST,
    CONTEXT_FLOOR,
    CONTEXT_WINDOW_AFTER,
    CONTEXT_WINDOW_BEFORE,
    DEFAULT_RECOGNIZERS,
    Recognizer,
)
from phi_mcp.types import Entity


class RegexEngine:
    """Deterministic regex/checksum detection engine.

    Args:
        recognizers: rule set to run; defaults to
            :data:`~phi_mcp.recognizers.DEFAULT_RECOGNIZERS`.
    """

    name = "regex"

    def __init__(self, recognizers: tuple[Recognizer, ...] = DEFAULT_RECOGNIZERS) -> None:
        self._recognizers = recognizers
        # Compile once; recognizers are immutable so this is safe to cache.
        self._compiled = [(rec, re.compile(rec.regex, rec.flags)) for rec in recognizers]

    def detect(self, text: str) -> list[Entity]:
        entities: list[Entity] = []
        for rec, pattern in self._compiled:
            for match in pattern.finditer(text):
                start, end = match.span(rec.group)
                if start < 0 or start >= end:  # group didn't participate
                    continue
                value = text[start:end]

                if rec.validator is not None and not rec.validator(value):
                    continue

                score = self._score(rec, text, start, end)
                if score is None:  # context required but absent
                    continue

                entities.append(
                    Entity(
                        entity_type=rec.entity_type,
                        start=start,
                        end=end,
                        score=score,
                        text=value,
                    )
                )
        return entities

    @staticmethod
    def _score(rec: Recognizer, text: str, start: int, end: int) -> float | None:
        """Return the context-adjusted score, or ``None`` to drop the match."""
        if not rec.context:
            return min(rec.base_score, 1.0)

        window = text[max(0, start - CONTEXT_WINDOW_BEFORE) : end + CONTEXT_WINDOW_AFTER].lower()
        has_context = any(word in window for word in rec.context)

        if not has_context:
            return None if rec.context_required else min(rec.base_score, 1.0)

        boosted = max(rec.base_score + CONTEXT_BOOST, CONTEXT_FLOOR)
        return min(boosted, 1.0)
