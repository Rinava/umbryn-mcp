"""Canonical entity-type names, shared by every engine.

Keeping one taxonomy means the regex engine and the Presidio engine emit the
*same* ``entity_type`` strings, so placeholders, config, and the eval harness
line up regardless of which backend detected a span.
"""

from __future__ import annotations

from typing import Final

# --- Standard PII -----------------------------------------------------------
PERSON: Final = "PERSON"
LOCATION: Final = "LOCATION"
EMAIL_ADDRESS: Final = "EMAIL_ADDRESS"
PHONE_NUMBER: Final = "PHONE_NUMBER"
US_SSN: Final = "US_SSN"
CREDIT_CARD: Final = "CREDIT_CARD"
IP_ADDRESS: Final = "IP_ADDRESS"
URL: Final = "URL"
DATE_TIME: Final = "DATE_TIME"

# --- HIPAA-relevant clinical identifiers ------------------------------------
NPI: Final = "NPI"  # National Provider Identifier (Luhn + 80840)
DEA_NUMBER: Final = "DEA_NUMBER"  # Drug Enforcement Administration number (checksum)
MEDICAL_RECORD_NUMBER: Final = "MEDICAL_RECORD_NUMBER"  # MRN, context-gated
MEDICARE_BENEFICIARY_ID: Final = "MEDICARE_BENEFICIARY_ID"  # MBI, position-typed
CLIA_NUMBER: Final = "CLIA_NUMBER"  # Clinical lab identifier

# --- Financial identifiers --------------------------------------------------
IBAN_CODE: Final = "IBAN_CODE"  # International Bank Account Number (mod-97 / ISO 7064)
