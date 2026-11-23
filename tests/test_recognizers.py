"""Unit tests for the dependency-free ruleset: checksums and regex detection."""

from __future__ import annotations

import time

import pytest

from umbryn_mcp import entities
from umbryn_mcp.checksums import (
    dea_is_valid,
    iban_is_valid,
    luhn_is_valid,
    nhs_is_valid,
    npi_is_valid,
    tfn_is_valid,
)
from umbryn_mcp.regex_engine import RegexEngine


# --- Check-digit validators -------------------------------------------------
@pytest.mark.parametrize("npi", ["1234567893", "1245319599", "1679576722", "1003000126"])
def test_valid_npis(npi: str) -> None:
    assert npi_is_valid(npi)


@pytest.mark.parametrize("npi", ["1710975306", "1234567890", "0000000000", "12345"])
def test_invalid_npis(npi: str) -> None:
    assert not npi_is_valid(npi)


def test_dea_checksum() -> None:
    assert dea_is_valid("AB1234563")
    assert not dea_is_valid("AB1234560")
    assert not dea_is_valid("ZZ1234563")  # bad registrant-type letter


def test_luhn() -> None:
    assert luhn_is_valid("4111111111111111")
    assert luhn_is_valid("4111 1111 1111 1111")
    assert not luhn_is_valid("4111111111111112")


def test_iban_checksum() -> None:
    assert iban_is_valid("DE94123456780000001234")
    assert iban_is_valid("DE94 1234 5678 0000 0012 34")
    assert iban_is_valid("GB15ZZZZ01020300654321")
    assert iban_is_valid("NL02ABNA0123456789")
    assert not iban_is_valid("DE00123456780000001234")
    assert not iban_is_valid("DE94 1234")


@pytest.mark.parametrize("nhs", ["9434765919", "4010232137", "943 476 5919"])
def test_valid_nhs(nhs: str) -> None:
    assert nhs_is_valid(nhs)


@pytest.mark.parametrize("nhs", ["9434765918", "1234567890", "943476591"])
def test_invalid_nhs(nhs: str) -> None:
    # 1234567890 exercises the "check digit == 10" -> invalid branch.
    assert not nhs_is_valid(nhs)


@pytest.mark.parametrize("tfn", ["963258140", "963 258 140", "963-258-140"])
def test_valid_tfn(tfn: str) -> None:
    assert tfn_is_valid(tfn)


@pytest.mark.parametrize("tfn", ["963258141", "96325814", "9632581400"])
def test_invalid_tfn(tfn: str) -> None:
    assert not tfn_is_valid(tfn)


# --- RegexEngine detection --------------------------------------------------
def _types(engine: RegexEngine, text: str) -> set[str]:
    return {e.entity_type for e in engine.detect(text)}


def test_detects_email_without_context() -> None:
    assert entities.EMAIL_ADDRESS in _types(RegexEngine(), "reach me at a.b@c.io")


def test_npi_requires_valid_checksum() -> None:
    engine = RegexEngine()
    assert entities.NPI in _types(engine, "NPI 1234567893")
    # A 10-digit number that fails the checksum is not an NPI.
    assert entities.NPI not in _types(engine, "order 1234567890")


def test_iban_requires_valid_checksum() -> None:
    engine = RegexEngine()
    assert entities.IBAN_CODE in _types(engine, "Wire to IBAN DE94123456780000001234")
    assert entities.IBAN_CODE in _types(engine, "Wire to DE94 1234 5678 0000 0012 34")
    assert entities.IBAN_CODE not in _types(engine, "ref DE00123456780000001234 here")


def test_mrn_requires_context() -> None:
    engine = RegexEngine()
    assert entities.MEDICAL_RECORD_NUMBER not in _types(engine, "the code 1234567 shipped")
    assert entities.MEDICAL_RECORD_NUMBER in _types(engine, "Patient MRN: 1234567")


def test_bare_ssn_requires_context_but_dashed_does_not() -> None:
    engine = RegexEngine()
    assert entities.US_SSN not in _types(engine, "reference 078051120 here")
    assert entities.US_SSN in _types(engine, "SSN 078051120")
    assert entities.US_SSN in _types(engine, "078-05-1120")


def test_email_detected_inside_mailto() -> None:
    found = [
        e
        for e in RegexEngine().detect("write mailto:foo@bar.com now")
        if e.entity_type == entities.EMAIL_ADDRESS
    ]
    assert len(found) == 1
    assert found[0].text == "foo@bar.com"


def test_email_regex_is_not_redos_prone() -> None:
    # The vulnerable (unbounded, overlapping) domain pattern took multiple seconds
    # on this input; the bounded, label-structured pattern is linear (~20ms).
    engine = RegexEngine()
    pathological = "a" * 40000 + "@" + "b." * 20000
    start = time.perf_counter()
    engine.detect(pathological)
    assert time.perf_counter() - start < 2.0


def test_context_words_match_on_word_boundary() -> None:
    # "tel" inside "hotel" must NOT boost the phone score (0.6 base, not 0.95).
    (phone,) = [
        e
        for e in RegexEngine().detect("hotel 212-555-1234")
        if e.entity_type == entities.PHONE_NUMBER
    ]
    assert phone.score == pytest.approx(0.6)


def test_detection_is_deterministic() -> None:
    engine = RegexEngine()
    text = "MRN: 1234567 email a@b.co NPI 1234567893"
    first = engine.detect(text)
    second = engine.detect(text)
    assert [(e.entity_type, e.start, e.end, e.score) for e in first] == [
        (e.entity_type, e.start, e.end, e.score) for e in second
    ]


# --- New identifiers --------------------------------------------------------
def test_nhs_number_requires_context_and_checksum() -> None:
    engine = RegexEngine()
    assert entities.UK_NHS_NUMBER in _types(engine, "NHS number 9434765919")
    # Right shape, valid checksum, but no NHS context -> not flagged.
    assert entities.UK_NHS_NUMBER not in _types(engine, "order ref 9434765919 shipped")
    # In-context but a broken check digit -> not flagged.
    assert entities.UK_NHS_NUMBER not in _types(engine, "NHS number 9434765918")


def test_itin_detected_on_shape_but_only_in_valid_ranges() -> None:
    engine = RegexEngine()
    assert entities.US_ITIN in _types(engine, "ITIN 912-70-1234")
    # Group digits 69 fall in the 66-69 gap that the IRS never issues.
    assert entities.US_ITIN not in _types(engine, "code 912-69-1234")
    # A normal SSN (no 9 prefix) is not an ITIN.
    assert entities.US_ITIN not in _types(engine, "078-05-1120")


def test_canadian_sin_requires_context_and_luhn() -> None:
    engine = RegexEngine()
    assert entities.CANADA_SIN in _types(engine, "SIN 046-454-286")
    assert entities.CANADA_SIN not in _types(engine, "046-454-286")  # no context
    assert entities.CANADA_SIN not in _types(engine, "SIN 046-454-287")  # bad Luhn


def test_australian_tfn_requires_context_and_checksum() -> None:
    engine = RegexEngine()
    assert entities.AUSTRALIA_TFN in _types(engine, "TFN 963 258 140")
    assert entities.AUSTRALIA_TFN not in _types(engine, "963 258 140")  # no context
    assert entities.AUSTRALIA_TFN not in _types(engine, "TFN 963 258 141")  # bad mod-11


def test_medicare_hicn_needs_suffix_and_context() -> None:
    engine = RegexEngine()
    assert entities.MEDICARE_HICN in _types(engine, "Medicare 123-45-6789A")
    assert entities.MEDICARE_HICN not in _types(engine, "123-45-6789A")  # no context
    # No beneficiary-code suffix -> it's a plain SSN, not a HICN.
    assert entities.MEDICARE_HICN not in _types(engine, "Medicare 123-45-6789")


def test_drivers_license_is_anchored_on_its_label() -> None:
    engine = RegexEngine()
    (dl,) = [
        e
        for e in engine.detect("driver's license D1234567 on file")
        if e.entity_type == entities.US_DRIVERS_LICENSE
    ]
    assert dl.text == "D1234567"  # the number, not the "driver's license" label
    assert entities.US_DRIVERS_LICENSE in _types(engine, "DL: X0987654")
    # A bare token with no license label nearby is not flagged.
    assert entities.US_DRIVERS_LICENSE not in _types(engine, "the code X0987654 here")
    # The label with no digit-bearing token after it captures nothing.
    assert entities.US_DRIVERS_LICENSE not in _types(engine, "driver's license unavailable")
