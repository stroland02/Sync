# Sync — The Routing Matrix

**Date:** 2026-07-27
**Status:** Specified. The table is binding on any tier routing added to the remediation graph.
The learned policy is deferred with a stated trigger.
**Scope:** How a `Finding` is routed to the cheapest strategy that will actually work, and how
that routing stays auditable and provably complete as oasdiff's rule set grows.

## The problem

Today there is no routing. `src/sync/remediate/graph.py` sends every finding to one
`remediator`, and `patch` calls a full agent loop regardless of how mechanical the change is.
That is correct for a walking skeleton and wrong for the economics: the stated advantage is
"knowing which change kinds are safely mechanical is what lets Sync skip a model call and beat
competitors on both cost and merge rate." A model call for a change a codemod handles is pure
cost, and worse, it is nondeterministic cost against a deterministic problem.

The naive fix — a big `if` chain over change kinds — fails for a reason worth stating before
designing around it.

## What the domain actually looks like

Measured from the pinned binary, `oasdiff 1.26.1`, via `oasdiff checks --format json`:

| | Count |
|---|---|
| Total checker rules | **506** |
| `level=error` | 212 |
| `level=info` | 264 |
| `level=warning` | 30 |

`VendorChange.kind` is `record["id"]` — one of those 506 identifiers. **A hand-written table
with 506 rows is not maintainable by one person, and would silently rot on every oasdiff
release.** That is the constraint the design has to survive.

The escape is that each rule carries structured metadata, and routing can key on the metadata
rather than on the identifier. Across the 212 breaking rules:

| Axis | Distribution |
|---|---|
| `direction` | request 118, response 81, none 13 |
| `kind` | structure 54, constraints 54, type 25, existence 24, lifecycle 21, values 20, requiredness 14 |
| `action` | change 60, remove 57, add 43, decrease 25, increase 22, generalize 4, specialize 1 |

Seven `kind` values and eight `action` values is a grid a person can reason about. Five hundred
and six identifiers is not.

## Two facts about oasdiff that the current code loses

Both were found by running the pinned binary against the committed fixture pair, and both bear
on routing.

**`oasdiff breaking` returns warning-level records, not only errors.** The fixture pair
produces exactly two records — `request-property-removed` and
`response-optional-property-removed` — and `oasdiff checks` classifies **both as
`level=warning`**, not `error`. Neither appears in the 212-rule breaking set. So the output of
`run_oasdiff_breaking` is a mix of severities, not a uniform one.

**`to_vendor_changes` discards that severity.** It sets `severity="breaking"` unconditionally
for every record. An endpoint deleted without deprecation and an optional response property
removed arrive downstream indistinguishable. Routing wants that distinction — it is one of the
three or four things most predictive of whether a change is mechanically patchable — and today
it is thrown away one line after being received.

A related trap for whoever fixes this: the JSON records from `oasdiff breaking` carry `level`
as an **integer** (the fixture's two records both report `level: 2`, which cross-references to
`warning` in `oasdiff checks`), while `oasdiff checks` reports `level` as a **string**. The two
surfaces do not agree on the type, and only the warning value has been confirmed by
cross-reference here. Anything mapping between them must verify the encoding rather than assume
it.

**Preserving oasdiff's level is a prerequisite for this design**, and it is deliberately not
done in this document: `severity` flows into `Finding`, which the MCP graph surface consumes,
so it is a contract change that wants its own task rather than a drive-by edit.

## The tiers

Four, not three. The zeroth is the one an implementation would otherwise miss.

| Tier | Strategy | Cost |
|---|---|---|
| **−1** | **No patch.** Report only. | Nothing |
| **0** | Deterministic codemod. No model call. | Nothing |
| **1** | Constrained model call — a single edit against a named template. | One call |
| **2** | Full agent loop, as today. | Many calls |

### Tier −1 exists because 21 breaking rules are not about the consumer's code

`kind=lifecycle` covers 21 of the 212 breaking rules, and reading them makes the category
obvious:

```
api-deprecated-sunset-missing        endpoint deprecated without sunset date
api-deprecated-sunset-parse          endpoint deprecated with invalid sunset date
api-invalid-stability-level          invalid stability level
sunset-deleted                       sunset deleted
api-sunset-date-too-small            deprecated endpoint sunset before min required deprecation days
```

Every one of these is a complaint about **how the vendor documented a deprecation**. None
describes a change to the shape of anything the customer's code sends or receives. There is no
edit that resolves `api-deprecated-sunset-missing` in a consumer's repository, because the
defect is in the vendor's specification.

Routing these to an agent produces a confident patch against code that was never wrong. That is
the most expensive failure mode available — it spends the reviewer trust that the whole
precision-over-recall position exists to protect. They are real findings and worth surfacing;
they are simply not remediation findings.

## The table

Default-deny. A finding reaches tier 0 only by matching an explicit rule; everything unmatched
falls through to tier 2. The fall-through direction matters: an unrecognised change routed to an
agent costs money, while an unrecognised change routed to a codemod corrupts code.

Evaluated top to bottom, first match wins — DMN's `FIRST` hit policy, which is the only one
that makes the ordering itself part of the specification rather than an accident.

| # | `kind` | `action` | `direction` | Additional condition | Tier |
|---|---|---|---|---|---|
| 1 | `lifecycle` | any | any | — | **−1** |
| 2 | any | any | any | `changed_field()` is `None` **and** the rule is field-scoped | **2** |
| 3 | `existence` | `remove` | `response` | field is read at exactly one call site | **0** |
| 4 | `existence` | `remove` | `request` | field is passed as a literal, not a variable | **0** |
| 5 | `requiredness` | `change` | `request` | the property already has a value at the call site | **−1** |
| 6 | `existence` | `add` | `request` | the added property is required | **1** |
| 7 | `type` | any | any | — | **2** |
| 8 | `structure` | any | any | — | **2** |
| 9 | *(fall-through)* | | | | **2** |

Rows 3 through 6 are the entire tier-0 and tier-1 surface, deliberately. Each carries an
**additional condition drawn from the call site, not from the change** — which is the point of
having an API Dependency Graph at all. "A response property was removed" is not enough to
justify a mechanical edit. "A response property was removed *and* exactly one call site reads
it" is.

Row 5 is worth reading twice: a request property becoming required needs no patch **when the
call site already passes it**. The graph knows that. Without the graph you would have to guess,
and guessing means either a needless PR or a missed break.

## Why a decision table rather than an `if` chain

The same logic in a conditional chain is untestable in the way that matters. Three properties
come from making the table data:

**Completeness is checkable.** Every rule ID `oasdiff checks` emits either matches a row or
provably reaches the fall-through. A test asserts this against the pinned binary, so a new
oasdiff release that adds a check fails CI rather than silently routing an unknown kind. This
is the property that makes the design survive a dependency that grows.

**Overlap is checkable.** Two rows whose conditions can both be true, with different tiers, is a
contradiction — findable by inspection when the rows are data, invisible when they are nested
`if`s.

**The routing decision is loggable as data.** `migration_outcome` already has `strategy` and
`tier` columns. With a table, the row number that fired is recordable too, which is what makes
"tier 0 was wrong for this kind" an answerable question later instead of an archaeology project.

RETE and a production-rule engine are the wrong tool here and are named so nobody reaches for
them: RETE's incremental matching pays off across thousands of rules and a continuously mutating
fact base. This is nine rows evaluated once per finding.

## Where it goes in the graph

The insertion point already exists. `src/sync/remediate/graph.py` has:

```python
builder.add_conditional_edges(
    "prepare",
    nodes.route_after_prepare,
    {"patch": "patch", "abandon": "abandon"},
)
```

Routing becomes additional destinations out of that same node — a codemod node and a report-only
node alongside `patch` and `abandon`. `RunState` gains `tier` and `strategy`, which
`migration_outcome` already expects as columns, so nothing downstream needs inventing.

`route_after_static` already models the discipline any new predicate must follow: it branches on
`verify_ok`, an explicit boolean a node set deliberately, rather than on whether `diagnostics`
happens to be non-empty. A real `tsc` failure can exit non-zero with nothing on either stream.
Routing predicates read state that was set on purpose.

## The learned policy, and when it is allowed

Not now, and the trigger is stated so the question is settled rather than revisited.

The table is the policy until `migration_outcome` holds enough labelled attempts to evaluate an
alternative **offline** — that is, to score a proposed policy against logged outcomes without
deploying it to real pull requests. That capability, not row count, is the gate: routing errors
here cost a wrong patch against a real repository, so a policy that has only been evaluated
online has been evaluated on customers.

Two things must be true before that evaluation is even possible, and both are cheap to arrange
now:

- **Every attempt records the tier that was chosen and the row that chose it**, including
  attempts that were abandoned. Abandoned attempts are the negative class; a corpus of successes
  alone cannot evaluate a router.
- **Features are computed by one shared function**, used both when routing live and when fitting
  offline. Two implementations that agree today diverge on the first edge case, and the failure
  is silent — good offline scores, bad live routing.

The minimum sample count at which a learned policy beats a fixed table is a real number in the
contextual-bandit literature, and this document does **not** state it, because the research pass
that would have established it did not complete. Do not invent one. Establish it, or keep the
table.

## Verification

- **Completeness against the pinned binary.** Parse `oasdiff checks --format json`; assert every
  ID either matches a row or reaches the fall-through, and that the fall-through is tier 2. Pin
  the oasdiff version in CI so this test means something — it is already pinned to 1.26.1 in
  `.github/workflows/ci.yml` for exactly this reason.
- **No two rows contradict.** For every pair of rows assigning different tiers, assert their
  conditions are disjoint or that the earlier row is intended to win, with the intent recorded.
- **Tier −1 emits no patch.** A `lifecycle` finding must produce a report and reach `END`
  without entering `patch`. Assert on the node sequence, not on the absence of a diff — a patch
  node that ran and produced nothing is a different bug wearing the same result.
- **Every tier-0 rule is proven on a fixture pair** where the codemod's output is asserted
  exactly. A mechanical transform whose result is not pinned is not mechanical.
- **The routing decision reaches the corpus.** Assert `migration_outcome.tier` and `.strategy`
  are populated from the real routing decision, not defaulted. A column that silently stays null
  destroys the only measurement that would justify the next version of this table.
