<!-- Thanks for contributing! Keep PRs focused; small ones merge fastest. -->

## What & why

<!-- What does this change, and what problem does it solve? Link the issue. -->

Closes #

## Checklist

- [ ] Tests added/updated (bugs get a failing test first, then the fix)
- [ ] `pytest` passes
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `mypy src/phi_mcp` passes
- [ ] Docs updated if behavior/config changed (README, docstrings)
- [ ] **No real PHI/PII** in fixtures, tests, or the eval corpus — synthetic only
- [ ] If a recognizer was added: eval corpus updated and `python eval/run_eval.py` still passes
