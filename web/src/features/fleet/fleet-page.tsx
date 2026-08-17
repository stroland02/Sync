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
 *   range past its bar. Its `actions` slot carries the screen's one primary action: reviewing the
 *   newest proposed patch. `proposed-patch.ts` reads the same `/api/runs` page `CodebasesPanel`
 *   already fetches for the newest run whose outcome is `opened`, and the button is absent rather
 *   than present when none has — a CTA that always points somewhere, aimed at an invented finding
 *   id when reality has nothing to offer, is the fixture-as-fact defect this task closes.
 * - **A `ControlBar` holds the screen's scope, with its action slot empty.** The left slot states
 *   what the counts are counted over rather than offering a selector, and that is deliberate:
 *   Fleet is the fleet-wide level by construction — the per-repository answer is one level down,
 *   at a repository's own Codebase screen — so a scope control here would claim a choice this
 *   level does not offer. The three repository filters sit beside that scope sentence as
 *   `chipSurface`-styled chips; the bar's action slot stays empty because the screen's one
 *   primary action already sits in the header, and a second slot for it would be the same action
 *   offered twice.
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
 *
 * ## The change-unit table is the data centrepiece, as of M14-W277
 *
 * The mock's Fleet screen (`docs/console-mock/screens/01-fleet.png`) is one dense CHANGE UNIT
 * table; the built screen carried repository cards and paragraphs instead, and no component here
 * consumed `GET /api/change-units` even after Lane E shipped it — `change-units-table.tsx`
 * synthesised its rows from `useOverview` and `useRuns`, deriving the same grain
 * `sync.dashboard.fleet.change_units` already computes. That is the exact defect
 * `.claude/rules/console-dev-loop.md` names: a rule the payload can answer, answered twice. The
 * table now reads the real endpoint and sits directly under the fact rail, above the repository
 * cards, so the density this screen was missing comes from more data rather than less prose —
 * every sentence below is unchanged.
 */

import { useState } from "react"
import { Link } from "react-router"

import { useRuns } from "@/api/queries"
import { Button } from "@/components/ui/button"
import { FactTile } from "@/components/fact-tile"
import { ChangeUnitsTable } from "@/features/fleet/change-units-table"
import { CodebasesPanel, type CodebaseFilter } from "@/features/fleet/codebases-panel"
import { FleetFacts } from "@/features/fleet/fleet-facts"
import { proposedPatchTarget } from "@/features/fleet/proposed-patch"
import { ScreenLimitsCard } from "@/features/fleet/screen-limits"
import { VendorDistributionCard } from "@/features/fleet/vendor-distribution"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { ControlBar } from "@/layouts/control-bar"
import { PageHeader } from "@/layouts/page-header"
import { chipSurface } from "@/lib/selectable-surface"

const DEFAULT_QUESTION =
  "All code repositories monitored by Sync, their attached API vendors, and active migrations."

const FILTERS: [CodebaseFilter, string][] = [
  ["ALL", "All repositories"],
  ["NEEDS_REVIEW", "With active remediations"],
  ["CLEAN", "Clean repositories"],
]

export interface FleetPageProps {
  readonly question?: string
}

export function FleetPage({ question = DEFAULT_QUESTION }: FleetPageProps) {
  const [filter, setFilter] = useState<CodebaseFilter>("ALL")
  const runsQuery = useRuns({ limit: 20, offset: 0 })
  const target = proposedPatchTarget(runsQuery.data?.items ?? [])

  return (
    <section className="flex flex-col gap-section">
      <PageHeader
        title="Repositories"
        question={question}
        trail={<Breadcrumbs trail={[{ label: "Repositories" }]} />}
        actions={
          target !== null && (
            <Button asChild>
              <Link to={target}>Review proposed patch</Link>
            </Button>
          )
        }
      />

      {/* Filter Tabs & Scope Description */}
      <ControlBar>
        <div className="flex flex-wrap items-center gap-row">
          {FILTERS.map(([value, label]) => (
            <Button
              key={value}
              type="button"
              size="sm"
              variant="outline"
              aria-pressed={filter === value}
              className={chipSurface(filter === value)}
              onClick={() => setFilter(value)}
            >
              {label}
            </Button>
          ))}
        </div>
        <span className="text-meta text-muted-foreground">
          Repositories monitored across the organization
        </span>
      </ControlBar>

      {/* 4-card metric strip */}
      <FleetFacts />

      {/* The data centrepiece: every open change unit, fleet-wide */}
      <ChangeUnitsTable />

      {/* Primary Monitored Codebases Panel */}
      <CodebasesPanel filter={filter} />

      {/* Contextual cards in a clean 2-column grid */}
      <div className="grid gap-section xl:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-section xl:col-span-2">
          <VendorDistributionCard />
        </div>
        <div className="flex min-w-0 flex-col gap-section">
          <FactTile
            label="Health score policy"
            value={
              <>
                There is no composite health figure here on purpose. A scalar that averaged three
                gates would collapse "we could not check" onto the same axis as "we checked and it
                passed", which is the failure this console exists to replace. Every figure on this
                screen instead names its own scope, and the panel beside them names what none of
                these figures can tell you at all.
              </>
            }
          />
          <ScreenLimitsCard />
        </div>
      </div>

      {/* Footnotes holding honesty requirements */}
      <div className="flex flex-col gap-row text-meta text-muted-foreground max-w-5xl leading-relaxed pt-section border-t border-border">
        <p>
          A checkpoint age is staleness, not liveness — it says how old the evidence is not whether the run is still going. A change unit collapses findings sharing a vendor change against one repository set; the call-site grain is intact underneath and reachable from every row.
        </p>
        <p>
          A repository the index never indexed has no row — absence is not zero: a repository configured but never indexed has no row in the repository list below, and the same absence as a repository nobody ever configured.
        </p>
        <p>
          A finding retried three times writes three attempts here and counts once toward the corpus grain.
        </p>
      </div>
    </section>
  )
}
