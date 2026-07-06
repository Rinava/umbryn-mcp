# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **IBAN** detection (`IBAN_CODE`), validated with the mod-97 / ISO 7064 check
  digit, in both the default and Presidio engines.

## [0.1.0] - 2026-07-03

Initial release.

### Added
- MCP server over stdio exposing three tools: `redact`, `restore`, `detect`.
- Fail-closed redaction core: engine errors and any below-threshold detection
  return a typed error and never leak text. Two configurable thresholds
  (`detection_floor`, `min_confidence`).
- Reversible, collision-proof typed placeholders with a property-tested
  `restore(redact(x)) == x` guarantee, and deterministic overlap resolution.
- Default **zero-dependency** regex + checksum engine covering standard PII
  (email, phone, SSN, credit card, IP, URL) and HIPAA identifiers: NPI and DEA
  (check-digit validated), Medicare MBI (position-typed), MRN (context-anchored),
  and CLIA lab numbers.
- Optional `[presidio]` engine adding `PERSON`/`LOCATION` NER via Microsoft
  Presidio + spaCy, with custom MRN/CLIA recognizers and entity-name
  normalization.
- Environment-based configuration (`PHI_MCP_ENGINE`, `PHI_MCP_MIN_CONFIDENCE`,
  `PHI_MCP_DETECTION_FLOOR`, `PHI_MCP_MAX_INPUT_CHARS`, `PHI_MCP_SPACY_MODEL`).
- Synthetic labeled eval harness with per-entity precision/recall and a quality
  gate; fast invariant test suite; stdio + Presidio integration smoke tests.
- Docs: architecture, threat model, contributing guide, example client configs.

[Unreleased]: https://github.com/Rinava/phi-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Rinava/phi-mcp/releases/tag/v0.1.0
