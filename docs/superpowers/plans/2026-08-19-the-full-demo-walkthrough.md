# The full demo walkthrough — `npx` to an open pull request

**Owner direction, 2026-08-19.** *"from the very beginning from the NPX command to the very end
pushing that pull request to the git repo… set everything up in between to do a full demo
walkthrough."*

This plan is built from what the tree actually does today, probed rather than assumed. Every claim
below carries the command that established it.

---

## 1. What is already standing

| Fact | Evidence |
|---|---|
| Postgres 16 on 5433 answers | socket probe, `LISTENING` |
| `gh` authenticated as `stroland02` | `gh auth status` |
| Both pinned Stripe specs cached | `.cache/specs/v2320.json`, `v2330.json`, `v2330.sdk.json` |
| The differ runs and the diff is real | `run_oasdiff_breaking` → **81,560** breaking records |
| The demo repo is indexed | `call_site` holds **31** rows for `github.com/stripe/stripe-connect-furever-demo` |
| An `npx` entry point exists and is published | `bin/sync-up.mjs`, `@stroland02/sync-up@0.1.3` |
| A one-command acceptance test exists | `tests/test_e2e_stripe.py`, `@pytest.mark.e2e` |

---

## 2. The five blockers, in the order they bite

### Blocker 1 — the graph has no findings, because Signal never ran here

`vendor_change` is **0 rows** and `finding` is **0 rows** against a database that holds 31 call
sites. Index has run; Signal and Detect have not. The console therefore shows an indexed codebase
with nothing wrong with it, which is the honest rendering of an empty half-pipeline and not a demo.

**Fix:** run Signal + Detect against the cached specs. No credential, no network beyond the cache,
no spend.

### Blocker 2 — the API on 8787 is serving a different graph

`GET /api/repositories` answers `{"repo_ids":["r1"]}` while the database holds the furever demo.
This is exactly the trap `.claude/rules/console-dev-loop.md` exists for: *"A long-lived API process
serves whatever Python it started with, and nothing signals the drift."*

**Fix:** restart the API with `SYNC_API_RELOAD=true` and the DSN stated, and confirm
`/api/repositories` names the demo repository before believing anything on screen.

### Blocker 3 — the loop cannot reach a pull request without a model, and that is structural

This is the one that decides whether the demo can be finished today, and it is not a configuration
oversight. The real v2320 → v2330 diff produces **only response-side** breaking records:

```
response-property-enum-value-added   42,264
response-optional-property-removed   39,296
```

No request property is removed on any operation this application calls — verified directly against
both specs for `/v1/charges`, `/v1/payment_intents`, `/v1/accounts`, `/v1/account_links`, all
unchanged. That is the README's own recorded qualification: *"The vendor change was constructed."*

So every finding the demo can produce is a removed **response** property. The routing matrix has a
mechanical row for exactly that — row 3, `response-field-removed-single-site` → `CODEMOD` — and it
**can never fire**, by design. `sync/route/facts.py` says so in its own docstring:

> `call_sites_reading_field` cannot be established here at all… Row 3, the response-side mechanical
> row, therefore still declines, **and a response-property removal still costs an agent run.**

`SYNC_MODEL`, `SYNC_MODEL_API_KEY` and `SYNC_MODEL_BASE_URL` are all **unset**, and
`resolve_provider` defaults to `unconfigured` deliberately (owner ruling, 2026-08-19: Sync never
inherits the installer's credential).

**Therefore: the walkthrough reaches Detect with no credential and no spend, and cannot reach
Remediate or a pull request without one.** There is no cheaper path today, because the only
mechanical route to a patch is unreachable for the only change kind the demo produces.

### Blocker 4 — no fork is configured to push to

`SYNC_E2E_REPO` is unset. A pull request needs a repository the operator owns; the recorded run used
a fork of `stripe/stripe-connect-furever-demo`. `run --repo` refuses a local path by design and takes
a remote.

### Blocker 5 — the acceptance path has drifted

The README records it: the e2e test *"has not re-executed since the pipeline changed underneath
it"* — the tier cascade, the push guard, branch deletion on abandonment and the dependency-edit
guard all landed on that path afterwards. **The first execution is a test of the pipeline, not a
demo rehearsal**, and should be budgeted as one.

---

## 3. The walkthrough, staged by what it costs

**Stages A–D need no credential and no spend, and are worth doing first regardless of the ruling on
stage E.**

### Stage A — install, from nothing
`npx @stroland02/sync-up` on a machine with no checkout, to the console password prompt. What the
package can do without a checkout is check the machine and hand over the clone that works (`B190`
carries the prebuilt image that closes the rest). The from-checkout path is `npm run no-admin`.

**Verifies:** the published entry point resolves and the honest boundary is where the README says.

### Stage B — the console comes up against a real graph
`npm run no-admin` → embedded Postgres, schema, API, console. Then the check Blocker 2 demands:
`/api/repositories` must name the demo repository.

**Verifies:** schema applied, API bound to the right DSN, console reachable.

### Stage C — Index: your own code on the screen
`uv run sync index --repo <checkout>` writes call sites and one `index_run` row.

**Verifies:** the Overview's pipeline strip moves off *never indexed*; Call sites and Services
populate; `last_index_run` renders.

### Stage D — Signal and Detect: the graph gains something wrong with it
Fold the cached specs into `vendor_change` and run the detectors, so `finding` is non-empty.

**Verifies:** Findings, Detectors and the change-unit grouping populate; the pipeline strip's Detect
cell shows a real count. **This is the furthest the demo goes without a credential.**

### Stage E — Remediate and the pull request *(requires the ruling in §2, Blocker 3)*
```
SYNC_E2E_REPO=<your fork> uv run pytest tests/test_e2e_stripe.py -m e2e -v -s
```
which is `sync run --vendor stripe --from-version v2320 --to-version v2330 --repo <fork>`: clone,
index, diff, detect, route, patch via an agent run, `tsc` on the tree a push would carry, push the
branch, open the pull request via `gh`.

**Verifies:** the claim the product is built to make. Costs a model run per attempted finding and
ends at a real pull request on a real repository.

---

## 4. Tasks

1. **Restart the API against the demo DSN** and assert `/api/repositories` names it. (Blocker 2)
2. **Run Signal + Detect** from the cached specs; assert `finding` is non-empty and the console's
   Detect cell agrees with the row count. (Blocker 1)
3. **Walk stages A–C in a terminal** and record what each screen shows, so the walkthrough is a
   script somebody else can follow rather than a memory.
4. **Write `docs/demo-walkthrough.md`** — the ordered commands with the expected screen after each,
   and the two honest stops (no credential → stage D; no fork → no pull request).
5. **Stage E, once ruled on:** create or name the fork, export the three model variables, run the
   acceptance test, and record the result and its cost.
6. **Re-point `test_day_one_path.py`** at the walkthrough doc if it becomes the documented path, so
   the commands stay held against the CLI the way the README's already are.

---

## 5. What this plan refuses

- **Constructing a vendor change to make the demo work.** The recorded M0 run did that and said so.
  A walkthrough that quietly hand-edits a spec to manufacture a breaking change is a demo of the
  demo. If a constructed change is wanted for the story, it is a labelled fixture and the screen
  says the change was constructed.
- **Inheriting a credential.** `resolve_provider` refuses `ANTHROPIC_API_KEY` on purpose; the
  walkthrough exports `SYNC_MODEL_API_KEY` explicitly or stops at stage D.
- **Pushing to anything but a fork the operator owns.**
- **Claiming stage E passed until it has been executed once against the current pipeline.** Blocker 5.

---

## 6. Ledger

| # | Decision | Against | Why |
|---|---|---|---|
| 1 | Stages A–D ship before the credential ruling | Waiting for stage E to plan anything | Four of five stages cost nothing and prove most of the product; blocking them on a spend decision idles the demo |
| 2 | The response-side finding costs an agent run, and the plan says so | Presenting the demo as free | Row 3 cannot fire — `facts.py` states it — so a plan promising a mechanical patch would fail at the moment it mattered |
| 3 | The API is restarted before anything is believed | Reading the console as-is | It is serving `r1` against a database holding the demo; the rule for this exact trap is already written |
| 4 | No spec is hand-edited to force a finding | A more impressive walkthrough | The real diff yields 81,560 records and real findings; a manufactured one would be the second thing the README already had to qualify |
