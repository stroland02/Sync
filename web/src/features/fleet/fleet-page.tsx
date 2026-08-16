/**
 * The fleet: what Sync is doing right now, across every run it has ever started, and what
 * an operator has to act on today.
 *
 * Five routes make this screen, each read through the view model built for its own grain
 * rather than the frozen `GraphSurface`: `GET /api/overview` for open findings by vendor,
 * `GET /api/runs` for the checkpointer, `GET /api/corpus` for the repair record,
 * `GET /api/repositories` for the index's repo_id roll-up, and `GET /api/detectors` for
 * open-finding attribution. The latter four read `sync.dashboard.fleet` and
 * `sync.dashboard.graph_views`, and none of them carries an indexing timestamp or a binding
 * rung envelope — inheriting one would invent a field the transport never sends.
 *
 * `/api/overview` is the one exception, and it earns a full paragraph rather than a
 * parenthetical because getting this wrong is exactly how the milestone's Critical review
 * finding hid: this route used to compose its envelope by re-reading the frozen
 * `GraphSurface.whats_at_risk` page, and an earlier version of this comment still described
 * that path after it was gone. `sync.dashboard.graph_views.overview_summary` has read
 * `GraphStore` directly since the fleet screen's scale fix — no `whats_at_risk` scan anywhere
 * in this route — and its envelope carries two fields the frozen surface's never did:
 * `total_findings_bound_reached` and `context_savings_bound_reached`, both naming a bounded
 * scan rather than a page-shaped one. A render site that treats `/api/overview`'s payload as
 * "the same envelope every other route gets, just also carrying vendors" is the render site
 * that shows a bounded figure as if it were exact — `VendorDistributionCard`,
 * `ProvenanceStrip` and now `FleetFacts` are where that is actually held, this paragraph is
 * only where a reader learns to expect it.
 *
 * There is no composite health figure here on purpose. A scalar that averaged three gates
 * would collapse "we could not check" onto the same axis as "we checked and it passed",
 * which is the failure this console exists to replace.
 *
 * ## The composition, recomposed onto the chassis by M7-W163
 *
 * **The panel order below is unchanged, because it is the operator's ranking and it was argued
 * for.** What changed is what the screen does with its width. Before this item the route was a
 * single column of six full-width cards under a 24px `h1`: measured at 1440x900 and 1280x800, a
 * type range of 2.67:1 against a 3.4 bar, and one placement of a panel beside a panel on the
 * whole screen. `reports/2026-08-06-why-the-console-came-out-flat.md` names why that happened
 * and it was not a mistake anyone made — the rules asked for it.
 *
 * Four changes, in the order the eye meets them:
 *
 * - **`PageHeader` carries the route's own `question`**, which has sat in `lib/routes.ts` unread
 *   by any feature screen since it was written. This is the first feature route to render the
 *   48px display step the chassis declared, and rendering it is the whole of what takes the type
 *   range past its bar.
 * - **A `ControlBar` holds the screen's scope and its one primary action.** The left slot states
 *   what the counts are counted over rather than offering a selector, and that is deliberate:
 *   Fleet is the fleet-wide level by construction — the per-repository answer is one level down,
 *   at a repository's own Codebase screen — so a scope control here would claim a choice this
 *   level does not offer. The action is the detector attribution link, which was a "Full detail"
 *   buried mid-paragraph in a card description and is now in the position the grammar of a
 *   control plane keeps for it.
 * - **A fact rail** — `FleetFacts` — places the four counts beside one another with the label
 *   register above the value. The paragraph that used to open the screen still opens the body of
 *   it, and it now qualifies figures that are on screen beside it rather than describing figures
 *   the reader has not reached.
 * - **The standing limits sit beside what they qualify.** That was already this docstring's
 *   stated intent — "placed immediately beside what it qualifies rather than at the bottom of the
 *   screen" — and it was not true: the panel was stacked underneath. It is a column of prose, so
 *   it takes a third of the width beside the two panels it limits, which is also what keeps the
 *   runs table on two thirds rather than a half.
 *
 * The repair record stays full width, since a chart plus three tallied breakdowns is an evidence
 * surface, not a summary; the repository roll-up and the detector attribution still close the
 * screen paired, because both are lower-cardinality context an operator checks rather than acts
 * on.
 *
 * ## Ported onto the vendored substrate by M7-W172, and the panel order still did not move
 *
 * Fleet is the first level on the vendored Supabase components, so what it does here is the
 * pattern the remaining eight copy. `docs/superpowers/briefs/2026-08-07-substrate-fleet.md` is the
 * gate that came first: every field this screen and its six children render, mapped to a slot
 * before a line of it changed, with nine rulings for the fields that had no obvious one. Read that
 * before porting a level, not this.
 *
 * Three things changed and none of them is the composition. Every panel is now `MetricPanel` over
 * the vendored `Card`, so the plane, the radius and the rule under a panel's header are the
 * substrate's rather than a second set of values. Every table takes the Studio anatomy through
 * `components/data-table.tsx` — the furniture register on a column heading, `DESIGN.md`'s own row
 * heights on the cells. And two panels now lead with a figure above their evidence: the vendor
 * count, which is that panel's own grain, and the corpus panel's distinct-findings count. No
 * other panel does, because the fact rail already carries every other count on this screen and
 * M7-W163's ruling against rendering one twice is what makes the rail worth having.
 *
 * **No row on this screen has an overflow menu.** Every row has exactly one action — the link it
 * already is — and the API is read-only, so a second would have to be invented. A menu whose only
 * entry duplicates the row is furniture claiming a choice nobody has.
 */

import { Link } from "react-router"

import { CorpusSummaryCard } from "@/features/fleet/corpus-summary"
import { DetectorsSummaryCard } from "@/features/fleet/detectors-summary"
import { FleetFacts } from "@/features/fleet/fleet-facts"
import { RepositoriesCard } from "@/features/fleet/repositories-table"
import { RunsCard } from "@/features/fleet/runs-table"
import { ScreenLimitsCard } from "@/features/fleet/screen-limits"
import { VendorDistributionCard } from "@/features/fleet/vendor-distribution"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { ControlBar } from "@/layouts/control-bar"
import { PageHeader } from "@/layouts/page-header"
import { ROUTES } from "@/lib/routes"

/**
 * The route's own question, read from the registry rather than written a second time here.
 *
 * **Resolved inside a component rather than at module scope, and that is not a style choice.**
 * `lib/routes.ts` imports this page to build its `element`, so a page that imports `ROUTES` closes
 * a cycle: at module-initialisation time `ROUTES` is still `undefined` and a top-level
 * `ROUTES.find(...)` throws `Cannot read properties of undefined`. `npm run build` does not catch
 * it — the cycle is legal ESM and typechecks — and it surfaced here as three vitest suites failing
 * to import. Dereferencing at render is safe because both modules have finished initialising by
 * then. B120 records the structural fix, which belongs to whoever owns `App.tsx`: pass the
 * question down from the route it came from, so no page reaches back into the registry at all.
 */
function routeQuestion(path: string): string {
  const entry = ROUTES.find((route) => route.path === path)
  if (entry === undefined) throw new Error(`no route declares ${path}`)
  return entry.question
}

export function FleetPage() {
  return (
    <section className="flex flex-col gap-8">
      <PageHeaderRegion />
      {/* The rail and the paragraph that qualifies it, beside one another rather than stacked.
          Measured at 1440x900: stacking them put the first table 640px down the page with no row
          of any table above the fold, against seven before this item. Prose in a column beside the
          figures it qualifies costs width the screen has and height it does not. */}
      <div className="grid gap-8 xl:grid-cols-3">
        <div className="min-w-0 xl:col-span-2">
          <FleetFacts />
        </div>
        <p className="max-w-prose text-body text-muted-foreground">
          There is no composite health figure here on purpose. A scalar that averaged three
          gates would collapse "we could not check" onto the same axis as "we checked and it
          passed", which is the failure this console exists to replace. Every figure on this
          screen instead names its own scope, and the panel beside them names what none of these
          figures can tell you at all.
        </p>
      </div>
      {/* Two thirds and a third rather than halves. The limits panel is prose and reads well
          narrow; the runs table is four columns including a finding id, and halving the width
          is what pushes those onto a third line. */}
      <div className="grid gap-8 xl:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-8 xl:col-span-2">
          <VendorDistributionCard />
          <RunsCard />
        </div>
        <ScreenLimitsCard />
      </div>
      <CorpusSummaryCard />
      <div className="grid gap-8 lg:grid-cols-2">
        <RepositoriesCard />
        <DetectorsSummaryCard />
      </div>
    </section>
  )
}

function PageHeaderRegion() {
  const question = routeQuestion("/")

  return (
    <div className="flex flex-col gap-section">
      <PageHeader
        title="Fleet"
        question={question}
        trail={<Breadcrumbs trail={[{ label: "Fleet" }]} />}
      />
      <ControlBar
        action={
          <Link
            to="/detectors"
            className="text-body underline underline-offset-2"
          >
            Detector attribution
          </Link>
        }
      >
        {/* One line. The longer form of this — that a single codebase's own figures live on that
            repository's Codebase screen and are a different number rather than a different
            rendering — is already in `VendorDistributionCard`'s description, and saying it twice
            is a fact that will disagree with itself. */}
        <div className="flex min-w-0 flex-col gap-field">
          <span className="furniture text-meta text-ink-muted">Scope</span>
          <span className="text-body">Every repository the index has seen.</span>
        </div>
      </ControlBar>
    </div>
  )
}
