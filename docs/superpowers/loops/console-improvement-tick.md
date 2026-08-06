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
- `docs/superpowers/plans/2026-08-06-sync-console-expansion.md` — the slice in execution as of
  2026-08-06, and the one that names which four workstreams are live. **Read it before taking an
  item**, because four agents are working in their own Orca workspaces
  (`orca/workspaces/Sync/m4-repository`, `m4-idiom`, `m4-signals`, `m4-conformance`), each on a
  branch based on `m4-dashboard`, and the item you were about to take may be someone's brief.
  `orca orchestration task-list --brief --json` says which are still dispatched.
- The authority above every plan is
  `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md`, section *M4 — Hosted
  control plane / Information architecture*, **second fenced block**. A plan is a plan; the
  specification is what a screen is checked against, and three plans built a hierarchy without
  opening it.
- `CLAUDE.md` and `.claude/rules/` — binding on everything.
- `git log --oneline -15` on `main`. Several sessions push here. Something you are about to build
  may already exist.
- The plan's SDD ledger under `.superpowers/sdd/2026-07-30-sync-m4-dashboard/progress.md`, which
  carries every ruling and every deferred minor from earlier ticks. **It is gitignored**, so it exists
  in one worktree on one machine and a worker in an Orca workspace has no copy of it. When you cannot
  open it, that is why, and it is not a sign that nothing was recorded.
- `docs/superpowers/reports/2026-08-06-m4-session-record.md` and any later dated sibling — the tracked
  half of the same record, which every checkout can actually read. A session that lands something
  another session must know about writes it there, not only into the ledger.

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

**The seven-item interface-quality checklist.** Copied from
`docs/superpowers/references/notes/impeccable-interface-quality.md:328-417`, unparaphrased, because
those seven ask something the four questions above do not: whether what *is* rendered can actually
be read. Run them after the four questions, on every tick that touches a screen.

Before the list: the one command, and its precondition. If the detector is installed, the fastest
way to answer items 1, 3, 4, 5 and 7 at once is a URL scan of each route. It is only valid if the
browser engine actually runs:

```bash
node -e "require.resolve('puppeteer')" || echo "URL SCAN INVALID — see section 5"
npx impeccable detect --no-advisory --viewport 1280x800 \
  http://localhost:5173/ \
  http://localhost:5173/vendors/stripe \
  http://localhost:5173/findings/<id> \
  http://localhost:5173/findings/<id>/workflow
```

Exit 2 means findings; exit 0 means either clean **or** that the browser engine was missing and the
scan silently did nothing. Never record a clean result without the first line passing.

1. **Did a full walk of Codebase → API Services → Errors & Incidents → Finding → Solution Workflow
   leave the browser console empty?** (`script-error`, one of only two rules carrying
   `severity: 'error'`.) It is first because in React 19 an uncaught exception unmounts a subtree and
   leaves nothing behind, which is the silent version of question 3 above: the state does not say
   what happened, because there is no state. This console has two places a transport change lands
   first — `run-outcome.tsx:121-130`, the branch for an outcome the console has never heard of, and
   `evidence.tsx:285-293`, which renders unnamed evidence keys through `JSON.stringify` — and both
   are reached by data, not by clicking. A tick that answers the other six while the console throws
   has measured the wrong thing.

2. **At a 1280px window, on the Errors & Incidents table, is the Rung column on screen without
   scrolling the table sideways?** (No rule id; `text-overflow` is structurally blind to this — see
   the note's section 5.) `vendor-findings-table.tsx` renders seven columns with Rung sixth, and
   every header and cell carries `whitespace-nowrap` inside a `w-full overflow-x-auto` container.
   The widest cell is `{row.file}:{row.line}`, a path supplied by a customer repository, and no
   fixture will be long enough to catch it. The failure is that the provenance column — non-
   negotiable under question 2 above — slides out of the viewport. Question 2 asks whether
   provenance is rendered; this asks whether it is visible.

3. **On each page, does the heading outline descend without skipping a level?**
   (`skipped-heading`.) It earns its place over every other accessibility rule because the
   console's navigation hierarchy *is* the dependency graph, and the heading tree is the only
   machine-readable assertion of which level of that graph you are looking at.

4. **Can you tell a page title, a card title and a row label apart at a glance?**
   (`flat-type-hierarchy`.) This is the one `slop` rule that earns a place, because "unstyled
   beyond legibility" fails at exactly this seam: with no design system, every level of a
   six-level hierarchy renders at nearly the same weight and the operator loses their place.

5. **On a 1920px window, does the prose in an error, empty or abandoned-run panel wrap at a
   readable measure?** (`line-length`, which fires above roughly 85 characters and only inside
   `p/li/td/th/dd/blockquote/figcaption`.) Tables want the whole viewport and paragraphs do not,
   and this console mixes both on one screen. Evidence nobody reads is the same failure as evidence
   not shown. The `<pre>` blocks (`evidence.tsx`, `max-h-72 overflow-auto whitespace-pre-wrap`) are
   already correct and are not what this asks about.

6. **Tab to the Next button inside a card. Is its whole focus ring visible?**
   (`clipped-overflow-container`.) A Card with `overflow-hidden` clips a focus ring drawn as a
   box-shadow. It also covers any future tooltip or popover added without a portal. Keyboard focus
   is a states question no screenshot answers.

7. **Is anything on screen rendered below 11px?** (`undersized-ui-text`, whose floor is 11px and
   whose "furniture" selector explicitly covers `td`, `th` and anything classed `meta`, `label` or
   `badge`.) It earns its slot because the standing temptation of a data-dense console is to reach
   for `text-[10px]` the next time a table gets crowded, and the rule's own docstring records that
   exact failure shipping once already, waved through because the size was on the design ramp.
   **Being on `DESIGN.md`'s ramp does not exempt a value from this floor.**

**This standings list is stale and is being replaced by a measurement.** The workstream at
`docs/superpowers/briefs/2026-08-06-m4-conformance-measurement.md` re-measures all seven items, plus
the fourteen invariants three reference surfaces agreed on, against the running console with the
commit SHA recorded on every table. When
`docs/superpowers/reports/2026-08-06-console-conformance.md` exists, read that instead of what
follows and delete this paragraph along with the list under it. Until then the list below is the
best record there is, and several design-system tasks have landed since it was written — **re-check
an item against the running tree before acting on it.**

**Where each item stood, checked against the tree at `72450ae` (2026-08-05), after Task 1 of
`docs/superpowers/plans/2026-08-05-sync-console-design-system.md` landed and before Tasks 2-7:**

- **Item 7 is already closed**, and stays closed rather than being newly fixed: the console's floor
  was 12px before this slice and still is. Task 1 gives that floor a name — `meta`, 12px, a floor
  and not a suggestion — in `DESIGN.md`, which is what keeps a future crowded table from reaching
  for `text-[10px]` instead of quietly regressing it.
- **Items 2, 3, 4, 5 and 6 are open.** Each has a task and a step that closes it once landed — item
  2 is Task 4 Step 4, items 3 and 4 are Task 3 Steps 1-2, item 5 is Task 4 Step 5, item 6 is Task 4
  Step 3 — and none of those steps had landed as of `72450ae`: every `h1` in the tree is still
  `text-lg` (`finding-page.tsx:77`, `fleet-page.tsx:24`, `overview-page.tsx:33`,
  `vendor-page.tsx:29`, `workflow-page.tsx:96`), `card.tsx` still sets `overflow-hidden`
  unconditionally, and `vendor-findings-table.tsx` still lists Rung sixth, after Call site. Re-check
  each against the running tree rather than trusting this note once those tasks land.
- **Item 1 is open and this slice does not close it.** The design system changes colour, type,
  space, elevation and motion; it does not touch `run-outcome.tsx`'s outcome branch or
  `evidence.tsx`'s unnamed-key rendering. It stays a tick item in its own right.

**The detector's status here, and why the scan above is not wired into an automated step.**
Checked in this worktree on 2026-08-05: `impeccable` is not a dependency of `web/package.json`, is
not resolvable via `npx --no-install`, and is not installed globally; `node -e
"require.resolve('puppeteer')"` fails with `MODULE_NOT_FOUND`. The precondition in the command
block above is written into this tick regardless of that, because it must hold before any future
session trusts a scan's exit code — a URL scan run without puppeteer prints one line to stderr and
exits **0**, which a tick reads as clean when it means the opposite:
`impeccable-interface-quality.md:207-223`. Until the detector is installed here, answer the seven
items by hand against the running dev server, as the rest of this tick already does for questions
1-4. If it is installed later, the precondition command must run and pass before any exit code from
the scan is trusted — do not skip straight to the `npx impeccable detect` line.

**3. Take exactly one item, and take it through the loop.**

Use `superpowers:subagent-driven-development`: dispatch one implementer, review it for spec
compliance and quality, run the fix loop, record the outcome in the ledger. One item per tick. A
tick that lands one reviewed improvement beats a tick that starts four.

Prefer, in this order:

1. A correctness or honesty defect from question 1, 2 or 3.
2. A deferred minor from the ledger whose cost has grown.
3. The top Deferred-table row whose retiring condition is now met.

**3a. When another agent holds `web/`, work the other half of the lane.**

Written on 2026-08-05, after six consecutive ticks arrived while a design-system fan-out was live in
this worktree and each one had to re-derive the same answer.

The instruction a tick starts from is *if the tree is dirty and moving, another agent is live, so
stop and write nothing*. That is right about the **files** and wrong about the **tick**. The
sentence exists to stop a tick committing on top of half-finished work, and `git commit -- <path>`
already stops that — it takes only the named path and leaves another agent's staged and unstaged
work untouched. Six ticks committed alongside a live fan-out that way and swept nothing.

So a busy `web/` closes one half of this session's lane and leaves the other open. `src/sync/api/`,
`src/sync/dashboard/` and `docs/` are reachable the whole time, and the console's honesty defects
are not all in TypeScript — of the six taken during that fan-out, four were transport or view-model
correctness and one was a governing document that had started to misinform.

The rules that made it safe, all of them learned the hard way:

- **Confirm the tree is moving before assuming it is.** Compare mtimes against the clock. A clean
  tree is not proof nobody is live: an agent that has read for ten minutes and written nothing looks
  identical to an idle one, and the fan-out's foundation agent held `web/` for twenty-two minutes
  before its first write.
- **Commit path-limited, always.** Never a bare `git commit`.
- **Do not run `npm run build`, `npm run lint` or `npm run dev`.** `tsc -b` writes build state and
  `vite build` writes `dist/`; two at once corrupt each other. Typecheck with `npx tsc --noEmit -p
  tsconfig.app.json`, which writes nothing — or take work that needs no frontend gate at all.
- **Do not write the database while another agent is walking the console against it.** Reads are
  fine. A test that inserts checkpoint rows is not, while somebody is looking at a screen that
  renders them.
- **Do not add a third payload field nothing renders.** Two additive fields waiting for a consumer
  is a queue; three is a backlog, and the value of the first two falls the longer they sit
  unrendered. When the only remaining transport work is a field the console cannot yet display, that
  is the signal to take a documentation or process item instead.

**Do not cross into another session's paths to stay busy.** `docs/superpowers/ORCHESTRATION.md`
states the boundary as directories. An edit outside it buys a merge conflict, and being blocked is
not an argument that outranks the boundary — check whether the other session is live, record the
ruling, and take something else.

**4. Verify before claiming.**

`npm run build` from `web/` must succeed with pristine output — it reached zero warnings in Task 1
and staying there is a gate, not a preference. Where a change is visible rather than structural,
run the API and look:

```bash
docker compose up -d
SYNC_GRAPH_DSN=postgresql://sync:sync@localhost:5433/sync SYNC_API_PORT=8787 uv run python -m sync.api
cd web && npm run dev
```

If the database this points at is empty, every screen renders an honest-but-useless empty state and
nothing checked above is actually being verified. Four separate rounds hit exactly that, each one
writing a throwaway script to insert some rows and deleting it afterward. That knowledge is now
committed: `scripts/seed_console.py` writes at least two vendors, several call sites and vendor
changes, open findings across more than one `binding_rung`, a finding retried across two
checkpointer generations, a live run and a terminal run, and `migration_outcome` rows where
`attempts` and `distinct_findings` differ — enough for every console screen to show something real.
Every row it writes is tagged `seed-console`, so it removes exactly what it inserted and nothing
else:

```bash
uv run python scripts/seed_console.py            # write the fixture (idempotent -- safe to re-run)
uv run python scripts/seed_console.py --remove    # delete it again, leaving everything else alone
```

Record what you saw, not that you looked.

**Stop both processes when the check is done.** A `python -m sync.api` or `npm run dev` left
listening past the end of a tick is not idle — it holds port 8787 or 5173 for the next session, which
then has to `taskkill` it before it can run its own verification. Ctrl-C both, or `taskkill` by PID,
before closing the tick.

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

## Skills to invoke while building this console

These are installed and apply to console work. Invoke the relevant one before writing code, not
after, because each changes what you would write rather than reviewing what you wrote.

| Skill | Invoke it when |
|---|---|
| `dataviz` | **Before the first line of any chart, plot, stat tile, sparkline, meter or dashboard layout.** `echarts` and `echarts-for-react` are installed and unused; the corpus and benchmark views in the plan are the first real call for them. Read it before choosing a chart form or a colour, not after. |
| `elements-of-style:writing-clearly-and-concisely` | Writing or revising any words a person reads on screen — an empty state, an error sentence, a node's purpose, a button. The console's honesty argument is carried in its sentences as much as in its data, and this milestone has already shipped two sentences that were false. |
| `superpowers:test-driven-development` | Any change with a test. The failing test comes first and must be watched failing. |
| `superpowers:systematic-debugging` | Any bug, failing test, or behaviour you cannot explain — before proposing a fix. |
| `superpowers-chrome:browsing` | Verifying a change on screen against a running API. Cheaper than reasoning about what a view will do, and this milestone's worst defects were all invisible in the diff. |

`superpowers:brainstorming` comes before any new screen or capability, and `superpowers:writing-plans`
after it. A tick does not invent a screen; it implements one a plan already argued for.

## The reference notes that apply right now

`docs/superpowers/references/` holds nineteen notes. Three bear on console work as it stands today,
and the rest are for questions this milestone is not asking:

- **`notes/impeccable-interface-quality.md`** — the checklist to run the console against. This is the
  one to open on a tick whose item is quality rather than correctness.
- **`notes/roadmap-frontend-skills.md`** — which frontend concept the console needs next, ordered
  against what it already does.
- **`notes/competitor-interfaces.md`** — concepts only, and read `.claude/rules/interface-originality.md`
  first. Useful for how a run in progress, a refusal, and evidence for a claim are *conceived*, never
  for how they are drawn.

The engineering notes are mostly backend-facing. Two exceptions earn a look from here:
`engineering/testing-strategy.md` when writing a test that asserts on the console, and
`engineering/ci-and-release-engineering.md` when touching the `web` job.

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
