# A Python repository that clears the bar now exists, and a fourth limitation stops it being pinned

**Date:** 2026-07-29
**Scope:** B42 — re-run the B37 search against the binder B38 and B39 repaired.
**Outcome:** the binder fixes are visible in the counts, none of the seventeen qualifies, and a
re-search found the first repository that does — `openbraininstitute/virtual-lab-api`,
Apache-2.0, 21 indexable call sites over 12 operations. **It was not pinned, because
`sync.benchmark.mutate` cannot generate a pair for a Python call site at all.** No corpus number
moved and no floor was restated.

## The seventeen, new counts beside old

Every one re-cloned at its default branch and indexed with the current adapter against the pinned
272-symbol map. Counts are taken **without** the `matches` gate so they compare like for like with
B37's table, which did the same; `matches` is reported separately because it is what decides
whether `sync.cli` would select an adapter at all.

| repository | licence | old | **new** | `matches` | manifest |
|---|---|---:|---:|---|---|
| `TechWithTy/fast_stripe_python_template` | none | 10 | **12** | no | none |
| `sjcahill/mainttracker_functions_core_lib` | **none** | 0 | **5** | yes | `pyproject.toml` |
| `DanielAguilarJ/RestoNext` | none | 2 | 2 | no | `requirements.txt` |
| `hashicorp-forge/grove` | MPL-2.0 | 1 | 1 | yes | `pyproject.toml` |
| `LilithB92/Online_training_DRF` | — | 0 | **raises** | — | `requirements.txt` |
| the remaining twelve | — | 0 | 0 | — | — |

**The binder fixes are real and visible.** `sjcahill` went from nothing to five, all through
`self.stripe.customers.*` — the B38 `self`-attribute receiver. `TechWithTy` gained two,
`stripe.payment_intents.list` and `stripe.balance_transactions.list`, which are B39's Python
spellings and were unreachable in any spelling before.

**None of them qualifies, and the reason is licensing rather than binding.** The bar is more than
a couple of sites, a licence that permits pinning, and a manifest. `sjcahill` now meets the count
and the manifest and has **no licence at all** — no `LICENSE` file anywhere in the tree, no
`license` key or classifier in `pyproject.toml`, no mention in the README, and the GitHub API
returns `license: null`. Unlicensed is all-rights-reserved, and a binder fix does not change that.
`TechWithTy` has the highest count and neither a licence nor a manifest. `grove` is licensed and
still contributes one.

## The search was re-run, and that was the right call

B37's candidate list was itself assembled by searching for *the shape the old binder could
index*, which its own report says explicitly. Re-measuring only those seventeen would have asked
the new binder a question shaped by the old one's limits, so the search was repeated against the
shapes B38 added.

Code search for `= stripe.StripeClient(`, `self.client.customers.create` and
`self.stripe.customers.create`, licences resolved through the API, and every permissively licensed
hit cloned and indexed:

| repository | licence | `matches` | sites | operations |
|---|---|---|---:|---:|
| **`openbraininstitute/virtual-lab-api`** | **Apache-2.0** | **yes** | **21** | **12** |
| `dj-stripe/dj-stripe` | MIT | yes | 0 | 0 |
| `oxcamne/oxcam` | BSD-3-Clause | yes | 0 | 0 |
| `aden-hive/hive`, `AngiesJobBoard/backend` | Apache-2.0 | no | 0 | 0 |
| `mbuunk52/advanced_subscriptions`, `olorin/python-eway-token`, `s-amundson/wpa_2p1` | MIT | no | 0 | 0 |

`openbraininstitute/virtual-lab-api` clears every clause of the bar. Three of its operations carry
three call sites each — `GetCustomers`, `GetProductsId`, `GetSubscriptions` — which is more than
the `hold_back` rule needs, so it would contribute falsifiable negatives rather than only
denominators.

## Why it was not pinned

`sync.benchmark.mutate` cannot make a pair for a Python call site. Measured, not assumed:

```
language_for('a.py')  = None
language_for('a.ts')  = 'typescript'

request-side:   unreachable = ('cs1',)   mutated? False
response-side:  unreachable = ('cs1',)   mutated? False
```

`generate_pair` skips any site whose `language_for` is `None`, records it as an unreachable target
and labels it unaffected. Every Python target, on both change kinds, comes out that way — the tree
is returned unedited.

Underneath that, the mutation primitives are TypeScript grammar throughout. `_object_argument`
looks for a child of kind `object`, which in Python's grammar is `dictionary`, and Python passes
request fields as `keyword_argument` rather than in a literal at all. `_result_binding` matches
`lexical_declaration`, `variable_declaration` and `assignment_expression`, none of which exist in
Python, where the node is `assignment`.

**So pinning this repository today would add pairs that score zero affected, zero findings and N
unreachable targets.** That moves `pairs_scored` — and therefore its floor — while contributing
nothing to either rate, and it would put a Python repository in the corpus that measures no Python.
The report this task came from names exactly that shape as the exclusion the exclusion count
cannot catch. Not pinning is the honest answer, and the blocker has a name.

It was also not fixed here. Teaching the generator Python is a task's worth of work — a dictionary
and keyword-argument request mutation, a Python response guard, a `language_for` that knows `.py`
— and doing it in the same change that pins the repository it unblocks would mean one worker
moving both the corpus and the thing that produces its ground truth. That constraint has held all
day and it holds here.

## Floors, and the two gate failures that did not happen

The brief expected `gate_corpus.py` to fail because pairs would be added, and the symbol-map pin to
hold. **Neither gate failed, because nothing was added.**

| | recorded | measured | moved |
|---|---|---|---|
| binding precision | 1.0000 n=16 | 1.0000 n=16 | no |
| binding recall | 1.0000 n=16 | 1.0000 n=16 | no |
| falsifiable negatives | 4 | 4 | no |
| pairs scored | 12 | 12 | no |
| symbol map digest | `5f71dcd3bec1…` | `5f71dcd3bec1…` | no |

`Every floor cleared.` No floor was restated, because no denominator moved — the same sentence
B37's report ends on, for the same reason.

The map pin holding is worth stating rather than assuming. The map was rebuilt from the staged
specification during this task and reproduced the pinned digest exactly, 272 symbols,
`5f71dcd3bec1302cf70cba56bc9ebf043b38a1727acb43cee9e20fa08ead6be7`.

## Determinism

Scored twice from two freshly created databases, byte-identical:

```
e48ee05da861900f07c807c99f34d03c6d5bac821f5facf3e76d452348855d60
```

## Python binding precision and recall

**Still unmeasured, and `null` rather than zero.** No Python repository is in the corpus, so
neither axis has a Python sample. The numbers above describe four TypeScript repositories, exactly
as they did this morning.

## One defect found on the way, not fixed

`LilithB92/Online_training_DRF` no longer returns zero — it raises:

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte
```

Its `requirements.txt` begins `ff fe`, a UTF-16 LE byte-order mark. `python_lang._requirement_lines`
guards the `pyproject.toml` branch with `except (TOMLDecodeError, UnicodeDecodeError)` and reads
`requirements.txt` with a bare `read_text(encoding="utf-8")`. So a customer repository whose
manifest is UTF-16 crashes adapter selection instead of answering "declares nothing", which is what
that function's own docstring promises for an unreadable manifest.

`src/sync/index/` is outside this task. Reported rather than repaired, with the reproducer above.

## What would unblock this, in the order it would pay

1. **Teach `sync.benchmark.mutate` Python.** One repository is waiting and it is the only thing in
   the way. `language_for` recognising `.py`, a request mutation over keyword arguments and
   dictionary literals, and a response guard in Python syntax.
2. **Guard the `requirements.txt` read**, above.

B37's list of three is now closed. This is the fourth, and unlike those three it is in the
generator rather than in the binder.
