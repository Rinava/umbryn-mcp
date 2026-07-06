"""The default detection engine: pure regex + checksums, zero heavy deps.

This engine installs and runs anywhere Python does — no spaCy, no model
download, no network, ever. It covers pattern-based PII (email, phone, SSN,
credit card, IP, URL) and the checksum/structure-based clinical identifiers
(NPI, DEA, MBI, MRN, CLIA).

What it deliberately does *not* do is name and address (``PERSON``/``LOCATION``)
detection, which needs statistical NER — install the optional Presidio engine
(``pip install "umbryn-mcp[presidio]"``) for that. Keeping the default engine
dependency-free is what makes the "runs fully inside your infrastructure, no
egress" guarantee trivial to audit.
"""

from __future__ import annotations

import re

from umbryn_mcp.recognizers import (
    CONTEXT_BOOST,
    CONTEXT_FLOOR,
    CONTEXT_WINDOW_AFTER,
    CONTEXT_WINDOW_BEFORE,
    DEFAULT_RECOGNIZERS,
    Recognizer,
)
from umbryn_mcp.types import Entity


class RegexEngine:
    """Deterministic regex/checksum detection engine.

    Args:
        recognizers: rule set to run; defaults to
            :data:`~umbryn_mcp.recognizers.DEFAULT_RECOGNIZERS`.
    """

    name = "regex"

    def __init__(self, recognizers: tuple[Recognizer, ...] = DEFAULT_RECOGNIZERS) -> None:
        # Compile once; recognizers are immutable so this is safe to cache. Each
        # entry also carries a compiled context matcher (or None) so context words
        # match on word boundaries — "lab" must not fire inside "collaborate".
        self._compiled = [
            (rec, re.compile(rec.regex, rec.flags), self._context_matcher(rec))
            for rec in recognizers
        ]

    @staticmethod
    def _context_matcher(rec: Recognizer) -> re.Pattern[str] | None:
        if not rec.context:
            return None
        alternation = "|".join(re.escape(word) for word in rec.context)
        return re.compile(rf"\b(?:{alternation})\b", re.IGNORECASE)

    def detect(self, text: str) -> list[Entity]:
        entities: list[Entity] = []
        for rec, pattern, context in self._compiled:
            for match in pattern.finditer(text):
                start, end = match.span(rec.group)
                if start < 0 or start >= end:  # group didn't participate
                    continue
                value = text[start:end]

                if rec.validator is not None and not rec.validator(value):
                    continue

                score = self._score(rec, context, text, start, end)
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
    def _score(
        rec: Recognizer, context: re.Pattern[str] | None, text: str, start: int, end: int
    ) -> float | None:
        """Return the context-adjusted score, or ``None`` to drop the match."""
        if context is None:
            return min(rec.base_score, 1.0)

        window = text[max(0, start - CONTEXT_WINDOW_BEFORE) : end + CONTEXT_WINDOW_AFTER]
        has_context = context.search(window) is not None

        if not has_context:
            return None if rec.context_required else min(rec.base_score, 1.0)

        boosted = max(rec.base_score + CONTEXT_BOOST, CONTEXT_FLOOR)
        return min(boosted, 1.0)
