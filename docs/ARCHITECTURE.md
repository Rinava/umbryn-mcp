# Architecture

`phi-redact-mcp` is a thin MCP transport wrapped around a dependency-free
redaction core. The design goal is that the interesting logic — and the
fail-closed guarantee — lives in plain Python that can be tested in
microseconds and embedded anywhere (a proxy, a batch job, another server), with
MCP and Presidio kept at the edges.

## Layers

```
┌──────────────────────────────────────────────────────────────┐
│ server.py            FastMCP over stdio: redact/restore/detect │  ← MCP edge
│                      maps PhiRedactionError → MCP tool error    │
├──────────────────────────────────────────────────────────────┤
│ factory.py / config.py    build a Redactor from env config      │
├──────────────────────────────────────────────────────────────┤
│ redactor.py          THE CORE. Fail-closed orchestration:       │  ← pure,
│                      threshold logic, overlap resolution,        │    no MCP,
│                      collision-proof reversible placeholders     │    no Presidio
├──────────────────────────────────────────────────────────────┤
│ engine.py            DetectionEngine protocol (the only seam)    │
├───────────────────────────────┬──────────────────────────────┤
│ regex_engine.py (default)     │ presidio_engine.py (optional)   │  ← detection
│ recognizers.py + checksums.py │ Presidio + spaCy, normalized     │    edge
└───────────────────────────────┴──────────────────────────────┘
```

Dependencies point **inward**: `server` → `factory` → `redactor` → `engine`
protocol. The core never imports MCP or Presidio, which is what makes the future
proxy/gateway mode (see [ROADMAP](../ROADMAP.md)) a matter of adding a new edge,
not rewriting the core.

## The core, in four decisions

**1. Two thresholds, and the gap between them blocks.**
`detection_floor` is the sensitivity boundary — below it, an engine signal is
treated as noise and ignored. `min_confidence` is the *trust* threshold. A
candidate that survives the floor but scores below `min_confidence` is
*uncertain*, and any uncertain candidate makes `redact` fail closed. We do not
redact the confident spans and pass the uncertain one through — the whole call
blocks. `detect`, by contrast, surfaces the uncertain band so you can inspect it.

**2. Redaction is offset-based, never search-based.**
Spans come back from the engine as `[start, end)` offsets and are cut by index.
A value that also appears elsewhere in the text is never touched by accident.

**3. Placeholders are collision-proof, so restore is an exact inverse.**
Each placeholder (`[NPI_1]`, `[PERSON_2]`, …) is verified absent from the
original text and from every other placeholder before use; the
bracket+underscore format is prefix-free. Therefore `restore` — a plain sequence
of string replacements — inverts `redact` exactly, for *arbitrary* input. This
is asserted by a Hypothesis property test, not just examples.

**4. Overlaps resolve by a total order.**
Nested/overlapping detections are reduced to a non-overlapping set by a fixed
priority: higher score, then longer span, then type name, then start offset.
Because it's a total order, output never depends on the order the engine emitted
detections in — the same input always produces the same redaction.

## The detection seam

`DetectionEngine` is a one-method protocol: `detect(text) -> list[Entity]`.
Implementations must be deterministic and must not egress to third parties at
detection time. Two ship today:

- **`RegexEngine`** (default) — runs [`recognizers.py`](../src/phi_mcp/recognizers.py),
  a table of regex + score + optional context words + optional check-digit
  validator. Zero heavy dependencies, no network, installs everywhere.
- **`PresidioEngine`** (optional) — wraps Microsoft Presidio's `AnalyzerEngine`,
  adds custom recognizers for the identifiers Presidio lacks (MRN, CLIA), and
  normalizes Presidio's entity names (`US_NPI` → `NPI`, …) to our taxonomy.

Both emit the same canonical entity types (see
[`entities.py`](../src/phi_mcp/entities.py)), so placeholders, config, and the
eval harness are engine-agnostic.

## Testing strategy

The test approach is intentionally non-uniform:

- **Invariant suite** (`tests/`, fast, Presidio faked) — fail-closed, round-trip
  (property-based), edge cases, tool contracts. Sub-second; this is the red-green
  loop.
- **Eval harness** (`eval/`) — precision/recall per entity type against a labeled
  synthetic corpus. Used to *tune* recognizers, not to gate the fast loop.
- **Integration smoke** (`tests_integration/`, slow, separate) — a real stdio
  MCP handshake against the built server, and a real-Presidio test that skips
  when Presidio isn't installed.
