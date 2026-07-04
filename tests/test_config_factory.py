"""Config parsing and engine selection."""

from __future__ import annotations

import pytest

from phi_mcp.config import Config
from phi_mcp.factory import build_engine, build_redactor
from phi_mcp.regex_engine import RegexEngine


def test_defaults() -> None:
    cfg = Config.from_env({})
    assert cfg.engine == "auto"
    assert cfg.min_confidence == 0.5


def test_env_overrides() -> None:
    cfg = Config.from_env(
        {
            "PHI_MCP_ENGINE": "regex",
            "PHI_MCP_MIN_CONFIDENCE": "0.7",
            "PHI_MCP_DETECTION_FLOOR": "0.2",
            "PHI_MCP_MAX_INPUT_CHARS": "500",
        }
    )
    assert cfg.engine == "regex"
    assert cfg.min_confidence == 0.7
    assert cfg.detection_floor == 0.2
    assert cfg.max_input_chars == 500


@pytest.mark.parametrize(
    "env",
    [
        {"PHI_MCP_ENGINE": "banana"},
        {"PHI_MCP_MIN_CONFIDENCE": "not-a-number"},
        {"PHI_MCP_MAX_INPUT_CHARS": "1.5"},
    ],
)
def test_invalid_env_rejected(env: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        Config.from_env(env)


def test_regex_engine_selected_explicitly() -> None:
    assert isinstance(build_engine(Config(engine="regex")), RegexEngine)


def test_auto_falls_back_to_regex_when_presidio_absent() -> None:
    # Presidio isn't installed in the fast-test environment, so auto must
    # gracefully degrade to the regex engine rather than crash.
    engine = build_engine(Config(engine="auto"))
    assert isinstance(engine, RegexEngine)


def test_build_redactor_wires_thresholds() -> None:
    redactor = build_redactor(Config(engine="regex", min_confidence=0.66, detection_floor=0.22))
    assert redactor.min_confidence == 0.66
    assert redactor.detection_floor == 0.22
