"""Optional Presidio-backed engine: adds statistical NER on top of the ruleset.

Presidio contributes ``PERSON`` and ``LOCATION`` (via spaCy) plus mature
built-ins for SSN, phone, email, credit card, ``US_NPI``, and ``US_MBI``. We add
custom recognizers for the format-less identifiers Presidio lacks (MRN, CLIA) and
normalise its entity names to our canonical taxonomy.

Presidio is an *optional* dependency. Importing this module is cheap; the heavy
import happens only when :class:`PresidioEngine` is constructed, and a missing
install raises a clear, actionable :class:`ImportError`.
"""

from __future__ import annotations

from phi_mcp.entities import (
    CLIA_NUMBER,
    MEDICAL_RECORD_NUMBER,
    PRESIDIO_ENTITY_MAP,
)
from phi_mcp.types import Entity

_INSTALL_HINT = (
    "The Presidio engine requires extra dependencies. Install them with:\n"
    '    pip install "phi-redact-mcp[presidio]"\n'
    "    python -m spacy download en_core_web_lg\n"
    "Or set PHI_MCP_ENGINE=regex to use the dependency-free default engine."
)


class PresidioEngine:
    """Detection engine backed by Microsoft Presidio + spaCy NER.

    Args:
        spacy_model: the spaCy model to load (default ``en_core_web_lg``; use
            ``en_core_web_sm`` for a lighter, lower-recall setup).
        language: analysis language.
    """

    name = "presidio"

    def __init__(self, spacy_model: str = "en_core_web_lg", language: str = "en") -> None:
        try:
            from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
            from presidio_analyzer.nlp_engine import NlpEngineProvider
        except ImportError as exc:  # pragma: no cover - exercised only without presidio
            raise ImportError(_INSTALL_HINT) from exc

        self._language = language

        nlp_engine = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": language, "model_name": spacy_model}],
            }
        ).create_engine()

        # Let AnalyzerEngine build its default registry (all predefined
        # recognizers, including the US ones we rely on: US_NPI, US_MBI, US_SSN,
        # MEDICAL_LICENSE), then layer on the identifiers Presidio doesn't ship.
        analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=[language])

        # Low base score + context words; Presidio's enhancer lifts them near a trigger.
        analyzer.registry.add_recognizer(
            PatternRecognizer(
                supported_entity=MEDICAL_RECORD_NUMBER,
                name="MrnRecognizer",
                patterns=[Pattern("mrn", r"\b[A-Z]{0,4}-?\d{5,12}[A-Z]?\b", 0.2)],
                context=["mrn", "medical record", "record number", "patient", "chart"],
                supported_language=language,
            )
        )
        analyzer.registry.add_recognizer(
            PatternRecognizer(
                supported_entity=CLIA_NUMBER,
                name="CliaRecognizer",
                patterns=[Pattern("clia", r"\b\d{2}D\d{7}\b", 0.4)],
                context=["clia", "lab", "laboratory"],
                supported_language=language,
            )
        )

        self._analyzer = analyzer

    def detect(self, text: str) -> list[Entity]:
        results = self._analyzer.analyze(text=text, language=self._language, score_threshold=0.0)
        return [
            Entity(
                entity_type=PRESIDIO_ENTITY_MAP.get(r.entity_type, r.entity_type),
                start=r.start,
                end=r.end,
                score=float(r.score),
                text=text[r.start : r.end],
            )
            for r in results
        ]
