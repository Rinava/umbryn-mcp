"""Score a detection engine against the labeled corpus.

Reports per-entity-type precision / recall / F1 using relaxed span matching
(same type + Jaccard overlap >= 0.5), then gates on the project's quality bar for
the HIPAA-relevant entity set: recall >= 0.90 and precision >= 0.80.

Usage:
    python eval/run_eval.py                 # regex engine (default)
    python eval/run_eval.py --engine presidio
    python eval/run_eval.py --min-recall 0.95
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from phi_mcp.config import Config
from phi_mcp.factory import build_engine

# The identifiers the quality bar is enforced on.
HIPAA_ENTITIES = {
    "NPI",
    "DEA_NUMBER",
    "MEDICARE_BENEFICIARY_ID",
    "MEDICAL_RECORD_NUMBER",
    "CLIA_NUMBER",
    "US_SSN",
}


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


def _jaccard(a: tuple[int, int], b: tuple[int, int]) -> float:
    lo = max(a[0], b[0])
    hi = min(a[1], b[1])
    inter = max(0, hi - lo)
    union = (a[1] - a[0]) + (b[1] - b[0]) - inter
    return inter / union if union else 0.0


def _score_doc(gold: list[dict], pred: list[dict], counts: dict[str, Counts]) -> None:
    used: set[int] = set()
    for g in gold:
        c = counts.setdefault(g["entity_type"], Counts())
        match = None
        for i, p in enumerate(pred):
            if i in used or p["entity_type"] != g["entity_type"]:
                continue
            if _jaccard((g["start"], g["end"]), (p["start"], p["end"])) >= 0.5:
                match = i
                break
        if match is None:
            c.fn += 1
        else:
            c.tp += 1
            used.add(match)
    for i, p in enumerate(pred):
        if i not in used:
            counts.setdefault(p["entity_type"], Counts()).fp += 1


def run(corpus: Path, engine_name: str) -> dict[str, Counts]:
    engine = build_engine(Config(engine=engine_name))
    counts: dict[str, Counts] = {}
    with corpus.open(encoding="utf-8") as fh:
        for line in fh:
            doc = json.loads(line)
            pred = [
                {"entity_type": e.entity_type, "start": e.start, "end": e.end}
                for e in engine.detect(doc["text"])
            ]
            _score_doc(doc["entities"], pred, counts)
    return counts


def _print_table(counts: dict[str, Counts]) -> None:
    print(f"\n{'entity_type':<26}{'prec':>8}{'recall':>8}{'f1':>8}{'tp':>6}{'fp':>6}{'fn':>6}")
    print("-" * 68)
    for name in sorted(counts):
        c = counts[name]
        mark = " *" if name in HIPAA_ENTITIES else "  "
        print(
            f"{name:<24}{mark}{c.precision:>8.2f}{c.recall:>8.2f}{c.f1:>8.2f}"
            f"{c.tp:>6}{c.fp:>6}{c.fn:>6}"
        )
    print("\n  * = HIPAA-relevant entity (subject to the quality gate)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default="regex", choices=["regex", "presidio", "auto"])
    parser.add_argument("--corpus", type=Path, default=Path(__file__).parent / "corpus.jsonl")
    parser.add_argument("--min-recall", type=float, default=0.90)
    parser.add_argument("--min-precision", type=float, default=0.80)
    args = parser.parse_args()

    if not args.corpus.exists():
        print(
            f"corpus not found: {args.corpus}\nRun: python eval/generate_corpus.py",
            file=sys.stderr,
        )
        return 2

    counts = run(args.corpus, args.engine)
    _print_table(counts)

    # Aggregate the gate over HIPAA entities.
    gate = Counts()
    for name in HIPAA_ENTITIES:
        c = counts.get(name)
        if c:
            gate.tp += c.tp
            gate.fp += c.fp
            gate.fn += c.fn
    print(
        f"\nHIPAA aggregate: precision={gate.precision:.3f} recall={gate.recall:.3f} "
        f"f1={gate.f1:.3f}"
    )
    print(f"Gate: precision>={args.min_precision} recall>={args.min_recall}")

    ok = gate.precision >= args.min_precision and gate.recall >= args.min_recall
    print("RESULT:", "PASS ✅" if ok else "FAIL ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
