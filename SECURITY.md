# Security Policy

`phi-redact-mcp` sits on a data-privacy boundary, so security reports are taken
seriously and handled with priority.

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Report privately using **[GitHub Private Vulnerability Reporting](https://github.com/Rinava/phi-mcp/security/advisories/new)**
(Security → Report a vulnerability). If that is unavailable, email
**laramateoco@gmail.com** with details.

Please include:

- a description of the issue and its impact (e.g. a class of PHI that leaks past
  redaction, a fail-closed bypass, an input that crashes the server),
- a **synthetic** reproduction — never include real PHI/PII in a report,
- affected version(s) and configuration (engine, thresholds).

You can expect an initial acknowledgement within a few days. We'll work with you
on a fix and coordinate disclosure; credit is given unless you prefer otherwise.

## What counts as a security issue

- Redaction that leaks a value it should have caught, in a way that suggests a
  systematic flaw (not a single tuning-level false negative — those are normal
  detector limits; see the [threat model](docs/THREAT_MODEL.md)).
- Any path where `redact` returns text on an error or low-confidence condition
  (a fail-closed bypass).
- Unexpected third-party network egress from the default engine.
- Denial of service via crafted input.

## Supported versions

The project is pre-1.0; security fixes land on the latest released version.
Pin a version and watch releases for updates.

| Version | Supported |
|---------|-----------|
| latest `0.x` | ✅ |
| older | ❌ |
