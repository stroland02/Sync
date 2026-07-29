# One PNG ends a corpus run, and the fix moves two digests and no number

**Date:** 2026-07-29
**Scope:** B30 — `_score_corpus` read every file under a checkout as UTF-8, so a repository with a
single image in it could not be scored at all.
**Outcome:** the skip is built, the paths it skips are reported on both surfaces that print a
score, the corpus fetcher's own pre-filter is gone, and neither corpus axis moved.

## What the numbers were taken against

Baseline measured on `a49d191` (`docs: name the two Python binding forms B34 has to get right`),
which was `origin/main` when this task started. The after-state is that commit plus the change
described here. Both scores were taken from freshly created databases over the twelve committed
specifications.

| | before | after |
|---|---:|---:|
| binding precision | 1.0000 (n=16) | 1.0000 (n=16) |
| binding recall | 1.0000 (n=16) | 1.0000 (n=16) |
| falsifiable negatives | 4 | 4 |
| call sites affected | 16 | 16 |
| call sites unaffected | 133 | 133 |
| unlabelled findings | 0 | 0 |
| pairs specified / scored | 12 / 12 | 12 / 12 |
| excluded pairs | none | none |
| **paths not read** | not reported | **64** |

**Nothing moved, and that was the prediction rather than the hope.** The fetcher's drop criterion
and the skip added here are the same criterion — a file leaves either one exactly when it does not
decode as UTF-8 — so the mapping handed to the indexer is identical whichever component knows
about binaries. What changed is where the knowledge lives and what the tree digest is a digest of.
The per-pair table is byte-identical to the baseline apart from the new `unread` column.

## What was wrong

```python
sources = {
    path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
    for path in sorted(root.rglob("*"))
    ...
}
```

`read_text` raises on the first byte that is not valid UTF-8, before a single call site is
indexed. The failure is not partial and not recoverable: a repository with one `.ico` in it is
unscoreable. Most real repositories have one. The frozen corpus is four repositories partly
because of this, so the cost is coverage rather than convenience.

## What was built

`sync.benchmark.checkout.read_checkout` returns the source mapping and the paths it could not
read. A file that does not decode is **skipped**, never decoded leniently: `errors="replace"`
would hand the indexer a file full of replacement characters, which is still a file tree-sitter
will parse, and every call site it found in one would be a phantom. `CLAUDE.md` already names the
shape — bytes that are not text are not decoded at all.

The decode itself stays `read_text` rather than `read_bytes().decode("utf-8")`, and that is
deliberate. The two differ on newlines: `read_text` translates CRLF, and this mapping is what call
site positions and content hashes are computed from. Decoding by hand would have moved the corpus
score for a reason that has nothing to do with binaries, and the movement would have looked like a
finding.

## The skip and the fetcher's drop are now one thing, and the walk is too

`scripts/fetch_corpus_repositories.py` held back undecodable files before hashing, because the
scorer could not survive them. That is the transformation that made the corpus score a tree which
was not the repository its manifest names, and with the skip where the reading happens there is
nothing left for the fetch to decide. It copies the pinned subtree verbatim.

So the two components no longer share a predicate for *what is source* — only one of them has one.
They do still both need to answer *what is part of the tree*, and that was two correct
implementations of one rule, which is the arrangement where a divergence is silent: the digest
would go on pinning one set of files while the score was taken over another, and neither component
would notice. It is now `sync.benchmark.checkout.tree_files`, imported by both, with a test
asserting that what the fetcher materialises is exactly what the scorer walks.

`sync.benchmark.checkout` imports stdlib only, which is what makes that sharing cheap — a setup
script that reaches the network does not acquire the scorer's Postgres dependency to use it.

## How the skipped paths are surfaced

Counted **and named**, on both surfaces that print a score:

- `scripts/score_corpus.py` prints `paths not read` in the summary block, an `unread` column in
  the per-pair table, and the distinct paths under their own heading at the bottom.
- `sync.benchmark.report.render_report`, which `sync benchmark --score-pair` uses, prints a
  `Checkout paths not read as source (n)` block. It prints nothing when there is nothing to say:
  a heading that appears on every run is one the next reader learns to skip.

Pooled across the corpus the paths are **deduplicated**, because four specifications name
`furever` and its 63 images are the same 63 images in each. A sum would have reported 254 skipped
paths over a corpus that skips 64, which reads as a much larger problem than the one it describes.
The per-pair counts are what say how many each scoring run walked past.

`2026-07-27-sync-benchmark-gates.md` is why the count is not optional: silent exclusion turns a
biased sample into an unqualified number, and a skip nobody counts is how a corpus stops
describing the repository it names.

## Legacy-encoded source, which is the case this cannot solve

A source file in a legacy encoding raises the same `UnicodeDecodeError` a PNG does, and skipping
it loses real call sites. Telling the two apart cheaply is not possible — any byte sequence that
is valid cp1252 is valid cp1252, and this repository runs on Windows where cp1252 is the platform
default. A heuristic would be a guess, and a guess that decoded a binary as cp1252 produces
exactly the phantom call sites the `errors="replace"` argument rejects.

**So naming the paths is the mitigation rather than the fix, and it is a real one for the case
that matters.** A reader who sees `src/legacy.ts` in the list knows to look; a reader handed only
`64` could not have known there was anything to look at.

Over this corpus the answer happens to be clean. All 64 skipped paths are images, fonts or an
icon:

```
41 .jpg   17 .png   3 .otf   2 .jpeg   1 .ico
```

No `.ts`, `.js`, `.json` or any other extension the indexer would have read. So no call site is
lost here — but that is a property of these four repositories, not a guarantee, and the list is
what makes the next repository's answer checkable.

## What moved in the manifest, and what did not

`benchmark/corpus/repositories.yaml` pins each entry by commit, subpath and `tree_digest`. **No
pinned commit or subpath changed.** Two of the four digests did, because the fetch now hashes
files it used to remove:

| repository | files before | files after | digest |
|---|---:|---:|---|
| `furever` | 172 | 235 | `0a14ffb4…` → `2562e449…` |
| `remix` | 16 | 17 | `20cbf5f7…` → `31dd7aac…` |
| `turbo` | 189 | 189 | unchanged |
| `fireship-server` | 36 | 36 | unchanged |

`turbo` and `fireship-server` carry no undecodable file at all, so the old pruning never touched
them. That corrects a sentence the fetcher's own docstring carried — "three of the four
repositories carry images" — which was true of the repositories and not of their scored subtrees.

The manifest now records what the digest covers and why it changed, in the file itself. Four
changed hashes in a diff tell a reviewer the bytes moved; they do not say the *subject* moved, and
without that the next person to see a mismatch goes looking for a vendor commit that never
happened.

## What was not done

**No threshold and no gate.** `2026-07-27-sync-benchmark-gates.md` forbids inventing one, and
nothing here is compared against a number.

**Nothing under `benchmark/corpus/pairs/` or `benchmark/corpus/recorded/`.** The specifications
are unchanged and no new recording was written; the measurement above is the record, taken against
the commit named at the top.

**Nothing under `src/sync/index/`, `src/sync/graph/`, `src/sync/remediate/`, or
`src/sync/benchmark/binding.py`.**
