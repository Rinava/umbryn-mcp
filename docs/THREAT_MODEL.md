# Threat model & honest limitations

This document states plainly what `umbryn-mcp` defends against, what it
assumes, and what it does **not** do. Read it before relying on the tool in any
setting where a leak matters.

## What it is

A **boundary control**: a set of MCP tools that detect and reversibly redact
PHI/PII in text so that only scrubbed text crosses to a model provider or other
downstream system. It is one control in a larger design — not a compliance
program.

## What it is *not*

**It does not make a system "HIPAA compliant."** HIPAA compliance is a property
of an entire system and organization — administrative, physical, and technical
safeguards; Business Associate Agreements; risk analysis; access control; audit;
training; breach procedures. A redaction library cannot supply any of those. Use
of this tool may be *part* of a compliant design, but this project makes **no
certification and no guarantee of compliance**, and nothing here is legal advice.
Talk to your privacy/compliance counsel.

It also does not: guarantee complete detection, de-identify beyond reversible
redaction (no format-preserving tokenization or k-anonymity), handle non-text
modalities (images, audio, structured DB rows), or act as a transparent proxy in
v1 (redaction happens through explicit tool calls you wire into your pipeline).

## Assets

- **Raw PHI/PII** in the input text (highest value).
- **The `token_map`** returned by `redact` — it contains original values and is
  as sensitive as the input.
- **Scrubbed text** — lower value, but may retain residual identifiers the
  detector missed.

## Trust boundary

```
        ┌─────────── you run and control this ───────────┐
input → │  MCP client → umbryn-mcp → detection engine │ → scrubbed text → model provider
        └─────────────────────────────────────────────────┘
                         ▲
                  token_map stays here
```

The server, the redaction core, and the detection engine all run **inside
infrastructure you control** (the default engine has no third-party
dependencies and makes no network calls at all). Only scrubbed text is intended
to leave the boundary. The `token_map` must never be sent to the model.

## Guarantees

- **Fail-closed.** On a detection engine error, or when any detection scores
  below the trust threshold, `redact` returns a typed error and **no redacted
  text**. Uncertainty blocks the request; it is never redact-what-we-can.
- **No third-party egress (default engine).** The regex engine is pure Python
  regex + arithmetic checksums — no spaCy, no downloads, no outbound calls. You
  can run it fully air-gapped and verify this by inspection.
- **Exact reversibility.** `restore(redact(x)) == x` for arbitrary input, proven
  by property-based tests.
- **Determinism.** Same input + same config ⇒ same output.

## Residual risks (what can still go wrong)

- **False negatives.** No detector catches everything. Names/addresses require
  the optional Presidio engine; even then, NER misses happen. Unusual identifier
  formats (institution-specific MRNs, non-US identifiers) may not match. **Do not
  treat redacted output as guaranteed PHI-free.** Evaluate on representative data
  and tune recognizers/thresholds for your domain.
- **The token map is sensitive.** It holds the original values. Store and
  transmit it with the same care as the raw input; never pass it to the model.
- **Presidio engine egress at setup.** Installing the `[presidio]` extra downloads
  a spaCy model over the network *once*. At detection time Presidio makes no
  third-party calls, but if you need an air-gapped install, pre-vendor the model
  or use the default regex engine.
- **Confidence thresholds are a tradeoff.** Raising `min_confidence` blocks more
  (safer, more false blocks); lowering it redacts more borderline hits. Tune
  deliberately; the defaults favor caution.
- **Redaction ≠ anonymization.** Placeholders are reversible by design. If your
  use case requires irreversible de-identification, this tool is not sufficient
  on its own.

## Reporting a vulnerability

This project handles sensitive-data workflows; please report security issues
privately. See [SECURITY.md](../SECURITY.md).
