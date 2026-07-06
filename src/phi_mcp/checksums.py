"""Check-digit validators for identifiers that carry one.

A regex tells you a string *looks* like an NPI or a credit card; a checksum
tells you it plausibly *is* one. Running these after the regex removes the vast
majority of false positives (random 10-digit numbers, ZIP+phone fragments, etc.),
which is what lets us assign these entities a high confidence score.

These algorithms were cross-checked against canonical worked examples:
NPI ``1234567893`` (CMS), DEA ``AB1234563``, ISO 13616 IBAN examples,
and the Luhn spec.
"""

from __future__ import annotations

import re

_DIGITS = re.compile(r"\d")


def luhn_is_valid(number: str) -> bool:
    """Standard Luhn (mod-10) validation. Used for credit-card numbers.

    Non-digit characters (spaces, dashes) are ignored so it works on formatted
    input. Requires at least two digits.
    """
    digits = [int(c) for c in _DIGITS.findall(number)]
    if len(digits) < 2:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def npi_is_valid(npi: str) -> bool:
    """Validate a 10-digit National Provider Identifier.

    The check digit is a Luhn computed over the 9-digit base with the constant
    ``80840`` prefix (80 = health, 840 = USA) prepended.
    """
    if len(npi) != 10 or not npi.isdigit():
        return False
    base = "80840" + npi[:9]
    total = 0
    for i, ch in enumerate(reversed(base)):
        d = int(ch)
        if i % 2 == 0:  # rightmost digit doubled
            d *= 2
            if d > 9:
                d -= 9
        total += d
    check = (10 - (total % 10)) % 10
    return check == int(npi[9])


#: DEA first letter: registrant type. Second char: last-name initial or ``9``.
_DEA_RE = re.compile(r"[ABCDEFGHJKLMPRSTUX][A-Z9]\d{7}")
_IBAN_RE = re.compile(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}")


def dea_is_valid(dea: str) -> bool:
    """Validate a DEA registration number (2 letters + 7 digits).

    Check digit = ``(d1+d3+d5) + 2*(d2+d4+d6)`` mod 10, compared to digit 7.
    """
    dea = dea.upper()
    if not _DEA_RE.fullmatch(dea):
        return False
    d = [int(c) for c in dea[2:]]
    total = (d[0] + d[2] + d[4]) + 2 * (d[1] + d[3] + d[5])
    return total % 10 == d[6]


def iban_is_valid(iban: str) -> bool:
    """Validate an IBAN via the mod-97 (ISO 7064) check.

    Spaces from printed grouping are stripped before validation. A valid IBAN
    leaves a remainder of 1 after moving the first four chars to the end and
    expanding letters to numbers (A=10 .. Z=35).
    """
    iban = iban.replace(" ", "").upper()
    if not (15 <= len(iban) <= 34) or not _IBAN_RE.fullmatch(iban):
        return False
    rearranged = iban[4:] + iban[:4]
    digits = "".join(ch if ch.isdigit() else str(ord(ch) - 55) for ch in rearranged)
    return int(digits) % 97 == 1
