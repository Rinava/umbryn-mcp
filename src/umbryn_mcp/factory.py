"""Wire configuration into a ready-to-use :class:`~umbryn_mcp.redactor.Redactor`.

The ``auto`` engine prefers Presidio when it's importable and falls back to the
dependency-free regex engine otherwise — so ``pip install umbryn-mcp`` works
out of the box, and ``pip install "umbryn-mcp[presidio]"`` transparently
upgrades detection with no config change.
"""

from __future__ import annotations

import logging

from umbryn_mcp.config import ENGINE_AUTO, ENGINE_PRESIDIO, ENGINE_REGEX, Config
from umbryn_mcp.engine import DetectionEngine
from umbryn_mcp.redactor import Redactor
from umbryn_mcp.regex_engine import RegexEngine

logger = logging.getLogger("umbryn_mcp")


def build_engine(config: Config) -> DetectionEngine:
    """Construct the detection engine named by ``config``."""
    if config.engine == ENGINE_REGEX:
        return RegexEngine()

    if config.engine == ENGINE_PRESIDIO:
        from umbryn_mcp.presidio_engine import PresidioEngine

        return PresidioEngine(spacy_model=config.spacy_model)

    # auto: prefer Presidio, fall back cleanly.
    if config.engine == ENGINE_AUTO:
        try:
            from umbryn_mcp.presidio_engine import PresidioEngine

            engine = PresidioEngine(spacy_model=config.spacy_model)
            logger.info("umbryn-mcp: using Presidio engine")
            return engine
        except Exception as exc:  # noqa: BLE001 - deliberate: degrade to regex on any failure
            logger.info("umbryn-mcp: Presidio unavailable (%s); using regex engine", exc)
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
