# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **IBAN** detection (`IBAN_CODE`), validated with the mod-97 / ISO 7064 check
  digit, in both the default and Presidio engines.

### Changed
- **BREAKING — renamed the project** from `phi-redact-mcp` to **`umbryn-mcp`**. The
  distribution and console script are now `umbryn-mcp` (was `phi-redact-mcp`), the
  import package is `umbryn_mcp` (was `phi_mcp`), and the environment-variable
  prefix is `UMBRYN_` (was `PHI_MCP_`). Update MCP client configs, any
  `import phi_mcp`, and any `PHI_MCP_*` env vars accordingly. The `0.1.0` release
  remains on PyPI under the old `phi-redact-mcp` name.

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
- Environment-based configuration (`UMBRYN_ENGINE`, `UMBRYN_MIN_CONFIDENCE`,
  `UMBRYN_DETECTION_FLOOR`, `UMBRYN_MAX_INPUT_CHARS`, `UMBRYN_SPACY_MODEL`).
- Synthetic labeled eval harness with per-entity precision/recall and a quality
  gate; fast invariant test suite; stdio + Presidio integration smoke tests.
- Docs: architecture, threat model, contributing guide, example client configs.

[Unreleased]: https://github.com/Rinava/umbryn-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Rinava/umbryn-mcp/releases/tag/v0.1.0
