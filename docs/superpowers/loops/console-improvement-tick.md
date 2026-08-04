# Console improvement tick

A repeating prompt for the operator console. Paste it, schedule it, or hand it to a fresh session.
It assumes nothing about what came before except this repository.

It is modelled on the "Autonomous Sync build tick" that drove the backend milestones, and it keeps
that loop's one rule: **work the loop without asking, and never end a tick by asking whether to
continue.** `.claude/rules/autonomous-development.md` names the three things that are still the
human's.

---

## The tick

**1. Read the ground truth before deciding anything.**

- `docs/superpowers/plans/2026-07-30-sync-m4-dashboard.md` — the console's plan, its architectural
  spine, and its **Deferred, deliberately** table. That table is the feature backlog for this loop.
- `CLAUDE.md` and `.claude/rules/` — binding on everything.
- `git log --oneline -15` on `main`. Several sessions push here. Something you are about to build
  may already exist.
- The plan's SDD ledger under `.superpowers/sdd/2026-07-30-sync-m4-dashboard/progress.md`, which
  carries every ruling and every deferred minor from earlier ticks.

**2. Measure the console against the product position, not against taste.**

The console exists because competing tools present a black box and a result, and ask a reviewer to
trust output on faith. Sync checkpoints every node of the remediation graph, so the console can show
`locate → patch → static verify → push → await CI → open PR` **as it happened**, with the evidence
at each step and failed attempts still visible with the reason they were abandoned.

Every tick, ask the four questions that follow from that, in order. The first one that answers "no"
is the tick's work.

1. **Is anything the operator needs to see missing from the screen?** A field the API returns and
   the console drops is a regression against the whole point.
2. **Is provenance rendered everywhere a binding is shown?** `binding_source` and `indexed_at`, at
   both levels — the per-row rung on a finding, and the page-level rung that is null whenever a
   page mixes rungs. A console that hides which rung produced a binding is worse than the payload
   it renders.
3. **Does every state say what happened?** "No findings", "the API is not running", "that finding
   is not open", and "still loading" are four different sentences. A spinner that never resolves
   and a silent empty table are both failures.
4. **Is the top item of the Deferred table now worth building?** Each row in that table names the
   condition that retires it. Check the condition, not the appetite.

**3. Take exactly one item, and take it through the loop.**

Use `superpowers:subagent-driven-development`: dispatch one implementer, review it for spec
compliance and quality, run the fix loop, record the outcome in the ledger. One item per tick. A
tick that lands one reviewed improvement beats a tick that starts four.

Prefer, in this order:

1. A correctness or honesty defect from question 1, 2 or 3.
2. A deferred minor from the ledger whose cost has grown.
3. The top Deferred-table row whose retiring condition is now met.

**4. Verify before claiming.**

`npm run build` from `web/` must succeed with pristine output — it reached zero warnings in Task 1
and staying there is a gate, not a preference. Where a change is visible rather than structural,
run the API and look:

```bash
docker compose up -d
SYNC_GRAPH_DSN=postgresql://sync:sync@localhost:5433/sync SYNC_API_PORT=8787 uv run python -m sync.api
cd web && npm run dev
```

Record what you saw, not that you looked.

**5. Close the tick.**

Append to the ledger: what shipped, its commit range, and what the next tick should look at first.
Then stop. Do not ask whether to continue.

---

## The deferred features, and what retires each

Copied from the plan so a tick does not have to re-derive them, and annotated with the condition to
check rather than the appetite to consult.

| Feature | Retires when |
|---|---|
| `framer-motion` transitions | The layout has stopped moving. Motion over a layout still in flux is work thrown away twice. |
| `@react-three/fiber` scenes | Something in the domain is actually spatial. A 3D element that illustrates nothing is decoration. |
| Premium components, bento grids | The data model is visible on screen. These are a design-system decision and the design system comes after. |
| `react-grid-layout` draggable widgets | A user knows what they want on screen. The first version is what answers that. |
| MUI fallback for enterprise grids | A specific grid defeats shadcn. Two design systems is a cost paid per component, not up front. |

All five packages are installed already, so none of these needs a stack change — only a reason.

## The reference libraries, consulted per milestone

On 2026-07-27 a set of references was handed to this project with an explicit instruction: *"lets
add these resources into when we are building in milestones so we look at them when needed and not
all now."* This section is that instruction applied to the console. Read the one whose column you
are working in, not the list.

| Working on | Read |
|---|---|
| Interface quality, polish, the details that separate a tool from a demo | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) |
| Which frontend skill or concept the console is leaning on next | [iamgini/roadmap.sh](https://github.com/iamgini/roadmap.sh) |
| A view that has to stay fast as the graph grows | [donnemartin/system-design-primer](https://github.com/donnemartin/system-design-primer), [binhnguyennus/awesome-scalability](https://github.com/binhnguyennus/awesome-scalability) |
| Paging or retrieval over a large payload | [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex) |
| A vendor surface the console needs to name | [public-apis/public-apis](https://github.com/public-apis/public-apis) |
| Running or hosting the console somewhere | [awesome-selfhosted/awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted), [ripienaar/free-for-dev](https://github.com/ripienaar/free-for-dev) |
| General tooling and operational knowledge | [trimstray/the-book-of-secret-knowledge](https://github.com/trimstray/the-book-of-secret-knowledge) |

## The interface is ours

`.claude/rules/interface-originality.md` binds every tick. Competitors are studied for concepts,
ideas, and efficient workflows and pipelines — never for how a screen should look. The eighteen
screenshots under `docs/superpowers/references/screenshots/` are a research artifact, not a design
target, and the rule exists because a directory of screenshots usually is one.

The test to apply before building anything a reference suggested: state it as a problem the operator
has, without naming the product it came from. If it cannot be stated that way, it has not been
understood well enough to build.

## What a tick must not do

- **Do not restyle ahead of the data.** Functionality before polish is a plan constraint, not a
  preference. A beautiful console showing the wrong rung is a failure; a plain one showing the right
  rung is a success.
- **Do not add a route the graph cannot answer.** A screen that needs data the graph does not hold
  is a question about the graph, and it belongs in a plan rather than in a component.
- **Do not reach past the HTTP transport.** The console consumes `src/sync/api/`, which consumes
  `GraphSurface`. A field the console needs that the surface does not expose is a change to the
  surface, reviewed against the frozen-tool rule — never a bypass into `GraphStore`.
- **Do not mutate.** Every route is a GET. Acting on a finding is a later slice with its own
  authorization story.
- **Do not skip the review.** An unreviewed improvement is churn with a commit message.
