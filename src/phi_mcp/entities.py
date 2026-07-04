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

#: Everything the project can name. Used for validation and docs.
ALL_ENTITIES: Final = (
    PERSON,
    LOCATION,
    EMAIL_ADDRESS,
    PHONE_NUMBER,
    US_SSN,
    CREDIT_CARD,
    IP_ADDRESS,
    URL,
    DATE_TIME,
    NPI,
    DEA_NUMBER,
    MEDICAL_RECORD_NUMBER,
    MEDICARE_BENEFICIARY_ID,
    CLIA_NUMBER,
)

#: Presidio's built-in entity names -> our canonical names. Anything not listed
#: here is passed through unchanged (our custom recognizers already emit
#: canonical names).
PRESIDIO_ENTITY_MAP: Final = {
    "US_NPI": NPI,
    "US_MBI": MEDICARE_BENEFICIARY_ID,
    "MEDICAL_LICENSE": DEA_NUMBER,
}
