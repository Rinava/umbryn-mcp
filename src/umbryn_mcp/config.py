"""Runtime configuration, sourced from an optional JSON file and the environment.

Every knob has a safe default, so ``umbryn-mcp`` runs with zero config. Two
configuration surfaces, in increasing precedence:

1. **A JSON config file**, pointed to by ``UMBRYN_CONFIG``. This is the only way
   to express the *structured* settings — per-entity confidence thresholds,
   disabled entity types, and custom recognizers — that don't fit a flat
   environment variable.
2. **Environment variables** (``UMBRYN_*``). These override the matching scalar
   in the file, so a client can ship one config file and still tweak a threshold
   per launch. The environment is the natural surface for an MCP server since
   clients start it as a subprocess and pass ``env`` in their config block.

The file is JSON rather than TOML deliberately: it needs no third-party parser on
Python 3.10 (``tomllib`` is 3.11+), which keeps the dependency-free promise
intact, and it mirrors the JSON MCP clients already use for their config blocks.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from umbryn_mcp.redactor import (
    DEFAULT_DETECTION_FLOOR,
    DEFAULT_MAX_INPUT_CHARS,
    DEFAULT_MIN_CONFIDENCE,
)

logger = logging.getLogger("umbryn_mcp")

#: Valid values for ``UMBRYN_ENGINE``.
ENGINE_AUTO = "auto"
ENGINE_REGEX = "regex"
ENGINE_PRESIDIO = "presidio"

#: Environment variable naming the JSON config file.
CONFIG_ENV = "UMBRYN_CONFIG"

#: Recognized top-level keys in the JSON config file. Anything else is a likely
#: typo, so we warn (but don't fail — forward-compat with newer configs).
_KNOWN_KEYS = frozenset(
    {
        "engine",
        "min_confidence",
        "detection_floor",
        "max_input_chars",
        "spacy_model",
        "entity_thresholds",
        "disabled_entities",
        "recognizers",
        "audit_log",
    }
)


@dataclass(frozen=True)
class Config:
    """Resolved server configuration.

    ``entity_thresholds`` and ``disabled_entities`` come only from the config
    file — they have no environment-variable equivalent because they're
    structured, not scalar.
    """

    engine: str = ENGINE_AUTO
    min_confidence: float = DEFAULT_MIN_CONFIDENCE
    detection_floor: float = DEFAULT_DETECTION_FLOOR
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS
    spacy_model: str = "en_core_web_lg"
    #: Emit structured audit records (redaction counts/types, never raw values).
    audit_log: bool = False
    #: Per-entity trust thresholds, overriding ``min_confidence`` for that type.
    entity_thresholds: Mapping[str, float] = field(default_factory=dict)
    #: Entity types to drop entirely — never detected, never redacted.
    disabled_entities: frozenset[str] = frozenset()
    #: Raw custom-recognizer specs; the factory turns these into
    #: :class:`~umbryn_mcp.recognizers.Recognizer` objects at startup.
    recognizers: tuple[Mapping[str, Any], ...] = ()

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Config:
        """Resolve configuration from the environment only (no config file).

        Retained for callers that want a pure-environment config; most code
        should use :meth:`load`, which also honours ``UMBRYN_CONFIG``.
        """
        env = os.environ if env is None else env
        return cls._resolve({}, env)

    @classmethod
    def load(cls, env: Mapping[str, str] | None = None) -> Config:
        """Resolve configuration from the JSON config file (if any) and the
        environment, with environment variables taking precedence over the file."""
        env = os.environ if env is None else env
        file_data = _read_config_file(env.get(CONFIG_ENV))
        return cls._resolve(file_data, env)

    @classmethod
    def _resolve(cls, file_data: Mapping[str, Any], env: Mapping[str, str]) -> Config:
        for key in file_data:
            if key not in _KNOWN_KEYS:
                logger.warning("umbryn-mcp: ignoring unknown config key %r", key)

        engine = _pick_str(env, "UMBRYN_ENGINE", file_data, "engine", ENGINE_AUTO).strip().lower()
        if engine not in (ENGINE_AUTO, ENGINE_REGEX, ENGINE_PRESIDIO):
            raise ValueError(f"engine must be one of auto/regex/presidio, got {engine!r}")

        return cls(
            engine=engine,
            min_confidence=_pick_float(
                env, "UMBRYN_MIN_CONFIDENCE", file_data, "min_confidence", DEFAULT_MIN_CONFIDENCE
            ),
            detection_floor=_pick_float(
                env, "UMBRYN_DETECTION_FLOOR", file_data, "detection_floor", DEFAULT_DETECTION_FLOOR
            ),
            max_input_chars=_pick_int(
                env, "UMBRYN_MAX_INPUT_CHARS", file_data, "max_input_chars", DEFAULT_MAX_INPUT_CHARS
            ),
            spacy_model=_pick_str(
                env, "UMBRYN_SPACY_MODEL", file_data, "spacy_model", "en_core_web_lg"
            ),
            audit_log=_pick_bool(env, "UMBRYN_AUDIT_LOG", file_data, "audit_log", False),
            entity_thresholds=_parse_entity_thresholds(file_data.get("entity_thresholds")),
            disabled_entities=_parse_disabled_entities(file_data.get("disabled_entities")),
            recognizers=_parse_recognizers(file_data.get("recognizers")),
        )


def _read_config_file(path: str | None) -> dict[str, Any]:
    """Load and JSON-parse the config file, failing closed on any problem.

    A misconfigured server must not start silently with surprising behaviour, so
    a missing file, unreadable file, invalid JSON, or non-object top level all
    raise rather than degrade to defaults.
    """
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:
        raise ValueError(f"config file not found: {path}") from exc
    except OSError as exc:
        raise ValueError(f"could not read config file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"config file {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"config file {path} must contain a JSON object at the top level")
    return data


def _parse_entity_thresholds(raw: Any) -> Mapping[str, float]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("entity_thresholds must be a JSON object of entity_type -> number")
    thresholds: dict[str, float] = {}
    for entity_type, value in raw.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"entity_thresholds[{entity_type!r}] must be a number, got {value!r}")
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"entity_thresholds[{entity_type!r}] must be in [0, 1], got {value}")
        thresholds[entity_type] = float(value)
    return thresholds


def _parse_disabled_entities(raw: Any) -> frozenset[str]:
    if raw is None:
        return frozenset()
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError("disabled_entities must be a JSON array of entity_type strings")
    return frozenset(raw)


def _parse_recognizers(raw: Any) -> tuple[Mapping[str, Any], ...]:
    """Shallow-validate the ``recognizers`` array. Per-recognizer field
    validation and regex compilation happen when the factory turns each spec
    into a :class:`~umbryn_mcp.recognizers.Recognizer`."""
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise ValueError("recognizers must be a JSON array of recognizer objects")
    return tuple(raw)


def _pick_str(
    env: Mapping[str, str], env_key: str, file_data: Mapping[str, Any], file_key: str, default: str
) -> str:
    raw = env.get(env_key)
    if raw is not None and raw != "":
        return raw
    value = file_data.get(file_key, default)
    if not isinstance(value, str):
        raise ValueError(f"{file_key} must be a string, got {value!r}")
    return value


def _pick_float(
    env: Mapping[str, str],
    env_key: str,
    file_data: Mapping[str, Any],
    file_key: str,
    default: float,
) -> float:
    raw = env.get(env_key)
    if raw is not None and raw != "":
        try:
            return float(raw)
        except ValueError as exc:
            raise ValueError(f"{env_key} must be a number, got {raw!r}") from exc
    value = file_data.get(file_key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{file_key} must be a number, got {value!r}")
    return float(value)


_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


def _pick_bool(
    env: Mapping[str, str], env_key: str, file_data: Mapping[str, Any], file_key: str, default: bool
) -> bool:
    raw = env.get(env_key)
    # An empty env var means "unset" (fall through to the file), matching the
    # scalar helpers above.
    if raw is not None and raw.strip() != "":
        lowered = raw.strip().lower()
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
        raise ValueError(f"{env_key} must be a boolean (true/false), got {raw!r}")
    value = file_data.get(file_key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{file_key} must be a boolean, got {value!r}")
    return value


def _pick_int(
    env: Mapping[str, str], env_key: str, file_data: Mapping[str, Any], file_key: str, default: int
) -> int:
    raw = env.get(env_key)
    if raw is not None and raw != "":
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError(f"{env_key} must be an integer, got {raw!r}") from exc
    value = file_data.get(file_key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{file_key} must be an integer, got {value!r}")
    return value
