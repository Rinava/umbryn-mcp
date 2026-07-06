"""Per-entity thresholds, disabled entities, and JSON config-file loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fakes import FakeEngine, make_entities
from umbryn_mcp.config import Config
from umbryn_mcp.errors import LowConfidenceError
from umbryn_mcp.redactor import Redactor


# --- Per-entity thresholds --------------------------------------------------
def test_per_entity_threshold_blocks_below_its_own_bar() -> None:
    text = "call 555-000-1234 now"
    engine = FakeEngine(make_entities(text, ("PHONE_NUMBER", 5, 17, 0.6)))
    # Global bar 0.5 would pass a 0.6 phone; a per-entity bar of 0.8 blocks it.
    redactor = Redactor(engine, min_confidence=0.5, entity_thresholds={"PHONE_NUMBER": 0.8})
    with pytest.raises(LowConfidenceError):
        redactor.redact(text)


def test_per_entity_threshold_only_affects_its_type() -> None:
    text = "a@b.co and 555-000-1234"
    engine = FakeEngine(
        make_entities(text, ("EMAIL_ADDRESS", 0, 4, 0.6), ("PHONE_NUMBER", 11, 23, 0.6))
    )
    # Raise only the phone bar; the 0.6 email must still redact fine.
    redactor = Redactor(engine, min_confidence=0.5, entity_thresholds={"PHONE_NUMBER": 0.9})
    with pytest.raises(LowConfidenceError):
        redactor.redact(text)
    # And with the phone removed, the email alone passes.
    email_only = FakeEngine(make_entities("a@b.co", ("EMAIL_ADDRESS", 0, 4, 0.6)))
    result = Redactor(
        email_only, min_confidence=0.5, entity_thresholds={"PHONE_NUMBER": 0.9}
    ).redact("a@b.co")
    assert "[EMAIL_ADDRESS_1]" in result.redacted_text


def test_per_entity_threshold_can_lower_the_bar() -> None:
    text = "ip 10.0.0.1 here"
    engine = FakeEngine(make_entities(text, ("IP_ADDRESS", 3, 11, 0.4)))
    # Global 0.5 would block a 0.4 hit; a 0.35 per-entity bar lets it through.
    redactor = Redactor(engine, min_confidence=0.5, entity_thresholds={"IP_ADDRESS": 0.35})
    result = redactor.redact(text)
    assert "[IP_ADDRESS_1]" in result.redacted_text


def test_entity_threshold_below_detection_floor_is_rejected() -> None:
    with pytest.raises(ValueError, match="detection_floor <= threshold"):
        Redactor(FakeEngine(), detection_floor=0.4, entity_thresholds={"NPI": 0.2})


# --- Disabled entities ------------------------------------------------------
def test_disabled_entity_is_not_redacted() -> None:
    text = "visit http://x.io and a@b.co"
    engine = FakeEngine(
        make_entities(text, ("URL", 6, 16, 0.6), ("EMAIL_ADDRESS", 21, 28, 0.9))
    )
    redactor = Redactor(engine, disabled_entities=frozenset({"URL"}))
    result = redactor.redact(text)
    assert "http://x.io" in result.redacted_text  # URL left intact
    assert "[EMAIL_ADDRESS_1]" in result.redacted_text


def test_disabled_entity_absent_from_detect() -> None:
    text = "visit http://x.io"
    engine = FakeEngine(make_entities(text, ("URL", 6, 17, 0.6)))
    redactor = Redactor(engine, disabled_entities=frozenset({"URL"}))
    assert redactor.detect(text).entities == ()


def test_disabling_a_type_suppresses_its_low_confidence_block() -> None:
    # A disabled type is dropped before the trust gate, so it can't fail closed.
    text = "noise 10.0.0.1"
    engine = FakeEngine(make_entities(text, ("IP_ADDRESS", 6, 14, 0.4)))
    redactor = Redactor(engine, min_confidence=0.5, disabled_entities=frozenset({"IP_ADDRESS"}))
    result = redactor.redact(text)
    assert result.redacted_text == text  # nothing redacted, nothing blocked


# --- JSON config file -------------------------------------------------------
def _write(tmp_path: Path, data: dict) -> str:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_config_file_supplies_structured_settings(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        {
            "engine": "regex",
            "min_confidence": 0.6,
            "entity_thresholds": {"PHONE_NUMBER": 0.8},
            "disabled_entities": ["URL"],
        },
    )
    cfg = Config.load({"UMBRYN_CONFIG": path})
    assert cfg.engine == "regex"
    assert cfg.min_confidence == 0.6
    assert cfg.entity_thresholds == {"PHONE_NUMBER": 0.8}
    assert cfg.disabled_entities == frozenset({"URL"})


def test_env_overrides_config_file_scalars(tmp_path: Path) -> None:
    path = _write(tmp_path, {"engine": "regex", "min_confidence": 0.6})
    cfg = Config.load({"UMBRYN_CONFIG": path, "UMBRYN_MIN_CONFIDENCE": "0.9"})
    assert cfg.min_confidence == 0.9  # env wins
    assert cfg.engine == "regex"  # file value kept where env is silent


def test_missing_config_file_fails_closed() -> None:
    with pytest.raises(ValueError, match="not found"):
        Config.load({"UMBRYN_CONFIG": "/no/such/file.json"})


def test_malformed_config_file_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        Config.load({"UMBRYN_CONFIG": str(path)})


def test_non_object_config_file_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "arr.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        Config.load({"UMBRYN_CONFIG": str(path)})


def test_bad_entity_threshold_value_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, {"entity_thresholds": {"NPI": 1.5}})
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        Config.load({"UMBRYN_CONFIG": path})


def test_disabled_entities_must_be_string_list(tmp_path: Path) -> None:
    path = _write(tmp_path, {"disabled_entities": "URL"})
    with pytest.raises(ValueError, match="array of entity_type"):
        Config.load({"UMBRYN_CONFIG": path})


def test_no_config_file_uses_defaults() -> None:
    cfg = Config.load({})
    assert cfg.engine == "auto"
    assert cfg.entity_thresholds == {}
    assert cfg.disabled_entities == frozenset()
