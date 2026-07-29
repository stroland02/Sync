# Python binds the client people actually write

**Date:** 2026-07-29
**Scope:** B38 — `PythonAdapter` bound a Stripe call only when the client was a bare imported
name, which is why sixteen of seventeen candidate repositories bound nothing at all.
**Outcome:** the two shapes the coverage measurement named now bind, with the adjacent forms
either covered or written down.

## What now binds

| shape | before | after |
|---|---|---|
| `from stripe import StripeClient` → `client = StripeClient(k)` → `client.charges.create(...)` | binds | binds |
| `import stripe` → `billing = stripe.StripeClient(k)` → `billing.charges.create(...)` | **nothing** | binds |
| `self.payments = stripe.StripeClient(k)` → `self.payments.charges.create(...)` | **nothing** | binds |
| singleton built in one module, imported and called in another | nothing | binds |

The module-attribute constructor is the one the measurement singled out: it is what Stripe's own
Python documentation tells people to write, it is one rule from the imported name that already
worked, and it alone moves eleven of the seventeen repositories off zero.

The `self` case is the one a corpus repository most needs, because a repository worth pinning has
a class around its Stripe usage rather than a module-level global.

## The one structural change

A client root used to be one segment, matched as `chain[0] in clients`. `self.payments` is two,
so the match is now over **prefixes, longest first**. A repository that binds both `client` and
`self.client` has to read the second as the client it is rather than as the first followed by an
attribute nobody named.

Two segments is the ceiling and the comment beside `_MAX_CLIENT_SEGMENTS` says why: the only
two-segment form is `self.<attribute>`, and a third would have to be an object this walk cannot
follow to its own construction.

The floor is unchanged. At least two segments must survive the root, because a call on the client
itself — `client.close()` — names no operation. That was `len(chain) < 3` and is now the same rule
expressed against the remainder.

## How the rule stays off other people's constructors

Two guards, and they answer two different ways of getting this wrong.

**The object is checked, never the attribute.** `notstripe.StripeClient(key)` spells the vendor's
class name on somebody else's module. A rule keyed on `StripeClient` would bind it, and every call
on the result would then be attributed to a vendor it never reached. The fixture asserts this
directly, alongside `bucket = boto3.client("s3")`.

**Module names are tracked apart from client names.** `names` accumulates client variables as well
as module aliases; if the constructor's object were checked against that set, every call on an
existing client would become a candidate constructor for another. `modules` holds only what was
bound by importing the vendor's module, and only it may stand to the left of a constructor.

**Only `self`.** `config.client = stripe.StripeClient(k)` is not bound. An attribute of anything
else names an object this walk cannot follow to its call sites, and a rule matching any attribute
target would be binding on the attribute name alone.

This matters more here than at the field step. Two false attributions were fixed in this file
today, both concerning what a bound call records; a false attribution at the *binding* step is
worse, because it produces findings against code that never called the vendor at all rather than
findings that overstate a real call's dependencies.

## Deliberately left, and asserted so

**A client received as a parameter and stored on the instance.**

```python
def __init__(self, given):
    self.given = given          # nothing statically says this is a Stripe client
```

The right-hand side is a parameter name. Binding on it would mean any attribute assigned from any
parameter counted, which is exactly the loose rule the guards above exist to prevent. Closing it
needs the caller's type, which tree-sitter does not give us. `tests/test_python_client_forms.py`
asserts it does *not* bind, so the boundary is read rather than discovered.

**A renamed re-export** — pre-existing, documented, unchanged. Client names match by name across
the repository, so `from .client import stripe_client as billing` binds nothing.

**Roots deeper than two segments**, per `_MAX_CLIENT_SEGMENTS`.

## What this does not fix, and is not supposed to

**A bound call site is not yet a resolved one.** 93 of 179 symbols are unreachable from Python at
all, which is B39 in the other worktree. A fixture here binds `charges.create` because this test's
own specification resolves it; a real repository will bind call sites whose symbols still reach no
operation, and that is the other task's to close. The two are separable exactly here: this one
ends at whether the receiver is recognised as the vendor's client.

**No corpus number moved and none could.** There is still no Python repository in the corpus —
this is the fix that makes pinning one worth doing. The evidence is the fixture and eight
assertions.

## Every behaviour from today's two field-step fixes is unchanged

`tests/test_python_response_binding.py` is the regression net for B34's false attribution through
`dict(...)` and B35's walrus. **All thirteen of its assertions pass and the file was not edited** —
its last commit is still `c077622`, B35's. Nothing in this change touches what a bound call site
records; it changes only whether a receiver is recognised as a client.

## Boundaries

`src/sync/signals/`, `src/sync/index/typescript.py` and `benchmark/` are unmodified.
