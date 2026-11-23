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
MEDICARE_HICN: Final = "MEDICARE_HICN"  # Legacy Health Insurance Claim Number (SSN + BIC)
CLIA_NUMBER: Final = "CLIA_NUMBER"  # Clinical lab identifier

# --- Government / taxpayer identifiers ---------------------------------------
US_ITIN: Final = "US_ITIN"  # Individual Taxpayer Identification Number (9XX-range)
UK_NHS_NUMBER: Final = "UK_NHS_NUMBER"  # UK National Health Service number (mod-11)
AUSTRALIA_TFN: Final = "AUSTRALIA_TFN"  # Australian Tax File Number (mod-11 weighted)
CANADA_SIN: Final = "CANADA_SIN"  # Canadian Social Insurance Number (Luhn)
US_DRIVERS_LICENSE: Final = "US_DRIVERS_LICENSE"  # Driver's license, context-anchored

# --- Financial identifiers --------------------------------------------------
IBAN_CODE: Final = "IBAN_CODE"  # International Bank Account Number (mod-97 / ISO 7064)
