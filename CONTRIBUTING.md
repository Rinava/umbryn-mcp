# Contributing to umbryn-mcp

Thanks for being here! This project is a deliberately friendly place to make a
first open-source contribution. Adding a detection recognizer is a small,
well-scoped, high-value task — a perfect first PR.

**One hard rule up front: never commit real PHI or PII.** All fixtures, tests,
and corpus entries must be synthetic (invented). If you're unsure whether an
example is safe to include, it isn't — make one up.

## Dev setup

```bash
git clone https://github.com/Rinava/umbryn-mcp && cd umbryn-mcp
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Optionally add the ML engine (heavier):

```bash
pip install -e ".[dev,presidio]"
python -m spacy download en_core_web_sm
```

## The loop

```bash
pytest                       # fast invariant suite (Presidio faked, sub-second)
ruff format . && ruff check --fix .
mypy src/umbryn_mcp
python eval/run_eval.py       # detection quality gate
pytest tests_integration      # slow: real stdio + real Presidio (auto-skips if absent)
```

Everything above runs in CI on every PR; running it locally first makes review fast.

## How to add a recognizer (the classic good first issue)

Say you want to detect a new identifier — a UK NHS number, a state license, etc.

1. Add a canonical name in [`src/umbryn_mcp/entities.py`](src/umbryn_mcp/entities.py).
2. If it has a check digit, add a validator in
   [`src/umbryn_mcp/checksums.py`](src/umbryn_mcp/checksums.py) (with a docstring citing
   the algorithm).
3. Add a `Recognizer(...)` to `DEFAULT_RECOGNIZERS` in
   [`src/umbryn_mcp/recognizers.py`](src/umbryn_mcp/recognizers.py). Prefer precision:
   use a check digit where one exists, and context-gate format-less identifiers.
4. Add unit tests in [`tests/test_recognizers.py`](tests/test_recognizers.py) —
   at least one true positive and one look-alike that must **not** match.
5. Add synthetic examples to the eval generator
   ([`eval/generate_corpus.py`](eval/generate_corpus.py)), regenerate the corpus,
   and confirm `python eval/run_eval.py` still passes the gate.
6. Note the new entity in the README coverage table.

That's a complete, reviewable PR. Open an issue first if you want to sanity-check
the approach.

## Conventions

- **Style:** `ruff format` (line length 100) and `ruff check` must pass. `mypy
  --strict` on `src/umbryn_mcp`.
- **Tests:** new behavior needs a test. Bugs get a failing test first, then the
  fix (see the fail-closed tests for the house style).
- **Commits:** clear, imperative subject lines (`Add UK NHS recognizer`). Keep
  PRs focused; link the issue they close.
- **PRs:** fill in the template checklist. Small and focused merges fastest.

## Good first issues

Browse [`good first issue`](https://github.com/Rinava/umbryn-mcp/labels/good%20first%20issue)
and [`help wanted`](https://github.com/Rinava/umbryn-mcp/labels/help%20wanted), or the
auto-generated [contribute page](https://github.com/Rinava/umbryn-mcp/contribute).
Comment to claim one — we try to respond quickly. See [ROADMAP.md](ROADMAP.md) for
the bigger picture.

By contributing you agree your work is licensed under the project's
[MIT License](LICENSE).
