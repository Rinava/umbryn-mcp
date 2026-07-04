"""Wire configuration into a ready-to-use :class:`~phi_mcp.redactor.Redactor`.

The ``auto`` engine prefers Presidio when it's importable and falls back to the
dependency-free regex engine otherwise — so ``pip install phi-redact-mcp`` works
out of the box, and ``pip install "phi-redact-mcp[presidio]"`` transparently
upgrades detection with no config change.
"""

from __future__ import annotations

import logging

from phi_mcp.config import ENGINE_AUTO, ENGINE_PRESIDIO, ENGINE_REGEX, Config
from phi_mcp.engine import DetectionEngine
from phi_mcp.redactor import Redactor
from phi_mcp.regex_engine import RegexEngine

logger = logging.getLogger("phi_mcp")


def build_engine(config: Config) -> DetectionEngine:
    """Construct the detection engine named by ``config``."""
    if config.engine == ENGINE_REGEX:
        return RegexEngine()

    if config.engine == ENGINE_PRESIDIO:
        from phi_mcp.presidio_engine import PresidioEngine

        return PresidioEngine(spacy_model=config.spacy_model)

    # auto: prefer Presidio, fall back cleanly.
    if config.engine == ENGINE_AUTO:
        try:
            from phi_mcp.presidio_engine import PresidioEngine

            engine = PresidioEngine(spacy_model=config.spacy_model)
            logger.info("phi-redact-mcp: using Presidio engine")
            return engine
        except Exception as exc:  # noqa: BLE001 - deliberate: degrade to regex on any failure
            logger.info("phi-redact-mcp: Presidio unavailable (%s); using regex engine", exc)
            return RegexEngine()

    raise ValueError(f"unknown engine: {config.engine!r}")


def build_redactor(config: Config | None = None) -> Redactor:
    """Build a :class:`Redactor` from ``config`` (or the environment)."""
    config = config or Config.from_env()
    return Redactor(
        build_engine(config),
        min_confidence=config.min_confidence,
        detection_floor=config.detection_floor,
        max_input_chars=config.max_input_chars,
    )
