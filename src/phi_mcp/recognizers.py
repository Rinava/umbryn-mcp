"""The shared, dependency-free recognizer ruleset.

Each :class:`Recognizer` is a regex plus scoring metadata. The regex engine runs
these directly; the Presidio engine reuses the format-less ones (MRN, CLIA) as
custom ``PatternRecognizer``s to complement Presidio's built-ins.

Scoring philosophy:

* **Checksum-backed** identifiers (NPI, DEA, credit card) get a high base score
  *and* a validator — a match that fails its check digit is discarded outright,
  not merely down-scored.
* **Strongly-structured** identifiers (email, MBI, dashed SSN with structural
  exclusions, CLIA) score high on shape alone.
* **Format-less** identifiers (MRN, bare SSN) are context-gated: they only fire
  when a trigger word sits nearby, and score modestly.

Context boosting mirrors Presidio's ``LemmaContextAwareEnhancer``: a nearby
context word adds ``CONTEXT_BOOST`` and floors the score at ``CONTEXT_FLOOR``.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from phi_mcp import checksums, entities

# Context-boost constants, matching Presidio's defaults.
CONTEXT_BOOST = 0.35
CONTEXT_FLOOR = 0.4
CONTEXT_WINDOW_BEFORE = 48
CONTEXT_WINDOW_AFTER = 12

# Allowed MBI letters (A-Z minus S, L, O, I, B, Z) and alphanumerics.
_MBI_L = "[ACDEFGHJKMNPQRTUVWXY]"
_MBI_AN = "[ACDEFGHJKMNPQRTUVWXY0-9]"


@dataclass(frozen=True)
class Recognizer:
    """A single detection rule.

    Args:
        entity_type: canonical entity name (see :mod:`phi_mcp.entities`).
        regex: the pattern. If ``group`` is non-zero, only that capture group's
            span is reported (used to anchor on context words without redacting
            them).
        base_score: confidence before any context boost, in ``[0, 1]``.
        context: trigger words that boost the score when found nearby.
        context_required: if true, a match with no nearby context word is dropped.
        validator: optional check-digit validator; a match it rejects is dropped.
        group: capture group whose span to report (0 = whole match).
        flags: regex flags.
    """

    entity_type: str
    regex: str
    base_score: float
    context: tuple[str, ...] = ()
    context_required: bool = False
    validator: Callable[[str], bool] | None = None
    group: int = 0
    flags: int = field(default=re.IGNORECASE)


# Ordered roughly by precision/value. The engine runs all of them; the redactor
# resolves any overlaps deterministically.
DEFAULT_RECOGNIZERS: tuple[Recognizer, ...] = (
    # --- Checksum-backed --------------------------------------------------
    Recognizer(
        entity_type=entities.NPI,
        regex=r"\b[12]\d{9}\b",
        base_score=0.85,
        context=("npi", "provider", "national provider"),
        validator=checksums.npi_is_valid,
    ),
    Recognizer(
        entity_type=entities.DEA_NUMBER,
        regex=r"\b[ABCDEFGHJKLMPRSTUX][A-Z9]\d{7}\b",
        base_score=0.8,
        context=("dea", "prescriber", "prescription", "controlled"),
        validator=checksums.dea_is_valid,
    ),
    Recognizer(
        entity_type=entities.CREDIT_CARD,
        regex=r"\b\d(?:[ -]?\d){11,18}\b",
        base_score=0.85,
        context=("card", "credit", "visa", "mastercard", "amex", "payment"),
        validator=checksums.luhn_is_valid,
    ),
    # --- Strongly structured ---------------------------------------------
    Recognizer(
        entity_type=entities.EMAIL_ADDRESS,
        # Domain is label-structured (labels can't contain '.') and every
        # quantifier is bounded, so matching is linear — no ReDoS on adversarial
        # input. This also matches the address inside a "mailto:" prefix.
        regex=r"\b[A-Za-z0-9._%+-]{1,64}@(?:[A-Za-z0-9-]{1,63}\.){1,8}[A-Za-z]{2,24}\b",
        base_score=0.9,
    ),
    Recognizer(
        entity_type=entities.MEDICARE_BENEFICIARY_ID,
        regex=(
            r"\b[1-9]"
            + _MBI_L
            + _MBI_AN
            + r"[0-9]"
            + _MBI_L
            + _MBI_AN
            + r"[0-9]"
            + _MBI_L
            + _MBI_L
            + r"[0-9]{2}\b"
        ),
        base_score=0.6,
        context=("mbi", "medicare", "beneficiary"),
    ),
    Recognizer(
        entity_type=entities.US_SSN,
        regex=r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b",
        base_score=0.85,
        context=("ssn", "social security"),
    ),
    Recognizer(
        entity_type=entities.CLIA_NUMBER,
        regex=r"\b\d{2}D\d{7}\b",
        base_score=0.6,
        context=("clia", "lab", "laboratory"),
    ),
    Recognizer(
        entity_type=entities.IP_ADDRESS,
        regex=r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b",
        base_score=0.6,
    ),
    Recognizer(
        entity_type=entities.URL,
        regex=r"\bhttps?://[^\s<>\"')\]]+",
        base_score=0.6,
    ),
    Recognizer(
        entity_type=entities.PHONE_NUMBER,
        regex=(r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]\d{3}[-.\s]\d{4}(?!\d)"),
        base_score=0.6,
        context=("phone", "tel", "call", "cell", "mobile", "fax", "contact"),
    ),
    # --- Format-less, context-anchored -----------------------------------
    Recognizer(
        entity_type=entities.MEDICAL_RECORD_NUMBER,
        regex=(
            r"(?:MRN|MR\s*#|med(?:ical)?\s*rec(?:ord)?(?:\s*(?:no|num|number|#))?"
            r"|patient\s*id|chart\s*(?:no|number|#))[:#\s-]*([A-Z]{0,4}-?\d{5,12}[A-Z]?)"
        ),
        base_score=0.6,
        group=1,
    ),
    # Bare 9-digit SSN: only when a context word is present (very FP-prone alone).
    Recognizer(
        entity_type=entities.US_SSN,
        regex=r"\b(?!000|666|9\d\d)\d{3}(?!00)\d{2}(?!0000)\d{4}\b",
        base_score=0.25,
        context=("ssn", "social security", "soc sec"),
        context_required=True,
    ),
)
