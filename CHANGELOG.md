# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **PEP 561 typing marker**: ship a `py.typed` file so downstream users who
  `pip install umbryn-mcp` actually receive the package's inline type
  information under mypy/pyright. The distribution already advertised
  `Typing :: Typed`, but the marker was missing, so type checkers treated the
  package as untyped.
### Added
- **Published benchmark**: per-entity precision/recall for the default engine in
  the README, reproducible via `python eval/run_eval.py --markdown`. The eval
  corpus now exercises every shipped recognizer (ITIN, NHS, SIN, HICN, driver's
  license), with checksum-failing look-alikes woven in as distractors, and the
  CI quality gate now also covers `MEDICARE_HICN` and `US_DRIVERS_LICENSE`.

## [0.2.0] - 2026-07-06

### Added
- **JSON config file** (`UMBRYN_CONFIG`) as a second configuration surface for
  the settings that don't fit a flat environment variable. Environment variables
  still override the file for scalar values. A malformed file fails closed at
  startup. See [`examples/umbryn_config.json`](examples/umbryn_config.json).
- **Per-entity trust thresholds** (`entity_thresholds`) that override
  `min_confidence` for a specific entity type, and **`disabled_entities`** to
  drop a type entirely (never detected or redacted).
- **Custom recognizers from config** (`recognizers`): define your own regex +
  context + optional check digit without forking. A `validator` is named by
  string against a fixed registry (`luhn`, `npi`, `dea`, `iban`, `nhs`), so a
  config file supplies data, never code.
- **Structured audit log** (`UMBRYN_AUDIT_LOG`): one record per `redact` call
  with redaction counts, types, and block reasons — never the raw values.
- **New recognizers**: US ITIN (`US_ITIN`), UK NHS number (`UK_NHS_NUMBER`,
  mod-11), Canadian SIN (`CANADA_SIN`, Luhn), legacy Medicare HICN
  (`MEDICARE_HICN`), and US driver's license (`US_DRIVERS_LICENSE`).

## [0.1.2] - 2026-07-06

### Fixed
- **MCP Registry publishing**: corrected the `io.github.Rinava` namespace case
  (GitHub OIDC is case-sensitive) and the matching `mcp-name` marker in the
  README, so the registry's PyPI-ownership check passes. No changes to the
  package itself; `0.1.1` is functionally identical but was only published to
  PyPI, not the registry.

## [0.1.1] - 2026-07-06

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

[Unreleased]: https://github.com/Rinava/umbryn-mcp/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Rinava/umbryn-mcp/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/Rinava/umbryn-mcp/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Rinava/umbryn-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Rinava/umbryn-mcp/releases/tag/v0.1.0
