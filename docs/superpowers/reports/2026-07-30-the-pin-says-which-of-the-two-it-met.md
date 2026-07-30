# The pin now says which of the two things it met

**Date:** 2026-07-30
**Scope:** B64 — `test_the_staged_map_matches_the_pin_this_corpus_records` asserted against a
gitignored artifact any process in the worktree can rewrite, and could not tell "the pin is wrong"
from "somebody regenerated the map".
**Outcome:** verification is over one snapshot, so a rewrite landing after the read cannot produce a
red at all; a refusal raised while the artifact is changing is a `SymbolMapRewritten` that says so
and still carries both digests. Sixteen tests in `tests/test_symbol_map_pin.py`, four gates green.

## The shape chosen, and what it does not cover

**Read the artifact once and decide everything from those bytes; when a refusal is raised, re-read
and say whether the file moved under it.** Both halves are in `verify_staged_map`, which is the
function `score_corpus.py` already calls, so the scorer gets the same treatment as the test rather
than a test-only improvement.

The snapshot half closes a window rather than narrowing one: a rewrite that lands after the read is
simply the next revision of an artifact this call has finished with, and nothing about it can make
the call refuse. The classification half narrows one: it catches a writer still active at the moment
of the refusal, and it cannot see a rewrite that completed before the read and then stopped. That
case is indistinguishable from a stale artifact **because it is one** — the file on disk is not the
map the corpus records, whatever put it there, and the answer to both is to restage from
`built_from`. Measured under a genuinely concurrent writer, 3726 of 4000 refusals were attributed to
the rewriting and 274 were reported as plain mismatches; the misses fall on the loud side, and the
control test pins that direction — nothing that did not change is ever called a rewrite.

Comparison is by content, not by mtime. `CLAUDE.md` carries why at length: filesystems record
modification times far more coarsely than the clock, so a check written that way mostly does not
detect. The bytes are already in hand.

## What changed

**`SymbolMapRewritten(SymbolMapMismatch)`.** A subclass, so `score_corpus.py` — which stops on
`SymbolMapMismatch` — goes on stopping. A rewrite mid-verification still refuses: the map a score
would have been taken over is not knowable. What differs is what the reader does next. A mismatch
says the pin and the artifact disagree and one has to be brought to the other; this says nothing was
established, so re-run in a quiet tree.

**`verify_staged_map` reads bytes once** and decides the parse, the count and the digest from that
snapshot. It decodes explicitly rather than handing bytes to `json.loads`, which would take an
encoding from a BOM.

**A file that does not parse is refused by name.** Half a file is what a write in progress looks like
from the reader's side, and `json.JSONDecodeError` is a `ValueError`, which is one of the three
things `score_corpus.py` catches — so the scorer used to print `refused: Expecting value: line 1
column 1` and name neither the file nor what to do about it.

**The gated test goes through `verify_staged_map`** instead of around it. Two changes in one: it now
fails when the scorer would refuse rather than when a locally rewritten pair of assertions would, and
it reads the artifact once. The previous form read it for the digest and read it again for the count,
which in shared gitignored space is two reads of a file another process may have replaced in between
— it could refuse over a map that was never on disk in that state.

**The skip on absence stays exactly as it was.** An absent artifact is a fact about the checkout, not
about the pin. A skip on mismatch would retire the check, which the brief ruled out and which is the
whole point of the pin.

**`read_staged_map` is gone.** With the gated test going through `verify_staged_map`, nothing called
it.

## Verification

**Two tests were watched red first.** The rewrite classification, and the parse failure:

```
FAILED test_a_refusal_raised_while_the_file_was_being_rewritten_says_so
    DID NOT MATCH 'changed while this ran'
FAILED test_a_file_that_is_not_json_is_refused_by_name_rather_than_by_stack_trace
    json.decoder.JSONDecodeError: Unterminated string starting at: line 1 column 28 (char 27)
```

**Every new property was then broken deliberately and the test that claims it went red.** The two
control tests could not be watched red first — they assert that behaviour did *not* change — so they
are proved this way instead:

```
RED: the refusal is never classified
     test_a_refusal_raised_while_the_file_was_being_rewritten_says_so
RED: every refusal is called a rewrite
     test_a_mismatch_nothing_rewrote_is_not_reported_as_a_rewrite
RED: the count is taken from a second read, as the old check did
     test_a_rewrite_landing_after_the_read_does_not_manufacture_a_refusal
RED: a decode error escapes instead of being refused
     test_a_file_that_is_not_json_is_refused_by_name_rather_than_by_stack_trace
```

The third mutation is the old check's own shape — digest from the first read, count from a second —
and it fails the snapshot test, which is what says the flake this brief came from cannot recur in
that form.

**The real case is still loud, demonstrated against the real artifact rather than a fixture.** One
symbol in the staged map was repointed and the gated test refused, naming both digests, as
`SymbolMapMismatch` and not as a rewrite:

```
scripts.symbol_map_pin.SymbolMapMismatch: .cache\specs\symbols.json is not the symbol map this
corpus was scored against: it digests to ea3c7b722fd5ac95… and benchmark\corpus\symbol_map.yaml
records 5f71dcd3bec1302c…
```

`score_corpus.py` refused with the same sentence, before scoring a pair. The artifact was restored
byte-for-byte afterwards and the file's suite is green again.

**A concurrent rewrite is recognisable, demonstrated without monkeypatching.** Two threads, one
artifact, one writer alternating between a large and a small map, a pin matching neither, 4000
verification attempts:

```
{'rewritten': 3726, 'mismatch': 274, 'verified': 0}

-- and …\racing-symbols.json changed while this ran: 0 bytes were read and it now holds 58 bytes.
Nothing was established about the pin. `.cache/` is gitignored and shared with every process in
this worktree, so another run regenerating the map looks exactly like this; re-run against a tree
nothing else is working in before treating the pin as wrong.
```

The four gates:

```
uv run pytest                                             2510 passed, 2 skipped in 121.69s
uv run lint-imports                                       Contracts: 1 kept, 0 broken
uv run python scripts/lint_encoding.py src scripts tests  exit 0
uv run python scripts/lint_dead_links.py src --baseline …  exit 0
```

**The second skip is this worktree, not this change**, and it is worth naming because the brief
expected `2507 passed, 1 skipped`. Four tests were added, so the collected total moves from 2508 to
2512, and `sync-solo-a` skips two of them rather than one: `test_oasdiff_determinism.py:159` wants
`tools/oasdiff` and `test_parameter_reduction.py:166` wants `.cache/specs/v2320.json`, which this
tree does not have. Both skip by design when their inputs are absent and both would run after
`scripts/fetch_measurement_inputs.py`. Neither is the pin test, which passes.

## What is left

**A stale artifact still reads as a mismatch, and should.** If a run regenerates the map, finishes,
and the suite runs afterwards, the classifier sees a file that is not changing and calls it what it
is. Making that case self-identifying would mean rebuilding the map from the specifications on disk
to see whether the staged bytes are a current regeneration — which is the trade
`scripts/symbol_map_pin.py` already refuses in its "Recording, not regenerating" section: it would
swap an unpinned input for an unpinned build.

**Nothing here stops two agents sharing a worktree**, which is what produced the observed failure.
The check is now legible when it happens; the sharing is a coordination matter.
