# Roadmap

Where this is headed, and where you can help. Items marked **good first issue**
are self-contained and beginner-friendly. Nothing here is a promise — priorities
follow contributor interest. Open an issue to discuss before starting something big.

## Shipped (v0.1)

- ✅ `redact` / `restore` / `detect` over stdio
- ✅ Fail-closed core (errors + low-confidence both block)
- ✅ Zero-dependency regex + checksum engine (NPI, DEA, MBI, MRN, CLIA + standard PII)
- ✅ Optional Presidio engine (PERSON/LOCATION NER)
- ✅ Property-tested reversibility, synthetic eval harness

## Next (P1) — fast follow

- ✅ **Config file** — per-entity thresholds and enabled/disabled entities via a
  JSON config file, not just env vars.
- ✅ **Custom recognizers at startup** — load user-defined regex + context
  recognizers from config without code changes.
- ✅ **Structured audit log** — counts and types of redactions (never raw values).
- **More recognizers** — US passport, insurance member IDs, more international
  identifiers. (ITIN, UK NHS, Canadian SIN, Medicare HICN, and US driver's
  license have shipped.) *(good first issue — see [CONTRIBUTING](CONTRIBUTING.md))*
- **Remote transport** — streamable-HTTP transport for hosted/multi-client use.
- **Published benchmark** — precision/recall on a public synthetic PHI corpus in
  the README.
- **Coverage + release automation** — Codecov badge, tag-triggered PyPI + MCP
  Registry publish. *(partly scaffolded in `.github/workflows/`)*

## Later (P2) — bigger bets

- **Transparent proxy / gateway mode** — automatically scrub payloads flowing to
  downstream MCP servers or model providers, no explicit tool call. The core is
  already cleanly separable to support this.
- **De-identification modes** — format-preserving tokenization, pseudonymization,
  beyond reversible redaction.
- **Policy packs** — selectable HIPAA / GDPR / PCI rule sets at runtime.
- **Deployment templates** — Docker and other one-command deploys that keep the
  detection engine inside your infrastructure by default.

## Non-goals

- Claiming to make a system "HIPAA compliant" (see the [threat model](docs/THREAT_MODEL.md)).
- A hosted/managed SaaS. This is a self-hostable open-source library.
- General content moderation or secret scanning — scope is PHI/PII.
