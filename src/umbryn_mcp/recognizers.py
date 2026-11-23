"""The shared, dependency-free recognizer ruleset.

Each :class:`Recognizer` is a regex plus scoring metadata. The regex engine runs
these directly; the Presidio engine reuses the format-less ones (MRN, CLIA) as
custom ``PatternRecognizer``s to complement Presidio's built-ins.

Scoring philosophy:

* **Checksum-backed** identifiers (NPI, DEA, credit card, IBAN) get a high base
  score *and* a validator — a match that fails its check digit is discarded
  outright, not merely down-scored.
* **Strongly-structured** identifiers (email, MBI, dashed SSN with structural
  exclusions, CLIA) score high on shape alone.
* **Format-less** identifiers (MRN, bare SSN) are context-gated: they only fire
  when a trigger word sits nearby, and score modestly.

Context boosting mirrors Presidio's ``LemmaContextAwareEnhancer``: a nearby
context word adds ``CONTEXT_BOOST`` and floors the score at ``CONTEXT_FLOOR``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from umbryn_mcp import checksums, entities

# Context-boost constants, matching Presidio's defaults.
CONTEXT_BOOST = 0.35
CONTEXT_FLOOR = 0.4
CONTEXT_WINDOW_BEFORE = 48
CONTEXT_WINDOW_AFTER = 12

#: Regex-flag names a custom recognizer may set from the config file.
_FLAG_NAMES: dict[str, int] = {
    "IGNORECASE": re.IGNORECASE,
    "I": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "M": re.MULTILINE,
    "DOTALL": re.DOTALL,
    "S": re.DOTALL,
    "VERBOSE": re.VERBOSE,
    "X": re.VERBOSE,
    "ASCII": re.ASCII,
    "A": re.ASCII,
}

# Allowed MBI letters (A-Z minus S, L, O, I, B, Z) and alphanumerics.
_MBI_L = "[ACDEFGHJKMNPQRTUVWXY]"
_MBI_AN = "[ACDEFGHJKMNPQRTUVWXY0-9]"


@dataclass(frozen=True)
class Recognizer:
    """A single detection rule.

    Args:
        entity_type: canonical entity name (see :mod:`umbryn_mcp.entities`).
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

    @classmethod
    def from_dict(cls, spec: Mapping[str, Any]) -> Recognizer:
        """Build a recognizer from a plain config dict, validating every field.

        Used to load user-defined recognizers from the JSON config file. A
        ``validator`` is named by string and resolved against
        :data:`~umbryn_mcp.checksums.VALIDATORS` — a config file can attach a
        check digit but cannot inject a callable. Raises :class:`ValueError` on
        any malformed field (including a regex that fails to compile), so a bad
        config fails at startup rather than silently disabling detection.

        Note on ReDoS: the regex is the operator's own trusted config, but a
        pathological pattern can still backtrack catastrophically. Prefer bounded
        quantifiers, as the built-in recognizers do.
        """
        if not isinstance(spec, Mapping):
            raise ValueError(f"recognizer spec must be an object, got {spec!r}")

        entity_type = spec.get("entity_type")
        if not isinstance(entity_type, str) or not entity_type:
            raise ValueError("recognizer 'entity_type' must be a non-empty string")

        regex = spec.get("regex")
        if not isinstance(regex, str) or not regex:
            raise ValueError(f"recognizer {entity_type!r} 'regex' must be a non-empty string")

        base_score = spec.get("base_score")
        if isinstance(base_score, bool) or not isinstance(base_score, (int, float)):
            raise ValueError(f"recognizer {entity_type!r} 'base_score' must be a number")
        if not 0.0 <= base_score <= 1.0:
            raise ValueError(f"recognizer {entity_type!r} 'base_score' must be in [0, 1]")

        context = spec.get("context", [])
        if not isinstance(context, list) or not all(isinstance(w, str) for w in context):
            raise ValueError(f"recognizer {entity_type!r} 'context' must be an array of strings")

        context_required = spec.get("context_required", False)
        if not isinstance(context_required, bool):
            raise ValueError(f"recognizer {entity_type!r} 'context_required' must be a boolean")

        group = spec.get("group", 0)
        if isinstance(group, bool) or not isinstance(group, int) or group < 0:
            raise ValueError(f"recognizer {entity_type!r} 'group' must be a non-negative integer")

        validator = None
        validator_name = spec.get("validator")
        if validator_name is not None:
            if not isinstance(validator_name, str) or validator_name not in checksums.VALIDATORS:
                allowed = ", ".join(sorted(checksums.VALIDATORS))
                raise ValueError(
                    f"recognizer {entity_type!r} 'validator' must be one of: {allowed}"
                )
            validator = checksums.VALIDATORS[validator_name]

        flags = _parse_flags(entity_type, spec.get("flags"))
        try:
            re.compile(regex, flags)
        except re.error as exc:
            raise ValueError(
                f"recognizer {entity_type!r} 'regex' failed to compile: {exc}"
            ) from exc

        return cls(
            entity_type=entity_type,
            regex=regex,
            base_score=float(base_score),
            context=tuple(context),
            context_required=context_required,
            validator=validator,
            group=group,
            flags=flags,
        )


def _parse_flags(entity_type: str, raw: Any) -> int:
    """Resolve a list of regex-flag names to a combined flag int.

    Omitting ``flags`` defaults to case-insensitive (matching the built-ins); an
    explicit empty list means no flags.
    """
    if raw is None:
        return re.IGNORECASE
    if not isinstance(raw, list):
        raise ValueError(f"recognizer {entity_type!r} 'flags' must be an array of flag names")
    flags = 0
    for name in raw:
        key = name.upper() if isinstance(name, str) else None
        if key is None or key not in _FLAG_NAMES:
            allowed = ", ".join(sorted(_FLAG_NAMES))
            raise ValueError(
                f"recognizer {entity_type!r} unknown regex flag {name!r}; allowed: {allowed}"
            )
        flags |= _FLAG_NAMES[key]
    return flags


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
    Recognizer(
        entity_type=entities.IBAN_CODE,
        regex=r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b",
        base_score=0.85,
        context=("iban", "bank", "account", "swift", "bic", "wire", "transfer"),
        validator=checksums.iban_is_valid,
    ),
    # UK NHS number: 10 digits (printed 3-3-4) with a mod-11 check digit. Any
    # 10-digit run is a large match space, so it's context-gated even though the
    # checksum is strong — a nearby "NHS" is what turns a checksum hit into a
    # confident one.
    Recognizer(
        entity_type=entities.UK_NHS_NUMBER,
        regex=r"\b\d{3}[ -]?\d{3}[ -]?\d{4}\b",
        base_score=0.4,
        context=("nhs", "national health service", "national health"),
        context_required=True,
        validator=checksums.nhs_is_valid,
    ),
    # Australian TFN: 9 digits (printed 3-3-3) with a mod-11 weighted check.
    # The checksum passes ~1 in 11 random 9-digit runs, so require a nearby
    # "TFN" / "tax file number" trigger, like NHS and SIN.
    Recognizer(
        entity_type=entities.AUSTRALIA_TFN,
        regex=r"\b\d{3}[ -]?\d{3}[ -]?\d{3}\b",
        base_score=0.4,
        context=("tfn", "tax file number", "tax file"),
        context_required=True,
        validator=checksums.tfn_is_valid,
    ),
    # Canadian SIN: 9 digits (printed 3-3-3) with a Luhn check. Luhn alone passes
    # ~1 in 10 random numbers, so require a nearby "SIN"/"social insurance".
    Recognizer(
        entity_type=entities.CANADA_SIN,
        regex=r"\b\d{3}[ -]\d{3}[ -]\d{3}\b",
        base_score=0.4,
        context=("sin", "social insurance"),
        context_required=True,
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
    # US ITIN: like an SSN but starts with 9 and the group digits fall in the
    # IRS ranges 50-65, 70-88, 90-92, 94-99. That constrained shape is specific
    # enough to score on its own (and the dashed SSN rule excludes the 9XX prefix,
    # so they never compete).
    Recognizer(
        entity_type=entities.US_ITIN,
        regex=r"\b9\d{2}-(?:5\d|6[0-5]|7\d|8[0-8]|9[0-2]|9[4-9])-\d{4}\b",
        base_score=0.6,
        context=("itin", "taxpayer", "tax id", "individual taxpayer"),
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
    # Legacy Medicare HICN: a 9-digit SSN plus a 1-2 char Beneficiary ID Code
    # suffix (e.g. 123-45-6789A). The alpha suffix is what distinguishes it from
    # a plain SSN; still context-gated since the digit shape alone is SSN-like.
    Recognizer(
        entity_type=entities.MEDICARE_HICN,
        regex=r"\b\d{3}-?\d{2}-?\d{4}[A-Z]\d?\b",
        base_score=0.4,
        context=("hicn", "medicare", "health insurance claim", "claim number", "beneficiary"),
        context_required=True,
    ),
    # US driver's license: no national format or checksum, so anchor on the label
    # itself and capture the following token (requiring at least one digit to
    # avoid grabbing an ordinary word). Reports only the number, not the label.
    Recognizer(
        entity_type=entities.US_DRIVERS_LICENSE,
        regex=(
            r"(?:driver'?s?\s+licen[sc]e|driving\s+licen[sc]e|\bDL)"
            r"(?:\s*(?:no\.?|number|#))?[:#\s-]*((?=[A-Z0-9]*\d)[A-Z0-9]{4,20})"
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
