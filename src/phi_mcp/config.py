"""Runtime configuration, sourced from environment variables.

Every knob has a safe default, so ``phi-redact-mcp`` runs with zero config. The
environment is the natural configuration surface for an MCP server since clients
launch it as a subprocess and pass ``env`` in their config block.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from phi_mcp.redactor import (
    DEFAULT_DETECTION_FLOOR,
    DEFAULT_MAX_INPUT_CHARS,
    DEFAULT_MIN_CONFIDENCE,
)

#: Valid values for ``PHI_MCP_ENGINE``.
ENGINE_AUTO = "auto"
ENGINE_REGEX = "regex"
ENGINE_PRESIDIO = "presidio"


@dataclass(frozen=True)
class Config:
    """Resolved server configuration."""

    engine: str = ENGINE_AUTO
    min_confidence: float = DEFAULT_MIN_CONFIDENCE
    detection_floor: float = DEFAULT_DETECTION_FLOOR
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS
    spacy_model: str = "en_core_web_lg"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Config:
        env = os.environ if env is None else env
        engine = env.get("PHI_MCP_ENGINE", ENGINE_AUTO).strip().lower()
        if engine not in (ENGINE_AUTO, ENGINE_REGEX, ENGINE_PRESIDIO):
            raise ValueError(f"PHI_MCP_ENGINE must be one of auto/regex/presidio, got {engine!r}")
        return cls(
            engine=engine,
            min_confidence=_float(env, "PHI_MCP_MIN_CONFIDENCE", DEFAULT_MIN_CONFIDENCE),
            detection_floor=_float(env, "PHI_MCP_DETECTION_FLOOR", DEFAULT_DETECTION_FLOOR),
            max_input_chars=_int(env, "PHI_MCP_MAX_INPUT_CHARS", DEFAULT_MAX_INPUT_CHARS),
            spacy_model=env.get("PHI_MCP_SPACY_MODEL", "en_core_web_lg"),
        )


def _float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be a number, got {raw!r}") from exc


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer, got {raw!r}") from exc
