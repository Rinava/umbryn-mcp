# Detection eval harness

This measures **detection quality** (precision/recall per entity type), separate
from the fast invariant suite that measures **orchestration** (fail-closed,
round-trip, overlaps). Keeping them separate is deliberate: the invariant suite
fakes the detector and runs in well under a second; this harness runs the real
engines against a labeled corpus and is where recognizers get tuned.

## The corpus

`corpus.jsonl` is **100% synthetic** — no real PHI, ever. Each line is
`{"text": ..., "entities": [{"entity_type", "start", "end"}]}`. It's produced by
[`generate_corpus.py`](generate_corpus.py), which:

- generates identifiers with **valid check digits** where they exist (NPI, DEA,
  credit card) and correct positional structure (MBI, SSN), so matches are
  realistic;
- records every gold span **by construction**, so labels are exact;
- weaves in **negative distractors** (10-digit order numbers, ZIP codes, dates,
  room/dose numbers) as *unlabeled* text, so precision is measured honestly —
  a detector that over-fires on look-alikes is penalized.

It is deterministic (fixed seed), so the committed corpus is reproducible:

```bash
python eval/generate_corpus.py --n 200      # regenerate corpus.jsonl
```

## Running

```bash
python eval/run_eval.py                      # default (regex) engine
python eval/run_eval.py --engine presidio    # requires the [presidio] extra + a spaCy model
python eval/run_eval.py --min-recall 0.95    # tighten the gate
```

## Scoring

A prediction matches a gold entity when the **type is identical** and the spans
overlap with **Jaccard ≥ 0.5** (relaxed span match, one-to-one greedy). From the
matches: `precision = tp/(tp+fp)`, `recall = tp/(tp+fn)`, `f1` the harmonic mean.

The **quality gate** aggregates over the HIPAA-relevant set (NPI, DEA, MBI, MRN,
CLIA, SSN) and requires **recall ≥ 0.90** and **precision ≥ 0.80**. `run_eval.py`
exits non-zero if the gate fails, so CI can enforce it.

## Honest limitations

Synthetic templates are easier than messy real-world clinical notes. These
numbers validate the ruleset against *its design targets* — they are **not** a
claim about accuracy on arbitrary production text, and they are **not** a
compliance certification. Real deployments should evaluate on their own
representative (de-identified or synthetic) data. See the
[threat model](../docs/THREAT_MODEL.md).
