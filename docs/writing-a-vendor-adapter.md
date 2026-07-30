# Writing a vendor adapter

Sync watches the third-party APIs a codebase calls and opens verified pull requests when one of
them breaks. It learns what a vendor changed from a **vendor adapter**, and adapters are the
part of the system we expect other people to write. A live codebase calls dozens of third-party
APIs; we cannot write dozens of adapters ourselves, so this interface has to be good enough that
vendors and their users write them. That is the whole argument for open core, and it is why
`sync.core` depends on nothing.

Your adapter depends on `sync.core` and nothing else. If you find yourself importing
`sync.graph` or `sync.remediate`, stop — the dependency is the wrong way round, and a test in
this repository enforces it.

## What an adapter is

Two methods and an identifier.

```python
class VendorAdapter(Protocol):
    vendor_id: str

    def fetch_changes(self, from_version: str, to_version: str) -> Iterable[VendorChange]: ...

    def operation_for_symbol(
        self, symbol: str, *, language: str | None = None
    ) -> OperationRef | None: ...
```

`fetch_changes` turns two versions of whatever the vendor publishes into structured changes.
`operation_for_symbol` maps a call in the customer's source — `stripe.charges.create` — onto the
operation it addresses. The second is the hinge of the whole system: without it, a specification
diff and the customer's code live in unconnected universes and no finding can ever be raised.

## Check your work

`isinstance(adapter, VendorAdapter)` will pass for almost anything. It is a `runtime_checkable`
Protocol, and those verify only that the method *names* exist — not signatures, not return types,
not behaviour. An adapter that raises where it should return `None` passes that check and then
fails inside the pipeline, where the error names our internals rather than your mistake.

So run the conformance kit instead:

```python
from sync.core.conformance import check_vendor_adapter

check_vendor_adapter(MyAdapter(...), known_symbol="myvendor.charges.create")
```

It raises `ConformanceFailure` naming the rule you broke and why it exists. Passing it is not a
guarantee of correctness — it is a floor. Your own tests, against committed fixtures of your
vendor's real artifacts, are what establish that the adapter is right.

## The guarantees, and why each one exists

**`operation_for_symbol` returns `None` for a symbol it cannot place. It never guesses, and it
never raises.**

This is the rule most worth internalising, because breaking it fails silently and in the
expensive direction. An unresolved symbol is *visibly* unresolved: nothing binds to it, no
finding is raised, and the gap can be counted and closed later. A wrongly resolved symbol
produces a finding against code that never made that call — a pull request against the wrong
line — and nobody learns it was wrong. Raising is a third failure: it aborts an indexing run over
one call site your adapter simply did not recognise.

**Accept the `language` argument even if you ignore it.**

The indexer passes it on every call. Two SDKs for the same vendor can spell the same operation
differently: `twilio-python` exposes `call_summaries` where `twilio-node` exposes `callSummaries`.
If your vendor's SDKs agree, ignore the value — but say in your docstring that you are ignoring it
and why, because the next reader needs to know that is a decision rather than an oversight. If
they disagree, a spelling that belongs to the other language must return `None` rather than be
rewritten into a match.

**`fetch_changes` may raise, but must return something iterable when it returns.**

Raising is correct when you *could not look* — a specification you could not fetch, a credential
that failed. Answering that with an empty iterable would tell Sync the vendor changed nothing,
which is a false negative in the one direction this system must not have. What you must not do is
return `None`; every caller writes a `for` loop over the result.

**`vendor_id` is a non-empty string, and it is stable.**

Every row your adapter produces is filed under it, and detectors are scoped by it. Changing it
later orphans everything already stored.

## Two things worth knowing before you start

**Keep the raw record.** `VendorChange.raw` should carry the vendor's own bytes alongside your
interpretation of them. Interpretations get revised; when ours were, having the raw records meant
the fix could be applied to history instead of re-fetching every specification pair.

**Your adapter will be wrong about something, and the wrongness should be countable.** Prefer a
gap you can measure — "this map covers 105 of 414 paths" — over a heuristic that fills the gap
with guesses. Coverage that is honest can be improved by whoever cares most; coverage that is
fabricated cannot be distinguished from the real thing until it produces a bad pull request.

## A worked example

The adapters in `src/sync/signals/` are the reference. `stripe` is the easiest possible vendor —
a public machine-readable specification, versioned in git, with a generated SDK manifest.
`twilio` is a harder one and its module docstrings record where the two diverge. `mcp_server`
watches a server's advertised tools rather than a specification, and shows what `fetch_changes`
means for a vendor with no versions at all.

## The other plugin points

`VendorAdapter` is the one most people write, but it is one of five protocols in
`sync.core.protocols`, and four of them have a conformance kit. This section covers the two
whose kits are least obvious. `Remediator` has `check_remediator`, whose one interesting rule is
that a patch is what is on disk rather than what the diff says is on disk. `RequestCorrelator`
has no kit; its single guarantee is `operation_for_symbol`'s, addressed by URL path instead of by
symbol.

### A language adapter

A `LanguageAdapter` turns a repository into call sites and stands between a proposed patch and
the customer's repository. The kit needs a real checkout to say anything at all:

```python
from sync.core.conformance import check_language_adapter

check_language_adapter(
    MyAdapter(...),
    RepoRef(repo_id="demo", url=..., local_path="/path/to/a/clean/clone", head_sha=...),
    installed_dependency="node_modules/mysdk/package.json",  # omit if you install nothing
)
```

It runs your real toolchain against that clone, so it is as slow as an install and a compiler
are. Hand it a *clean* checkout: `prepare` runs against it, and an adapter that measures a
typecheck baseline is right to refuse a tree with uncommitted changes in it.

**A call site's path is repository-relative and spelled with forward slashes.** Everything
downstream opens it as `Path(repo.local_path) / site.path`, and pathlib discards the left-hand
side when the right one is absolute — silently, so the remediator edits a file outside the clone
rather than failing. A backslash path is the same bug with a delay: it passes every test on the
machine that produced it and names no file on the customer's CI.

**`matches` answers for every repository, including ones it does not own.** Every registered
adapter is asked about every repository before any of them is chosen, so one that raises on a
tree with no manifest in it takes down the selection loop and the traceback names the wrong
adapter. Return a `bool` rather than the thing you matched on — a manifest path is truthy for
every repository that has one at all, which is how an adapter comes to claim another language's
work.

**Indexing twice over an unchanged checkout produces the same call sites.** INDEX is a pipeline
stage and every stage here is idempotent. One that is not leaves the graph holding whichever run
happened last, and no query can tell which run that was.

**`static_verify` returns a `VerifyResult`, and a failing one carries diagnostics.** That string
is the entire input to the next patch attempt. A failure carrying none spends an agent run to
arrive back where it started.

Three properties of `static_verify` are load-bearing and the kit reaches one and a half of them,
which is worth saying plainly rather than leaving to be discovered:

| Property | What the kit checks |
|---|---|
| It measures the tree a push would carry, holding untracked and ignored files out of the compile | Only the restore: a file the verification moved has to come back. Whether the *verdict* excluded it needs a source file that fails to compile, which only you can write |
| It subtracts a pre-existing baseline, so errors the checkout already had do not fail a patch | Nothing. It needs a checkout that already fails to compile, committed in that state before `prepare` measures it — the kit will not commit to your repository |
| It refuses a patch that edited an installed dependency | Checked, but only if you pass `installed_dependency`. The kit has no language-agnostic way to find one |

That last one matters more than it sounds. An edit inside an installed dependency satisfies a
gate the customer's CI will not: no checkout of the branch contains that file, because the
install is theirs. Refusing by raising is as good as returning a failure.

### A detector

A `Detector` queries the graph and emits findings. The kit takes one already constructed, holding
whatever store or fixture it queries — the five in this repository take a store, a specification,
a repository id and a set of thresholds between them, and no signature would fit all of them.

```python
from sync.core.conformance import check_detector

check_detector(MyDetector(store, repo_id="demo"))
```

Construct it over input that actually reaches its thresholds. The kit insists on at least one
finding, because every other rule is vacuous against a scan that emits nothing — and that is not
a hypothetical: the first run of this kit against `StatusRateDetector` reported conformance while
the detector emitted nothing, on a fixture a hundred and twenty calls short of its floor.

**Two scans of an unchanged graph produce the same findings.** DETECT is a pipeline stage, and a
detector whose answer depends on how many times it has been asked makes the graph a record of run
ordering.

**Every finding names the binding rung it rests on.** `Finding.binding_rung` defaults to
`unattributed`, which the graph reserves for rows written before the column existed —
`GraphStore.insert_finding` refuses that value, so a detector that leaves the field alone is
rejected on the first finding it ever raises. The kit checks that a rung was named and never which
one: the rung names the binding whose wrongness would make the finding wrong, so a claim read off
the static index is `static`, and one resting on a span-to-operation correlation carries the
correlator's own rung through — including `unresolved`, when nothing correlated. That is your
judgement about your detector, and a false positive nobody can attribute to a rung is one nobody
can fix.

**Two findings from one scan may not share `(detector, call_site_id, vendor_change_id, claim)`.**
That quadruple is how the graph identifies a finding, and the insert is `ON CONFLICT DO NOTHING`.
So a detector saying two different things about one call site under one change and one claim keeps
whichever it emitted first, and the second is discarded at the store without a warning. If you have
two things to say, give them claims that name the two different things, or say both in one finding.
`claim` joined that key after the rule was written, and this paragraph named the triple until B67
noticed it still did.

**Every finding names its call site and carries your `detector_id`.** A finding addresses its
location by `call_site_id` and by nothing else, so one carrying an empty string has no line to
report and no file to patch — drop it and count it instead. And `detector` is what attributes a
false positive back to the code that raised it; a finding signed with a name nothing answers to
cannot be attributed to anything.
