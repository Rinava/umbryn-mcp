"""The redaction core: detect, redact, restore — fail-closed by construction.

Design notes worth reading before you trust this in a pipeline:

**Two thresholds, one of which blocks.** ``detection_floor`` is the sensitivity
boundary — below it, the engine's signal is treated as noise (not a detection).
``min_confidence`` is the *trust* threshold. Every candidate that survives the
floor but scores below ``min_confidence`` lands in an *uncertain band*, and the
presence of any uncertain candidate makes :meth:`redact` fail closed. We do not
redact-what-we-can and pass the rest through; uncertainty blocks the whole call.

**Redaction is offset-based, never search-based.** Spans are cut by index, so a
value that happens to appear elsewhere in the text is never accidentally
touched.

**Placeholders are collision-proof.** Each placeholder is verified absent from
the original text and from every other placeholder, and the bracket+underscore
format is prefix-free. That makes :meth:`restore` an exact inverse of
:meth:`redact` for *arbitrary* input — a property the test suite proves with
Hypothesis.

**Overlaps merge, never drop.** Overlapping detections are grouped into
connected clusters and each cluster is redacted as one span covering the *union*
of its members, so no byte any detection flagged can survive in cleartext.
Dropping the lower-priority span instead would leak its non-overlapping bytes
whenever two confident spans partially overlap. The cluster's placeholder label
is picked by a fixed priority (higher score, then longer span, then type name,
then position), so output is stable across runs.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from umbryn_mcp.engine import DetectionEngine
from umbryn_mcp.errors import (
    DetectionError,
    InputTooLargeError,
    InvalidInputError,
    LowConfidenceError,
    RestoreError,
)
from umbryn_mcp.types import DetectionResult, Entity, RedactionResult

DEFAULT_MIN_CONFIDENCE = 0.5
DEFAULT_DETECTION_FLOOR = 0.35
DEFAULT_MAX_INPUT_CHARS = 100_000


class Redactor:
    """Orchestrates a :class:`~umbryn_mcp.engine.DetectionEngine` into a fail-closed
    redact / restore / detect boundary.

    Args:
        engine: the detection backend (Presidio in production, a fake in tests).
        min_confidence: trust threshold. Any surviving candidate below this
            blocks :meth:`redact`. Must satisfy
            ``0 <= detection_floor <= min_confidence <= 1``.
        detection_floor: sensitivity boundary. Candidates below this are treated
            as noise and ignored everywhere.
        max_input_chars: hard input-size limit; larger input is rejected with a
            typed error rather than processed slowly or partially.
        entity_thresholds: per-entity-type trust thresholds that override
            ``min_confidence`` for that type. Each must satisfy
            ``detection_floor <= threshold <= 1``.
        disabled_entities: entity types to drop entirely — never detected,
            never redacted, never surfaced by :meth:`detect`.
    """

    def __init__(
        self,
        engine: DetectionEngine,
        *,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        detection_floor: float = DEFAULT_DETECTION_FLOOR,
        max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
        entity_thresholds: Mapping[str, float] | None = None,
        disabled_entities: frozenset[str] = frozenset(),
    ) -> None:
        if not 0.0 <= detection_floor <= min_confidence <= 1.0:
            raise ValueError(
                "thresholds must satisfy 0 <= detection_floor <= min_confidence <= 1 "
                f"(got detection_floor={detection_floor}, min_confidence={min_confidence})"
            )
        if max_input_chars <= 0:
            raise ValueError("max_input_chars must be positive")
        entity_thresholds = dict(entity_thresholds or {})
        for entity_type, threshold in entity_thresholds.items():
            if not detection_floor <= threshold <= 1.0:
                raise ValueError(
                    f"entity threshold for {entity_type!r} must satisfy "
                    f"detection_floor <= threshold <= 1 (got {threshold})"
                )
        self._engine = engine
        self.min_confidence = min_confidence
        self.detection_floor = detection_floor
        self.max_input_chars = max_input_chars
        self.entity_thresholds = entity_thresholds
        self.disabled_entities = disabled_entities

    # -- public API ---------------------------------------------------------

    def detect(self, text: str) -> DetectionResult:
        """Find PHI/PII without mutating the input.

        Returns every candidate at or above ``detection_floor`` (including the
        uncertain band, and including candidates that overlap a stronger one), so
        callers can inspect coverage before trusting the boundary. Overlaps are
        NOT resolved here — surfacing every uncertain hit is the whole point.
        Unlike :meth:`redact`, this never blocks on low confidence.
        """
        self._check_input(text)
        candidates = self._run_engine(text)
        ordered = sorted(candidates, key=lambda e: (e.start, e.end, e.entity_type))
        return DetectionResult(entities=tuple(ordered))

    def redact(self, text: str) -> RedactionResult:
        """Replace detected PHI/PII with reversible typed placeholders.

        Fail-closed on two paths:

        * the engine raising or returning a malformed span → :class:`DetectionError`;
        * any candidate below ``min_confidence`` → :class:`LowConfidenceError`.

        On success, every returned placeholder is reversible via :meth:`restore`.
        """
        self._check_input(text)
        # Gate on the FULL candidate set *before* resolving overlaps. Overlap
        # resolution folds each overlapping cluster into one span, which would
        # silently absorb an uncertain span that overlaps a confident one and
        # skip the block. Any uncertain candidate at all must fail the whole call.
        candidates = self._run_engine(text)

        uncertain = [e for e in candidates if e.score < self._threshold_for(e.entity_type)]
        if uncertain:
            raise LowConfidenceError(
                f"{len(uncertain)} detection(s) below the confidence threshold; "
                "blocking rather than passing raw data through",
                details={
                    "min_confidence": self.min_confidence,
                    "uncertain": [
                        {
                            "entity_type": e.entity_type,
                            "score": e.score,
                            "threshold": self._threshold_for(e.entity_type),
                        }
                        for e in uncertain
                    ],
                },
            )

        return self._build_redaction(text, self._resolve_overlaps(candidates, text))

    def restore(self, redacted_text: str, token_map: dict[str, str]) -> str:
        """Invert :meth:`redact`: substitute every placeholder back to its value.

        For output produced by :meth:`redact` this returns the original text
        byte-for-byte. The substitution is **single-pass**, so a value that
        happens to contain another placeholder is never re-expanded — this holds
        even for token maps not produced by :meth:`redact`.
        """
        if not isinstance(redacted_text, str):
            raise InvalidInputError("redacted_text must be a string")
        if not isinstance(token_map, dict):
            raise InvalidInputError("token_map must be a mapping of placeholder -> value")
        if not token_map:
            return redacted_text

        for placeholder, value in token_map.items():
            if not isinstance(placeholder, str) or not isinstance(value, str):
                raise RestoreError("token_map entries must be string -> string")
            if placeholder == "":
                raise RestoreError("token_map keys (placeholders) must be non-empty")

        # One left-to-right pass over the union of placeholders: each match is
        # replaced exactly once and the inserted value is never re-scanned, so
        # substituted text cannot be mistaken for another placeholder. Longest
        # key first makes a longer placeholder win where one is a prefix of
        # another.
        pattern = re.compile(
            "|".join(re.escape(p) for p in sorted(token_map, key=len, reverse=True))
        )
        return pattern.sub(lambda m: token_map[m.group(0)], redacted_text)

    # -- internals ----------------------------------------------------------

    def _threshold_for(self, entity_type: str) -> float:
        """The trust threshold for ``entity_type`` — its per-entity override if
        one is configured, else the global ``min_confidence``."""
        return self.entity_thresholds.get(entity_type, self.min_confidence)

    def _check_input(self, text: str) -> None:
        if not isinstance(text, str):
            raise InvalidInputError("text must be a string")
        if len(text) > self.max_input_chars:
            raise InputTooLargeError(
                f"input length {len(text)} exceeds limit {self.max_input_chars}",
                details={"length": len(text), "limit": self.max_input_chars},
            )

    def _run_engine(self, text: str) -> list[Entity]:
        """Call the engine, converting *any* failure or malformed result into a
        fail-closed :class:`DetectionError`, and drop below-floor noise."""
        try:
            raw = self._engine.detect(text)
        except Exception as exc:
            # Deliberate broad catch: any failure is unknown risk, so we block.
            raise DetectionError("detection engine failed") from exc

        kept: list[Entity] = []
        for entity in raw:
            if not isinstance(entity, Entity):
                raise DetectionError(f"engine returned a non-Entity: {entity!r}")
            if not (0 <= entity.start < entity.end <= len(text)):
                raise DetectionError(
                    f"engine returned an out-of-range span [{entity.start}:{entity.end}] "
                    f"for text of length {len(text)}"
                )
            if entity.entity_type in self.disabled_entities:
                continue
            if entity.score >= self.detection_floor:
                kept.append(entity)
        return kept

    @staticmethod
    def _resolve_overlaps(entities: list[Entity], text: str) -> list[Entity]:
        """Reduce to a non-overlapping set by MERGING overlaps — never dropping bytes.

        Overlapping detections are grouped into connected clusters, and each
        cluster is redacted as a single span covering the *union* of its members.
        Dropping the lower-priority span instead (the naive resolution) would emit
        its non-overlapping bytes in cleartext even though a detection flagged
        them — a PHI leak whenever two confident spans partially overlap (e.g. a
        greedy EMAIL_ADDRESS match abutting a CREDIT_CARD). Redacting the union
        guarantees every flagged byte is covered.

        The cluster's label/score is its highest-priority member — higher score,
        then longer span, then type name, then start — a total order, so the
        outcome never depends on input ordering. A connected overlap cluster is
        gap-free, so the union never redacts a byte that no detection flagged.
        """
        if not entities:
            return []
        # Sort by position, then grow a cluster while the next span starts before
        # the running cluster ends (i.e. overlaps it). Touching-but-disjoint spans
        # (start == cluster end) stay separate — they share no bytes.
        clusters: list[list[Entity]] = []
        cluster_end = -1
        for entity in sorted(entities, key=lambda e: (e.start, e.end)):
            if entity.start < cluster_end:
                clusters[-1].append(entity)
                cluster_end = max(cluster_end, entity.end)
            else:
                clusters.append([entity])
                cluster_end = entity.end

        merged: list[Entity] = []
        for cluster in clusters:
            rep = min(
                cluster,
                key=lambda e: (-e.score, -(e.end - e.start), e.entity_type, e.start),
            )
            start = min(e.start for e in cluster)
            end = max(e.end for e in cluster)
            merged.append(
                Entity(
                    entity_type=rep.entity_type,
                    start=start,
                    end=end,
                    score=rep.score,
                    text=text[start:end],
                )
            )
        # Stable left-to-right output.
        return sorted(merged, key=lambda e: (e.start, e.end, e.entity_type))

    def _build_redaction(self, text: str, entities: list[Entity]) -> RedactionResult:
        """Cut spans by offset and swap in collision-proof typed placeholders."""
        token_map: dict[str, str] = {}
        value_to_placeholder: dict[tuple[str, str], str] = {}
        type_counters: dict[str, int] = {}
        allocated: set[str] = set()

        pieces: list[str] = []
        cursor = 0
        for entity in entities:  # already sorted by start, non-overlapping
            value = text[entity.start : entity.end]
            key = (entity.entity_type, value)
            placeholder = value_to_placeholder.get(key)
            if placeholder is None:
                type_counters[entity.entity_type] = type_counters.get(entity.entity_type, 0) + 1
                placeholder = self._alloc_placeholder(
                    entity.entity_type, type_counters[entity.entity_type], allocated, text
                )
                value_to_placeholder[key] = placeholder
                token_map[placeholder] = value
            pieces.append(text[cursor : entity.start])
            pieces.append(placeholder)
            cursor = entity.end
        pieces.append(text[cursor:])

        return RedactionResult(
            redacted_text="".join(pieces),
            token_map=token_map,
            entities=tuple(entities),
        )

    @staticmethod
    def _alloc_placeholder(entity_type: str, n: int, allocated: set[str], text: str) -> str:
        """Return a placeholder guaranteed absent from ``text`` and from every
        previously allocated placeholder, so restore is an exact inverse."""
        candidate = f"[{entity_type}_{n}]"
        suffix = 0
        while candidate in allocated or candidate in text:
            suffix += 1
            candidate = f"[{entity_type}_{n}_{suffix}]"
        allocated.add(candidate)
        return candidate
