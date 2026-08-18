/**
 * The Overview: which repository to open, and the four fleet counts while you decide.
 *
 * **One question per screen.** This level asks which repository, and everything that answered a
 * different question has moved to where that question is asked. The fleet-wide change-unit table
 * and the vendor distribution went to the Codebase screen, where they are scoped to one repository
 * and therefore actionable; a fleet-wide table on a screen whose job is choosing between
 * repositories made the choosing harder rather than easier.
 *
 * **The name.** This destination was titled "Repositories", labelled "Codebases" in the route
 * registry, and sits at the `Fleet` level — three names for one screen. It is "Overview" now in
 * everything a reader sees. The *level* keeps the specification's word, because
 * `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md` is what
 * `tests/test_console_hierarchy.py` checks `GRAPH_LEVELS` against, and a display rename is not a
 * hierarchy change.
 *
 * **No page-level action.** `PageHeader`'s `actions` slot carried "Review proposed patch", pointing
 * at whichever run happened to be the newest with an opened pull request. With nine change units
 * open that reads as *the* patch, which is a claim about priority the data does not make. The
 * action belongs on the change-unit row it acts on, beside that row's own standing and checkpoint
 * age, where it also reads as the log of what happened to that change.
 *
 * **The codebase list is not here.** Ruled twice by the owner: this screen shows findings for the
 * one workspace already chosen, and a directory of every codebase answers a different question —
 * which workspace am I in — that the scope switcher already answers. The listing moved whole to
 * Settings' Codebases group rather than being deleted, because it fixed a real defect worth
 * keeping: the panel it replaced printed one fleet-wide `total_findings` under every card, a false
 * claim about every repository but the one that figure happened to match.
 *
 * **What stays, and why it is not clutter.** The four counts, the standing limits, the
 * composite-health refusal and the three footnotes are the qualifications that make every figure on
 * this screen readable. `CLAUDE.md` protects four distinctions and the console architecture plan's
 * *Establish 2* reproduces twenty-four sentences that may be restyled and re-placed but never
 * shortened. The absence footnote pointed at "the repository list below"; the list moved, so the
 * pointer moved with it and now names the codebase list in Settings. Re-placing a referent is
 * permitted where shortening the sentence is not — and leaving it pointing at a list this screen no
 * longer holds would be a true sentence with a dead pointer, which is the quiet half of the defect.
 */

import { useLocation } from "react-router"

import { useOverview, useRepositories, useRepositoryCoverage } from "@/api/queries"
import { FactTile } from "@/components/fact-tile"
import { CodebaseFactsBand, resolveCodebaseScope } from "@/features/fleet/codebase-facts"
import { TotalsBar } from "@/features/fleet/totals-bar"
import { VendorCardsGrid } from "@/features/fleet/vendor-cards-grid"
import { OverviewGraphPanel } from "@/features/index-graph/overview-graph-panel"
import { FleetFacts } from "@/features/fleet/fleet-facts"
import { RungUpgradeCard } from "@/features/fleet/rung-upgrade-card"
import { ScreenLimitsCard } from "@/features/fleet/screen-limits"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { scopeFromLocation } from "@/layouts/scope-switchers"

// The screen's stated question, which changed when the codebase listing left it. It described
// "all code repositories monitored by Sync" while this screen answered that; it now answers what
// is true about the one workspace already chosen, and says so.
const DEFAULT_QUESTION =
  "What the index, the vendors and the detectors currently say about this workspace."

export interface FleetPageProps {
  readonly question?: string
}

/**
 * The graph draws one codebase, so it draws nothing until the address names one.
 *
 * The band beside it resolves the same six scopes and says which it landed on. Picking a
 * repository here because exactly one exists would be fine; picking one because several do would
 * be the console deciding what the operator is looking at, which is the claim the band refuses in
 * words and this panel refuses by not drawing.
 */
/**
 * The band below the fold: the totals line, then one card per vendor.
 *
 * Adopted from Lane F and scoped the way the graph is -- both describe one codebase, so neither
 * draws until the address names one. `total_findings_bound_reached` is passed through rather than
 * dropped, because past the route's bound the count is a floor, and printing a floor plain would
 * overstate what was counted.
 */
function OverviewTotalsRegion() {
  const { pathname, search } = useLocation()
  const repositories = useRepositories()
  const scope = resolveCodebaseScope(
    scopeFromLocation(pathname, search).repoId,
    repositories.data?.repo_ids
  )
  const repoId = scope.kind === "selected" || scope.kind === "only" ? scope.repoId : null

  const coverage = useRepositoryCoverage(repoId ?? "")
  const overview = useOverview(repoId ?? undefined)

  if (repoId === null) return null

  return (
    <div className="flex flex-col gap-section">
      <TotalsBar
        totalCallSites={coverage.data?.total_call_sites ?? null}
        totalFindings={overview.data?.total_findings ?? null}
        findingsAreFloor={overview.data?.total_findings_bound_reached ?? false}
      />
      <VendorCardsGrid repoId={repoId} />
    </div>
  )
}

function OverviewGraphRegion() {
  const { pathname, search } = useLocation()
  const repositories = useRepositories()
  const scope = resolveCodebaseScope(
    scopeFromLocation(pathname, search).repoId,
    repositories.data?.repo_ids
  )

  if (scope.kind === "selected" || scope.kind === "only") {
    return <OverviewGraphPanel repoId={scope.repoId} />
  }
  return (
    <p className="text-meta text-muted-foreground">
      No codebase is selected, so there is no dependency graph to draw. The graph is one
      codebase's call sites out to its vendors; drawn across several it would show a shape no
      repository has.
    </p>
  )
}

export function FleetPage({ question = DEFAULT_QUESTION }: FleetPageProps) {
  return (
    <section className="flex flex-col gap-section">
      {/* "Overview", once. This destination was titled "Repositories", labelled "Codebases" in the
          route registry and sits at the "Fleet" level — three names for one screen, which is its own
          kind of clutter. The *level* keeps the specification's word; only what a reader sees
          changes, so `tests/test_console_hierarchy.py` is untouched.

          No page-level action. "Review proposed patch" pointed at whichever run happened to be the
          newest with an opened pull request, which reads as *the* patch when there are nine change
          units. It belongs on the change-unit row it acts on, beside that row's own standing. */}
      {/* Answer 7 removes the page header; the question it carried is kept as one dense line,
          because a screen that does not say what it is answering is the black box this console
          exists to replace. Recorded conflict: the mock draws a header here and answer 20 rules
          for the answer. */}
      <div className="flex flex-col gap-field">
        <Breadcrumbs trail={[{ label: "Overview" }]} />
        <p className="text-meta text-muted-foreground">{question}</p>
      </div>

      {/* The top band: what is true about the codebase this screen is about. The owner's ruling of
          2026-08-18 is that the Overview *is* the selected codebase and selection is chrome — so
          the facts about that one codebase lead, and the directory of codebases below is what a
          reader chose from rather than what the screen is about. The route, the hierarchy and
          `GRAPH_LEVELS` are untouched: that amendment is the specification's and has not landed,
          and `.claude/rules/console-hierarchy.md` makes the ordering the whole rule. */}
      <div className="grid gap-section xl:grid-cols-2">
        <CodebaseFactsBand />
        <OverviewGraphRegion />
      </div>

      {/* Decision 2's below-the-fold half: the totals, then the vendors they are made of. */}
      <OverviewTotalsRegion />

      {/* 4-card metric strip */}
      <FleetFacts />

      {/* Value before configuration, and the order on this screen is the argument. The repository
          list and its counts come first: real findings, read from source, before anything was
          attached. Only then does this panel say what that evidence rests on and what the next rung
          would take. Putting it above the list would make the first thing a reader meets a setup
          instruction, which is the onboarding every telemetry product has and the one Sync does not
          need — its screen is not empty before traces arrive. */}
      <RungUpgradeCard />

      {/* Two columns, and the second one is load-bearing rather than decorative. The health-refusal
          sentence ends "the panel beside them names what none of these figures can tell you at
          all"; W362 left both panels stacked inside one wrapper, so that clause described a layout
          that did not exist. The band is what makes it true again. */}
      <div className="grid gap-section xl:grid-cols-2">
        <div className="min-w-0">
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
        </div>
        <div className="min-w-0">
          <ScreenLimitsCard />
        </div>
      </div>

      {/* Footnotes holding honesty requirements */}
      <div className="flex flex-col gap-row text-meta text-muted-foreground max-w-5xl leading-relaxed pt-section border-t border-border">
        <p>
          A checkpoint age is staleness, not liveness — it says how old the evidence is not whether the run is still going. A change unit collapses findings sharing a vendor change against one repository set; the call-site grain is intact underneath and reachable from every row.
        </p>
        <p>
          A repository the index never indexed has no row — absence is not zero: a repository configured but never indexed has no row in the codebase list in Settings, and the same absence as a repository nobody ever configured.
        </p>
        <p>
          A finding retried three times writes three attempts here and counts once toward the corpus grain.
        </p>
      </div>
    </section>
  )
}
