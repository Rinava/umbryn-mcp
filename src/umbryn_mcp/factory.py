"""Wire configuration into a ready-to-use :class:`~umbryn_mcp.redactor.Redactor`.

The ``auto`` engine prefers Presidio when it's importable and falls back to the
dependency-free regex engine otherwise — so ``pip install umbryn-mcp`` works
out of the box, and ``pip install "umbryn-mcp[presidio]"`` transparently
upgrades detection with no config change.
"""

from __future__ import annotations

import logging

from umbryn_mcp.audit import logging_sink
from umbryn_mcp.config import ENGINE_AUTO, ENGINE_PRESIDIO, ENGINE_REGEX, Config
from umbryn_mcp.engine import DetectionEngine
from umbryn_mcp.recognizers import DEFAULT_RECOGNIZERS, Recognizer
from umbryn_mcp.redactor import Redactor
from umbryn_mcp.regex_engine import RegexEngine

logger = logging.getLogger("umbryn_mcp")


def _recognizers(config: Config) -> tuple[Recognizer, ...]:
    """The built-in ruleset plus any user-defined recognizers from config.

    A malformed custom recognizer raises here, at startup, rather than silently
    disabling detection later.
    """
    custom = tuple(Recognizer.from_dict(spec) for spec in config.recognizers)
    return DEFAULT_RECOGNIZERS + custom


def build_engine(config: Config) -> DetectionEngine:
    """Construct the detection engine named by ``config``."""
    recognizers = _recognizers(config)

    if config.engine == ENGINE_REGEX:
        return RegexEngine(recognizers)

    if config.engine == ENGINE_PRESIDIO:
        from umbryn_mcp.presidio_engine import PresidioEngine

        return PresidioEngine(spacy_model=config.spacy_model, recognizers=recognizers)

    # auto: prefer Presidio, fall back cleanly.
    if config.engine == ENGINE_AUTO:
        try:
            from umbryn_mcp.presidio_engine import PresidioEngine

            engine = PresidioEngine(spacy_model=config.spacy_model, recognizers=recognizers)
            logger.info("umbryn-mcp: using Presidio engine")
            return engine
        except Exception as exc:  # noqa: BLE001 - deliberate: degrade to regex on any failure
            logger.info("umbryn-mcp: Presidio unavailable (%s); using regex engine", exc)
            return RegexEngine(recognizers)

    raise ValueError(f"unknown engine: {config.engine!r}")


def build_redactor(config: Config | None = None) -> Redactor:
    """Build a :class:`Redactor` from ``config`` (or the config file + environment)."""
    config = config or Config.load()
    return Redactor(
        build_engine(config),
        min_confidence=config.min_confidence,
        detection_floor=config.detection_floor,
        max_input_chars=config.max_input_chars,
        entity_thresholds=config.entity_thresholds,
        disabled_entities=config.disabled_entities,
        audit=logging_sink() if config.audit_log else None,
    )
