"""Optional Presidio-backed engine: statistical NER on top of the shared ruleset.

Division of labour: **Presidio contributes only the entities regex can't** —
``PERSON`` and ``LOCATION`` (spaCy NER), ``NRP`` (nationality/religion/politics),
and ``DATE_TIME``. Every structured identifier (NPI, DEA, MBI, MRN, CLIA, SSN,
email, phone, credit card, IP, URL) comes from the same checksum-validated
:class:`~phi_mcp.regex_engine.RegexEngine` the default engine uses.

Why not lean on Presidio's own identifier recognizers? Because they aren't
check-digit validated and lose Presidio's overlap conflict-resolution to broader
patterns — e.g. a valid NPI gets swallowed by ``US_BANK_NUMBER`` and never
surfaces. Sourcing identifiers from the shared ruleset gives both engines
identical, validated identifier behaviour and lets Presidio do what it's good at.

Presidio is an *optional* dependency. Importing this module is cheap; the heavy
import happens only when :class:`PresidioEngine` is constructed, and a missing
install raises a clear, actionable :class:`ImportError`.
"""

from __future__ import annotations

from phi_mcp.regex_engine import RegexEngine
from phi_mcp.types import Entity

_INSTALL_HINT = (
    "The Presidio engine requires extra dependencies. Install them with:\n"
    '    pip install "phi-redact-mcp[presidio]"\n'
    "    python -m spacy download en_core_web_lg\n"
    "Or set PHI_MCP_ENGINE=regex to use the dependency-free default engine."
)


class PresidioEngine:
    """Detection engine: Presidio/spaCy NER + the shared identifier ruleset.

    Args:
        spacy_model: the spaCy model to load (default ``en_core_web_lg``; use
            ``en_core_web_sm`` for a lighter, lower-recall setup).
        language: analysis language.
    """

    name = "presidio"

    #: Presidio's native names for the entities we take from it — the ones the
    #: regex engine can't produce.
    _NER_ENTITIES = ("PERSON", "LOCATION", "NRP", "DATE_TIME")

    def __init__(self, spacy_model: str = "en_core_web_lg", language: str = "en") -> None:
        try:
            from presidio_analyzer import AnalyzerEngine
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
        self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=[language])
        # Identifiers come from the shared, checksum-validated ruleset.
        self._identifiers = RegexEngine()

    def detect(self, text: str) -> list[Entity]:
        ner = self._analyzer.analyze(
            text=text,
            language=self._language,
            entities=list(self._NER_ENTITIES),
            score_threshold=0.0,
        )
        # NER entity names (PERSON, LOCATION, NRP, DATE_TIME) are already canonical.
        entities = [
            Entity(
                entity_type=r.entity_type,
                start=r.start,
                end=r.end,
                score=float(r.score),
                text=text[r.start : r.end],
            )
            for r in ner
        ]
        entities.extend(self._identifiers.detect(text))
        return entities
