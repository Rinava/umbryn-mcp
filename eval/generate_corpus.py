"""Generate a fully-synthetic, labeled PHI/PII corpus.

Every identifier here is randomly generated (valid check digits where they exist)
and every label is recorded by *construction*, so the gold spans are exact and no
real PHI is ever involved. Negative distractors — numbers that look like
identifiers but aren't (failed checksums, order numbers, ZIP codes, dates) — are
woven in as unlabeled text to measure precision honestly.

Deterministic: a fixed seed means the committed ``corpus.jsonl`` is reproducible.

Usage:
    python eval/generate_corpus.py            # writes eval/corpus.jsonl
    python eval/generate_corpus.py --n 300    # more documents
"""

from __future__ import annotations

import argparse
import json
import random
import string
from pathlib import Path

from umbryn_mcp import entities
from umbryn_mcp.checksums import iban_is_valid, luhn_is_valid, nhs_is_valid

_MBI_L = "ACDEFGHJKMNPQRTUVWXY"
_MBI_AN = _MBI_L + string.digits


# --- valid-identifier generators -------------------------------------------
def _npi_check(base9: str) -> str:
    s = "80840" + base9
    total = 0
    for i, ch in enumerate(reversed(s)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - (total % 10)) % 10)


def make_npi(rng: random.Random) -> str:
    base = str(rng.randint(1, 2)) + "".join(str(rng.randint(0, 9)) for _ in range(8))
    return base + _npi_check(base)


def make_dea(rng: random.Random) -> str:
    letters = rng.choice("ABCFGM") + rng.choice(string.ascii_uppercase)
    d = [rng.randint(0, 9) for _ in range(6)]
    chk = (d[0] + d[2] + d[4] + 2 * (d[1] + d[3] + d[5])) % 10
    return letters + "".join(map(str, d)) + str(chk)


def make_mbi(rng: random.Random) -> str:
    return "".join(
        [
            str(rng.randint(1, 9)),
            rng.choice(_MBI_L),
            rng.choice(_MBI_AN),
            str(rng.randint(0, 9)),
            rng.choice(_MBI_L),
            rng.choice(_MBI_AN),
            str(rng.randint(0, 9)),
            rng.choice(_MBI_L),
            rng.choice(_MBI_L),
            str(rng.randint(0, 9)),
            str(rng.randint(0, 9)),
        ]
    )


def make_ssn(rng: random.Random) -> str:
    area = rng.randint(1, 899)
    while area == 666:
        area = rng.randint(1, 899)
    return f"{area:03d}-{rng.randint(1, 99):02d}-{rng.randint(1, 9999):04d}"


def make_cc(rng: random.Random) -> str:
    digits = [4] + [rng.randint(0, 9) for _ in range(14)]
    total = 0
    for i, d in enumerate(reversed([*digits, 0])):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    digits.append((10 - (total % 10)) % 10)
    s = "".join(map(str, digits))
    return " ".join(s[i : i + 4] for i in range(0, 16, 4))


def make_phone(rng: random.Random) -> str:
    return f"{rng.randint(200, 999)}-{rng.randint(200, 999)}-{rng.randint(1000, 9999)}"


def make_email(rng: random.Random) -> str:
    first = rng.choice(["alex", "sam", "jordan", "casey", "riley", "morgan"])
    last = rng.choice(["ng", "reyes", "khan", "obrien", "diaz", "park"])
    dom = rng.choice(["example.com", "clinic.org", "health.net"])
    return f"{first}.{last}@{dom}"


def make_ip(rng: random.Random) -> str:
    return ".".join(str(rng.randint(1, 254)) for _ in range(4))


def make_mrn(rng: random.Random) -> str:
    return str(rng.randint(100000, 9999999))


def make_clia(rng: random.Random) -> str:
    return f"{rng.randint(10, 99)}D{rng.randint(1000000, 9999999)}"


def make_iban(rng: random.Random) -> str:
    # Synthetic DE-style IBAN: 18-digit numeric BBAN with correct mod-97 check digits.
    bban = "".join(str(rng.randint(0, 9)) for _ in range(18))
    rearranged = bban + "DE00"
    digits = "".join(ch if ch.isdigit() else str(ord(ch) - 55) for ch in rearranged)
    check = 98 - (int(digits) % 97)
    return f"DE{check:02d}{bban}"


def make_invalid_iban(rng: random.Random) -> str:
    # IBAN-shaped distractor that must fail the mod-97 check. The ``DE00`` check
    # digits never occur in a real IBAN, but a random 18-digit body still passes
    # mod-97 about 1% of the time, so resample until it genuinely fails — an
    # accidentally-valid IBAN here would be a real detection, not a distractor.
    while True:
        candidate = f"DE00{rng.randint(10**17, 10**18 - 1)}"
        if not iban_is_valid(candidate):
            return candidate


# ITIN group digits fall only in the IRS-issued ranges.
_ITIN_GROUPS = [*range(50, 66), *range(70, 89), *range(90, 93), *range(94, 100)]


def make_itin(rng: random.Random) -> str:
    return f"9{rng.randint(0, 99):02d}-{rng.choice(_ITIN_GROUPS):02d}-{rng.randint(0, 9999):04d}"


def make_nhs(rng: random.Random) -> str:
    # 10 digits with a valid mod-11 check digit, printed unbroken to avoid a
    # 3-3-4 grouping that would also match the phone recognizer. Some 9-digit
    # bases have no valid check digit (remainder 10), so resample those.
    while True:
        base = "".join(str(rng.randint(0, 9)) for _ in range(9))
        for c in range(10):
            if nhs_is_valid(base + str(c)):
                return base + str(c)


def make_sin(rng: random.Random) -> str:
    # 9 Luhn-valid digits, printed in the distinctive 3-3-3 grouping.
    base = "".join(str(rng.randint(0, 9)) for _ in range(8))
    for c in range(10):
        if luhn_is_valid(base + str(c)):
            s = base + str(c)
            return f"{s[:3]}-{s[3:6]}-{s[6:]}"
    raise AssertionError("unreachable: some check digit always yields a valid Luhn number")


def make_invalid_sin(rng: random.Random) -> str:
    while True:
        s = "".join(str(rng.randint(0, 9)) for _ in range(9))
        if not luhn_is_valid(s):
            return f"{s[:3]}-{s[3:6]}-{s[6:]}"


def make_invalid_nhs(rng: random.Random) -> str:
    while True:
        s = "".join(str(rng.randint(0, 9)) for _ in range(10))
        if not nhs_is_valid(s):
            return s


def make_hicn(rng: random.Random) -> str:
    # 9-digit SSN body + a beneficiary-identification-code letter, printed
    # unbroken so the SSN body alone doesn't also match the dashed-SSN rule.
    area = rng.randint(1, 899)
    while area == 666:
        area = rng.randint(1, 899)
    body = f"{area:03d}{rng.randint(1, 99):02d}{rng.randint(1, 9999):04d}"
    return body + rng.choice(string.ascii_uppercase)


def make_dl(rng: random.Random) -> str:
    # A letter + 7 digits — a plausible license token that carries a digit (so
    # the recognizer's digit lookahead fires). No national format or checksum.
    return rng.choice(string.ascii_uppercase) + "".join(str(rng.randint(0, 9)) for _ in range(7))


def make_passport(rng: random.Random) -> str:
    # Generate either a legacy 9-digit passport number or a Next Generation
    # passport number (one letter + eight digits). Entirely synthetic.
    if rng.random() < 0.5:
        return "".join(str(rng.randint(0, 9)) for _ in range(9))
    return rng.choice(string.ascii_uppercase) + "".join(str(rng.randint(0, 9)) for _ in range(8))


# --- a document builder that records exact spans ---------------------------
class _Doc:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.ents: list[dict] = []
        self.pos = 0

    def lit(self, text: str) -> _Doc:
        self.parts.append(text)
        self.pos += len(text)
        return self

    def ent(self, entity_type: str, value: str) -> _Doc:
        start = self.pos
        self.parts.append(value)
        self.pos += len(value)
        self.ents.append({"entity_type": entity_type, "start": start, "end": self.pos})
        return self

    def render(self) -> dict:
        return {"text": "".join(self.parts), "entities": self.ents}


# Negative distractors: look-alikes that must NOT be flagged.
def _distractor(rng: random.Random) -> str:
    return rng.choice(
        [
            f"order #{rng.randint(1000000000, 1999999999)}",  # 10 digits, fails NPI checksum
            f"ZIP {rng.randint(10000, 99999)}",
            f"seen on {rng.randint(2020, 2025)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            f"room {rng.randint(100, 999)}",
            f"dose {rng.randint(5, 500)} mg",
            f"ref {make_invalid_iban(rng)}",
            # In-context but checksum-failing: must NOT be flagged (tests the validator).
            f"NHS ref {make_invalid_nhs(rng)}",
            f"SIN {make_invalid_sin(rng)}",
        ]
    )


def _document(rng: random.Random) -> dict:
    d = _Doc()
    d.lit("Patient seen by provider ").ent(entities.NPI, make_npi(rng))
    d.lit(". MRN: ").ent(entities.MEDICAL_RECORD_NUMBER, make_mrn(rng))
    d.lit(f". {_distractor(rng)}. ")
    if rng.random() < 0.7:
        d.lit("SSN ").ent(entities.US_SSN, make_ssn(rng)).lit(". ")
    if rng.random() < 0.6:
        d.lit("Medicare MBI ").ent(entities.MEDICARE_BENEFICIARY_ID, make_mbi(rng)).lit(". ")
    if rng.random() < 0.5:
        d.lit("Prescriber DEA ").ent(entities.DEA_NUMBER, make_dea(rng)).lit(". ")
    if rng.random() < 0.5:
        d.lit("Lab CLIA ").ent(entities.CLIA_NUMBER, make_clia(rng)).lit(". ")
    if rng.random() < 0.7:
        d.lit("Contact ").ent(entities.EMAIL_ADDRESS, make_email(rng))
        d.lit(" or phone ").ent(entities.PHONE_NUMBER, make_phone(rng)).lit(". ")
    if rng.random() < 0.4:
        d.lit("Card on file ").ent(entities.CREDIT_CARD, make_cc(rng)).lit(". ")
    if rng.random() < 0.4:
        d.lit("IBAN ").ent(entities.IBAN_CODE, make_iban(rng)).lit(". ")
    if rng.random() < 0.3:
        d.lit("Portal IP ").ent(entities.IP_ADDRESS, make_ip(rng)).lit(". ")
    if rng.random() < 0.5:
        d.lit("ITIN ").ent(entities.US_ITIN, make_itin(rng)).lit(". ")
    if rng.random() < 0.5:
        d.lit("NHS number ").ent(entities.UK_NHS_NUMBER, make_nhs(rng)).lit(". ")
    if rng.random() < 0.4:
        d.lit("SIN ").ent(entities.CANADA_SIN, make_sin(rng)).lit(". ")
    if rng.random() < 0.4:
        d.lit("Medicare HICN ").ent(entities.MEDICARE_HICN, make_hicn(rng)).lit(". ")
    if rng.random() < 0.4:
        d.lit("driver's license ").ent(entities.US_DRIVERS_LICENSE, make_dl(rng)).lit(". ")
    if rng.random() < 0.4:
        d.lit("driver's license ").ent(entities.US_DRIVERS_LICENSE, make_dl(rng)).lit(". ")

    if rng.random() < 0.4:
        d.lit("Passport number ").ent(
            entities.US_PASSPORT,
            make_passport(rng),
        ).lit(". ")
    d.lit(f"{_distractor(rng)}.")
    return d.render()


def generate(n: int, seed: int = 20260703) -> list[dict]:
    rng = random.Random(seed)
    return [_document(rng) for _ in range(n)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=200, help="number of documents")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "corpus.jsonl")
    args = parser.parse_args()

    docs = generate(args.n)
    with args.out.open("w", encoding="utf-8") as fh:
        for doc in docs:
            fh.write(json.dumps(doc) + "\n")
    n_ents = sum(len(d["entities"]) for d in docs)
    print(f"wrote {len(docs)} documents, {n_ents} labeled entities -> {args.out}")


if __name__ == "__main__":
    main()
