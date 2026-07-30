# sync-core

The plugin SDK for [Sync](https://github.com/stroland02/sync): the protocols, models and
conformance kit a vendor adapter is written against.

Install it on its own. It depends on `pydantic` and nothing else — no database driver, no graph
runtime, no model SDK — so an adapter you write against it inherits none of Sync's runtime.

```console
pip install sync-core
```

## What is in it

Five protocols, in `sync.core`. Each is structural, so you satisfy one by having its methods and
never by subclassing it:

| Protocol | What it answers |
|---|---|
| `VendorAdapter` | What a vendor changed between two versions, and which operation an SDK symbol calls |
| `RequestCorrelator` | Which operation an observed HTTP request addressed |
| `LanguageAdapter` | Where in a repository a vendor's API is called |
| `Detector` | Which of those call sites a change puts at risk |
| `Remediator` | What patch repairs one |

Alongside them: the models every stage passes — `VendorChange`, `CallSite`, `Finding`, `Patch`,
`OperationRef` — and `sync.core.conformance`, a kit that checks an adapter against the rules the
protocols cannot express.

## Writing an adapter

```python
from sync.core import OperationRef
from sync.core.conformance import check_vendor_adapter


class AcmeAdapter:
    vendor_id = "acme"

    def operation_for_symbol(self, symbol, *, language=None):
        if symbol == "acme.things.create":
            return OperationRef(operation_id="createThing", http_method="POST", path="/v1/things")
        return None

    def fetch_changes(self, since, until):
        return []


check_vendor_adapter(AcmeAdapter(), known_symbol="acme.things.create")
```

`check_vendor_adapter` raises `ConformanceFailure` naming the rule that broke. Run it in your own
test suite: it is the difference between an adapter that satisfies the type checker and one the
pipeline can actually use.

## The authoring guide

[`CONTRIBUTING.md`](https://github.com/stroland02/sync/blob/main/CONTRIBUTING.md) is the guide —
what each protocol owes its caller, what belongs in an adapter and what never does, and how to
run the conformance kit against yours.

The rule worth knowing before you start: vendor-specific knowledge lives in the adapter. A
vendor's URL conventions, its `operationId` scheme and its SDK naming are the adapter's business
and never `sync.core`'s, which is why this package can stay small enough to depend on one thing.

## Licence

Apache-2.0. The full text ships in this distribution and is in
[`LICENSE`](https://github.com/stroland02/sync/blob/main/LICENSE).
