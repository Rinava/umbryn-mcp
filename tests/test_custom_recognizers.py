"""User-defined recognizers loaded from config: parsing, validation, wiring."""

from __future__ import annotations

import re

import pytest

from umbryn_mcp import entities
from umbryn_mcp.config import Config
from umbryn_mcp.factory import build_engine, build_redactor
from umbryn_mcp.recognizers import Recognizer

EMP = {
    "entity_type": "EMPLOYEE_ID",
    "regex": r"\bEMP-\d{6}\b",
    "base_score": 0.85,
}


# --- Recognizer.from_dict validation ----------------------------------------
def test_from_dict_happy_path() -> None:
    rec = Recognizer.from_dict(
        {
            "entity_type": "EMPLOYEE_ID",
            "regex": r"\bEMP-\d{6}\b",
            "base_score": 0.8,
            "context": ["employee", "badge"],
            "context_required": True,
            "group": 0,
            "flags": ["IGNORECASE", "MULTILINE"],
        }
    )
    assert rec.entity_type == "EMPLOYEE_ID"
    assert rec.context == ("employee", "badge")
    assert rec.context_required is True
    assert rec.flags == re.IGNORECASE | re.MULTILINE


def test_from_dict_defaults() -> None:
    rec = Recognizer.from_dict(EMP)
    assert rec.context == ()
    assert rec.context_required is False
    assert rec.validator is None
    assert rec.flags == re.IGNORECASE  # omitted flags default to case-insensitive


def test_from_dict_named_validator_resolves() -> None:
    rec = Recognizer.from_dict({**EMP, "validator": "luhn"})
    assert rec.validator is not None
    assert rec.validator("4111111111111111") is True


_BASE = {"entity_type": "X", "regex": "x", "base_score": 0.5}


@pytest.mark.parametrize(
    ("spec", "match"),
    [
        ({"regex": "x", "base_score": 0.5}, "entity_type"),
        ({"entity_type": "X", "base_score": 0.5}, "regex"),
        ({"entity_type": "X", "regex": "x"}, "base_score"),
        ({**_BASE, "base_score": 2}, r"\[0, 1\]"),
        ({**_BASE, "validator": "evil"}, "must be one of"),
        ({**_BASE, "regex": "("}, "failed to compile"),
        ({**_BASE, "flags": ["NOPE"]}, "unknown regex flag"),
        ({**_BASE, "context": "employee"}, "array of strings"),
        ({**_BASE, "group": -1}, "non-negative integer"),
    ],
)
def test_from_dict_rejects_malformed(spec: dict, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        Recognizer.from_dict(spec)


def test_from_dict_does_not_accept_a_callable_validator() -> None:
    # The whole point of naming validators: config can't smuggle in code.
    with pytest.raises(ValueError, match="must be one of"):
        Recognizer.from_dict({**EMP, "validator": lambda s: True})


# --- Wiring through the factory ---------------------------------------------
def test_custom_recognizer_detected_end_to_end() -> None:
    text = "ticket for EMP-004521 opened"
    redactor = build_redactor(Config(engine="regex", recognizers=(EMP,)))
    result = redactor.redact(text)
    assert "[EMPLOYEE_ID_1]" in result.redacted_text
    assert redactor.restore(result.redacted_text, result.token_map) == text


def test_custom_recognizer_named_validator_drops_invalid() -> None:
    spec = {
        "entity_type": "LOYALTY_CARD",
        "regex": r"\b\d{16}\b",
        "base_score": 0.85,
        "validator": "luhn",
    }
    engine = build_engine(Config(engine="regex", recognizers=(spec,)))
    types = {e.entity_type for e in engine.detect("card 4111111111111111")}
    assert "LOYALTY_CARD" in types  # Luhn-valid
    assert "LOYALTY_CARD" not in {e.entity_type for e in engine.detect("card 4111111111111112")}


def test_custom_recognizer_context_required() -> None:
    spec = {
        "entity_type": "CASE_ID",
        "regex": r"\b\d{8}\b",
        "base_score": 0.4,
        "context": ["case"],
        "context_required": True,
    }
    engine = build_engine(Config(engine="regex", recognizers=(spec,)))
    assert "CASE_ID" not in {e.entity_type for e in engine.detect("the number 12345678")}
    assert "CASE_ID" in {e.entity_type for e in engine.detect("case 12345678")}


def test_malformed_custom_recognizer_fails_at_build() -> None:
    bad = {"entity_type": "X", "regex": "(", "base_score": 0.5}
    with pytest.raises(ValueError, match="failed to compile"):
        build_engine(Config(engine="regex", recognizers=(bad,)))


def test_custom_recognizers_coexist_with_builtins() -> None:
    engine = build_engine(Config(engine="regex", recognizers=(EMP,)))
    types = {e.entity_type for e in engine.detect("EMP-004521 and a@b.co")}
    assert "EMPLOYEE_ID" in types
    assert entities.EMAIL_ADDRESS in types
