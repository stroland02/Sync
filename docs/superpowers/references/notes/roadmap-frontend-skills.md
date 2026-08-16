# roadmap.sh — frontend track, audited against the M4 operator console

Audited 2026-08-04. Target as briefed: `https://github.com/iamgini/roadmap.sh`, and the roadmap.sh
project it mirrors.

## 1. What this reference actually is

roadmap.sh is a community-maintained index of developer skill trees — an ordered graph of topic
names, where clicking a node opens roughly one paragraph of description and a handful of links to
articles and videos elsewhere. The repository named in the brief, `iamgini/roadmap.sh`, is not the
project: it is a frozen 2019 copy of the roadmap.sh *website application* whose last commit is dated
2019-11-14 and whose message is "Delete .nojekyll" (VERIFIED, `gh api repos/iamgini/roadmap.sh/commits`,
sha `09fa166f56330e8264abf31be02f8726fe5fc4ab`; the repo reports `fork: false` with a null parent, so
it is an uploaded snapshot rather than a tracked fork, and `pushed_at` is `2019-11-14T22:12:03Z`).
The live project lives at `nilbuild/developer-roadmap` — the URL `kamranahmedse/developer-roadmap`
now redirects there — with 363,586 stars and a push on 2026-08-04 (VERIFIED,
`gh api repos/kamranahmedse/developer-roadmap`).

Two structural facts matter before anyone spends time here. First, the upstream repository no longer
contains the site's application code at all: its root tree holds only `.github`, `roadmaps`,
`scripts`, and config files, so the Next.js/Babel/Yarn stack the 2019 snapshot preserves describes
nothing that exists today (VERIFIED, `gh api repos/nilbuild/developer-roadmap/git/trees/master`).
Second, the per-topic content is thin by design. The `testing` node's entire body is one paragraph
plus two links; `accessibility` is one paragraph plus two links, and it accidentally prints "Visit
the following resources to learn more:" twice (VERIFIED, read
`roadmaps/frontend/content/testing@igg4_hb3XE3vuvY8ufV-4.md` and
`accessibility@e-k6EhoxYG9h0x6vWOrDh.md`). The value on offer is the *ordering and completeness of
the topic list*, not instruction. Treat it as a checklist against which to notice an omission, and
never as a source you learn something from.

**Verdict on the audit target.** `iamgini/roadmap.sh` is worth zero minutes; do not open it again.
The upstream project is worth one bookmark, and the bookmark should be the React roadmap rather than
the frontend one — see below.

### The frontend track's actual shape

Fetched from `https://roadmap.sh/frontend.json` (VERIFIED): Internet fundamentals → HTML → CSS →
JavaScript → version control → package managers → build tools (module bundlers, linters and
formatters) → pick a framework → CSS frameworks → testing → then a flat advanced tier holding
authentication strategies, web security, web APIs, web components, TypeScript, SSR, GraphQL,
performance, deployment, accessibility, PWAs, mobile apps and desktop apps. The topic file listing
confirms this and adds a substantial 2026 AI tier that the older public mental model of this roadmap
does not include — `agents`, `mcp`, `skills`, `prompting-techniques`, `streamed-responses`,
`how-llms-work`, `implementing-ai`, `ai-assisted-coding`, `anthropic`, `claude-code`, `cursor`,
`copilot`, `antigravity` (VERIFIED, `gh api .../roadmaps/frontend/content`).

That shape is the problem with using the frontend roadmap for this job. Everything before the
advanced tier, Sync's console has already passed; everything in the advanced tier is either
irrelevant to an internal operator tool or is a whole stack Sync is not on. Roughly ninety percent
of the frontend track is out of scope for M4 before you start reading.

**The React roadmap is the one that answers the brief's question.** Its topic list is where the
"next concepts" actually live: `error-boundaries`, `suspense`, `portals`, `refs`, `context`,
`creating-custom-hooks`, `hooks-best-practices`, `composition`, `react-testing-library`, `vitest`,
`playwright`, `react-aria`, `types--validation`, `zod`, `react-hook-form`, `state-management`,
`tanstack-query`, `tanstack-router` (VERIFIED, `gh api .../roadmaps/react/content`). Use that list,
not the frontend one.

### What the console does today, for grounding

Read-only inspection of the M4 worktree on 2026-08-04 (VERIFIED): `web/package.json` pins Vite 8.2,
React 19.2, TypeScript ~6.0, Tailwind 4.3, `@tanstack/react-query` 5.101, `react-router` 8.3, echarts
6.1, radix-ui and shadcn, linted by `oxlint`, installed with npm (a `package-lock.json` is present).
`web/src/App.tsx` declares four routes plus a catch-all under one `AppShell`. `web/src/api/queries.ts`
calls `useQuery` six times. There is no `Suspense`, no `ErrorBoundary`, and no `React.lazy` anywhere
in `web/src` (VERIFIED, grep over `web/src`). `web/src/index.css` defines fourteen `--color-*` tokens
in a Tailwind v4 `@theme` block and carries a comment pinning the console to one palette because the
dark values do not exist yet.

Two findings from that inspection are worth stating on their own, because they are the kind of thing
a checklist audit exists to catch.

**There is no frontend test tooling of any kind.** No `vitest`, no `@testing-library/*`, no
`playwright`, no `jsdom` or `happy-dom`, no `msw`, no `axe`, and no `*.test.*` or `*.spec.*` file
under `web/src` (VERIFIED, grep over `web/package.json` and find over `web/src`). The repository's
own `CLAUDE.md` opens its process section with "Test first, always", and the console is the one
subsystem where that rule is currently not in force at all.

**Five of the six "deliberately deferred" libraries are already installed.** `framer-motion`,
`@react-three/fiber`, `@react-three/drei`, `three`, and `react-grid-layout` all sit in
`dependencies` — not `devDependencies` — with `@types/three` and `@types/react-grid-layout` beside
them, and `web/src/components/3d/` contains only a README (VERIFIED, `web/package.json` and the
`web/src` file listing). Only the MUI fallback is genuinely absent. Deferred and installed is the
worst of both states: the install cost and the lockfile surface are already paid, and the discipline
the deferral was meant to buy is not being enforced by anything.

## 2. What Sync should adopt, in order

Each item names the roadmap node that proves the concept is considered load-bearing by a source
outside this project, and then says where it lands in the console. The ordering is mine (INFERENCE),
argued from what the console's four views already do.

**1 — Vitest and React Testing Library.** Roadmap nodes `vitest@hVQ89f6G0LXEgHIOKHDYq` and
`react-testing-library` in the React track, plus `testing@igg4_hb3XE3vuvY8ufV-4` in the frontend
track (VERIFIED). This lands as a `test` block in `web/vite.config.ts` and colocated `*.test.tsx`
files beside the four feature pages. Vitest is the right runner rather than Jest specifically because
it reuses the Vite config and transform pipeline the console already has, so adopting it adds a test
command and not a second build (INFERENCE, though it is the reason the roadmap marks Vitest
recommended and Jest an alternative). The gain is not coverage for its own sake: the console's four
views each render a different shape of the dependency graph, and right now nothing anywhere proves
that a finding with an abandoned attempt still renders its `abandon_reason`. That is the product
claim, and it is currently untested.

**2 — Error boundaries.** Roadmap node `error-boundaries@gMHMjsh0i8paLZUH5mDX3`, whose text is
explicit that without one, a render-time throw corrupts React's state and takes the tree down
(VERIFIED). This lands as a boundary wrapping the `<Route element={<AppShell />}>` in
`web/src/App.tsx`, and probably a second one inside the workflow view so one bad node does not take
the sequence with it. The console already handles *fetch* failure carefully —
`web/src/components/states.tsx` distinguishes `ApiStatusError`, `MalformedResponseError`,
`NotFoundError` and `UnreachableApiError` and says which one happened — but a throw during render
bypasses all of it and produces a blank page. A console whose stated position is that failed attempts
stay visible with the reason they were abandoned should not itself fail without a reason.

**3 — Suspense, and route-level code splitting.** Roadmap node `suspense@_F3WMxhzaK9F8_-zHDDMF`
(VERIFIED). This lands in two places. `React.lazy` on the four route elements in `App.tsx` stops
every view from shipping in the initial bundle, which matters more with each view added past the
first three. Separately, `useSuspenseQuery` in `web/src/api/queries.ts` collapses the per-component
`isLoading` ladder into one fallback per route boundary. Take the code-splitting half first; the
query half is a refactor of working code and can wait for a view that actually needs it.

**4 — Accessibility, treated as a testable property.** Roadmap nodes
`accessibility@e-k6EhoxYG9h0x6vWOrDh` in the frontend track and `accessibility-testing` in the
design-system track (VERIFIED). The console has started on this already — `states.tsx` sets
`role="alert"` on the alarm panel — which is why the next step is the mechanical one it is missing:
`react-router` does not move focus on navigation, so a keyboard or screen-reader user who follows a
breadcrumb from Finding to Solution Workflow stays parked where they were. Since the console's
navigation hierarchy *is* the dependency graph, focus that does not follow the route makes the entire
hierarchy unavailable to assistive technology. This lands as a focus-management effect in
`web/src/layouts/app-shell.tsx` and an axe assertion in the test suite from item 1. Roadmap node
`react-aria@RvDfKoa_HIW3QDBfkPv3m` is the fallback if radix's primitives turn out not to cover a
control the console needs, but radix already carries most of this and adopting React Aria on top
would be a second primitives library — read it only when a specific gap appears.

**5 — Zod at the API boundary.** Roadmap node `types--validation@UNlvRp6k3_RDoTAAIEfJ1`, which
states the case exactly: "TypeScript can only help you avoid mistakes during the development. We
can't rely on it to validate a client's input. Zod is a powerful validation library that allows us to
validate: form input, local storage, API contracts" (VERIFIED). This lands in `web/src/api/types.ts`
and `web/src/api/client.ts`, where the Starlette responses are presently typed rather than checked
(INFERENCE — the existence of a `MalformedResponseError` in `web/src/api/errors.ts` says some shape
checking is happening, but I did not read how it is done). Sync's own `CLAUDE.md` already requires
validation at system boundaries and names vendor responses as one; the console's own API is the same
kind of boundary. There is an argument from the product itself here: a tool whose entire thesis is
that API contracts drift silently should not consume its own API on an unchecked type assertion.

**6 — Design tokens and dark mode as one slice, when the design-system slice lands.** The
design-system roadmap is the checklist, and it is unusually complete for this: `defining-design-tokens`,
`functional-colors`, `dark-mode`, `typography`, `spacing`, `sizing`, `breakpoints`, `component-catalog`,
`documentation`, `semantic-versioning`, `accessibility-testing` (VERIFIED, `gh api
.../roadmaps/design-system/content`). This lands in `web/src/index.css`, which is already the right
shape — a Tailwind v4 `@theme` block *is* the token layer, and the file's own comment says a deferred
slice owns the real palette. The gain is that dark mode becomes a second set of token values rather
than a sweep of `dark:` classes across every component, which is precisely why the file currently
pins to one palette instead.

**7 — Streamed responses, but only when a live run view exists.** Roadmap node
`streamed-responses@FyNXhHq1VIASNq-LI7JIu`, which covers the Streams API and server-sent chunking
(VERIFIED). Nothing in the console needs this today; the API is read-only and the Solution Workflow
view renders a run that already finished. Record it here so that when someone wants to watch a
remediation run as it happens, the first move is SSE over the existing HTTP transport rather than
inventing a WebSocket channel.

### One thing the roadmap does not cover that the console will need

There is no virtualization node anywhere in the frontend or React tracks — the closest is
`lists-and-keys`, which is about reconciliation, not windowing (VERIFIED, both content listings).
The console renders findings tables over a real customer codebase, and a table that is fine at fifty
rows is not fine at five thousand. Do not conclude from this roadmap that the topic is unimportant;
conclude that this roadmap's audience is people learning React, not people shipping data-dense
operator tools. Source that one elsewhere when the row counts justify it.

## 3. What to deliberately skip, and the cost of not skipping it

**The entire pre-framework spine.** Internet fundamentals, DNS, hosting, HTML, CSS, JavaScript,
version control, package managers. Nothing here is new to this project.

**Every framework alternative, and SSR with them.** Vue, Angular, Svelte, Solid, Astro, Nuxt,
SvelteKit, Next.js and TanStack Start all have nodes; the console is a Vite SPA on react-router and
staying there. Skipping SSR is the one worth spelling out, because it is the advanced-tier node most
likely to look tempting. SSR buys first-paint and SEO for public pages. The console is an internal
operator tool behind a read-only API, so it has neither concern, and the cost is concrete: a
rendering server in the deployment story where there is currently only static output and a Starlette
process, plus one more place a credential could come to rest in a project whose non-negotiables say
we never hold customer secrets.

**Bundler and package-manager alternatives.** esbuild, Rollup, Parcel, Rolldown, yarn, pnpm, Bun.
Vite 8 already owns the bundling decision and the console is on npm. The root `CLAUDE.md` separately
records that yarn is not installed on this machine, so a yarn-shaped instruction from a tutorial is
an active hazard rather than a neutral one.

**PWAs and service workers.** The cost is not the setup, it is that a service worker is a cache you
now have to invalidate correctly forever. A console showing a stale finding because a worker served
a stale bundle is strictly worse than a console that took another 200ms, and diagnosing it costs a
day.

**Mobile and desktop targets.** React Native, Flutter, Ionic, Electron, Tauri. There is no second
platform on the roadmap for this product.

**Web components, shadow DOM, custom elements.** These are the architectural opposite of shadcn,
which works by copying component source into the repository so it can be edited. Adopting web
components means giving that up and maintaining a styling boundary the Tailwind tokens do not cross.

**GraphQL, Apollo, Relay, urql.** The API is a read-only Starlette service with exactly one consumer.
GraphQL's cost is a schema layer plus a resolver story plus a client cache that duplicates what
react-query already does, in exchange for flexibility that a single first-party consumer does not
need.

**MUI and Chakra.** This matches the existing deferral of an MUI fallback for enterprise grids, and
the reason to keep deferring it is specific: MUI carries its own theming system, and the Tailwind v4
`@theme` tokens in `index.css` do not feed it. Adopting MUI means two component systems, two token
systems, and two sets of dark-mode values in one bundle, and every future palette change has to be
made twice.

**The whole 2026 AI tier of the frontend roadmap.** `agents`, `mcp`, `skills`,
`prompting-techniques`, `how-llms-work`, `implementing-ai`, `anthropic`, `claude-code`, `cursor`,
`copilot`, `antigravity`. Sync is built on this material; the roadmap's treatment is one paragraph
and a YouTube link per node. Reading it costs an hour and returns nothing this project does not
already know in more depth than the source has.

**Animation, for now — but resolve the installed-and-deferred contradiction.** The React roadmap
places `animation`, `framer-motion`, `react-spring` and `gsap` as leaves rather than prerequisites
(VERIFIED, React content listing), which supports the existing decision to defer them. The
contradiction is worth a decision rather than drift: `framer-motion`, `three`, `@react-three/fiber`,
`@react-three/drei` and `react-grid-layout` are in `dependencies` right now. Either move them out
until a slice claims them, or stop describing them as deferred. Left as-is, the first person to
`import` one of them will do it without anyone deciding, because nothing in the repository is
stopping them.

## 4. Who should consult this, and what it answers

**M4, the operator console — this is the only consumer.** The question it answers is "the console has
outgrown its first three views; what is the next frontend concept worth adding, and what can I safely
never learn?" The answer is section 2 in order, and the meta-answer is that the *React* roadmap, not
the frontend one, is the list to check against. Re-read this note when a fifth view is proposed or
when the test-tooling gap in item 1 is finally closed.

**A future design-system or premium-components slice.** The design-system roadmap's topic list is a
usable pre-flight checklist for that slice — it names the token, dark-mode, catalog, documentation
and versioning decisions that are easy to skip and expensive to retrofit. That is the second and last
reason to open this reference.

**Nobody else.** INDEX, SIGNAL, DETECT, the remediation pipeline, `sync.core`, the vendor adapters
and the graph schema get nothing from this reference at all. It is a frontend learning index; it has
no opinion about dependency graphs, binding rungs, idempotent stages, or anything else this project
is actually hard at. If a future brief points a backend or pipeline agent at roadmap.sh, that brief
is misrouted.

### Could not verify

The upstream repository no longer publishes the roadmap graph structure as a file — `roadmaps/frontend`
contains only a `content` directory, and there is no `frontend.json` in the tree (VERIFIED). The
section ordering in this note therefore comes from `https://roadmap.sh/frontend.json`, a live site
endpoint rather than a versioned artifact, so it cannot be pinned to a commit and may reorder without
notice. I also did not read `web/src/api/types.ts`, `client.ts` or `errors.ts` beyond their names,
because other agents were editing that tree during this audit; the claim in item 5 about unchecked
type assertions is reasoning from the file names and is labelled INFERENCE for that reason.
