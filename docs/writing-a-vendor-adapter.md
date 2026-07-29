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
