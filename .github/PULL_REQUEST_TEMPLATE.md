## What this changes, and why

<!-- The diff says what. Say why. -->

## Evidence

<!-- How do you know it works? A measurement beats an assertion. If you fixed a defect,
     show it failing before and passing after. -->

- [ ] Wrote the failing test first and watched it fail for the reason expected
- [ ] Proved any new gate, lint or rule can actually fail

## Gates

```
uv run pytest
uv run lint-imports
uv run python scripts/lint_encoding.py src scripts tests
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

<!-- Paste the summary lines rather than paraphrasing them. -->

## If this touches the binder or the corpus

- [ ] `scripts/gate_corpus.py` still clears every floor, or a floor is restated **in this commit**
      with the old and new values side by side and the reason it moved
- [ ] No floor was lowered because a number got worse

## Anything left deliberately undone

<!-- Stating what you did not fix, and why, is worth more than silence. -->
