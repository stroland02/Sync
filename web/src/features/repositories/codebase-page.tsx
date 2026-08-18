/**
 * Codebase: the selected repository, and the root of everything beneath it.
 *
 * `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:397` names this
 * level "Codebase (the selected repository)" and the amended hierarchy (`:433`) keeps it —
 * this screen did not exist until the 2026-08-05 reconciliation found the console had no way
 * to select one, and everything below it (`/vendors/:id`, `/detectors`, the old `/codebase`)
 * was answering fleet-wide for exactly that reason. This is the fix: pick a repository here,
 * and drill down from it into the vendor rows below.
 *
 * Three view models, three questions, and none of them confirms another.
 *
 * `overview_summary` scoped to this repository answers "what is currently wrong here" — the
 * question the design document says a user actually arrives with. `index_coverage` answers
 * "how much of this codebase has Sync read" from `call_site` alone. `observed_telemetry`
 * answers "what traffic did Sync see" from three tables that carry no bearing on what the
 * static index found — a call site can exist with no traffic observed, and traffic can arrive
 * that correlates to no known call site. Three cards rather than one keeps those boundaries
 * visible instead of implying any of them confirms the others, and there is deliberately no
 * figure combining them: a scalar over "what is broken", "what we read" and "what we watched"
 * would collapse three different kinds of not-knowing onto one axis.
 *
 * Every figure on this screen and on every screen below it is scoped to `repoId`. The three
 * routes it reads take the repository — `/api/overview`, `/api/repositories/{repo}/coverage`
 * and `/api/repositories/{repo}/observed` — and each answer names the scope it was computed
 * in, so picking a different repository changes every number here rather than some of them.
 *
 * ## Ported onto the chassis and the vendored substrate by M7-W173
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-codebase.md` is the mapping table this port was
 * gated on, and it is what to read before porting a level, not this docstring.
 *
 * **The chassis arrives here in the same work item as the substrate, because this level never had
 * it.** Fleet took the chassis in M7-W163 and the substrate in M7-W172; Codebase had neither, and
 * rendered a bare 22px heading over three stacked full-width panels while the route's own question
 * sat unread in `lib/routes.ts`. So `PageHeader` now carries that question at the display step,
 * a `ControlBar` states the scope and holds one action, and the two panels the question is
 * actually about sit beside one another.
 *
 * **Neither of this level's outbound links moved into the control bar.** Fleet lifted its
 * detector-attribution link out of a card description and into the action slot; here the detectors
 * link and the Signals link each complete a sentence that argues for them, and a qualification with
 * its link taken out is a qualification shortened. The action slot takes the Signals screen as a
 * plain navigation instead — the one thing an operator does next that is not a row on this page.
 *
 * **No fact rail, and that is ruling 9 of the brief rather than an omission.** `IndexCoverageCard`
 * is mounted by the Signals level too, so hoisting its call-site figure into a Codebase-only rail
 * would either delete that figure from Signals or render it twice here.
 *
 * ## No runs panel and no repair record, until `B149` closes
 *
 * `RunsCard` and `CorpusSummaryCard` both name this screen as their destination and both are
 * unmounted anywhere in the console. Neither is mounted here, and the reason is the payload rather
 * than the layout: `RunRow` carries no `repo_id`, and `/api/corpus` accepts no repository
 * parameter, so either one placed under this heading would render every repository's rows beneath
 * one repository's name. That is the attribution `M14-W265` removed from the repository cards.
 * `codebase-page.test.tsx` holds the absence so a later tidy cannot restore it quietly.
 */

import { Link, useParams } from "react-router"

import { InfoHint } from "@/components/info-hint"
import { Button } from "@/components/ui/button"
import { ChangeUnitsTable } from "@/features/fleet/change-units-table"
import { CodebaseFactsCard } from "@/features/repositories/codebase-facts-card"
import { GettingStartedCard } from "@/features/repositories/getting-started-card"
import { OverviewGraphPanel } from "@/features/index-graph/overview-graph-panel"
import { IndexCoverageCard } from "@/features/repositories/index-coverage-card"
import { OpenFindingsCard } from "@/features/repositories/open-findings-card"
import { ObservedTelemetryCard } from "@/features/telemetry/observed-telemetry-card"
import { ControlBar } from "@/layouts/control-bar"
import { UnknownRoute } from "@/layouts/unknown-route"


/**
 * The one sentence that makes `/repositories/:repoId/vendors` reachable.
 *
 * That route is declared, built and tested, and nothing in the application linked to it: the
 * sidebar renders a route with an unbound parameter as plain text, so the vendors list could be
 * opened only from an address that already named a repository — which is this screen. The link
 * belongs in prose rather than in the control bar's action slot, for the reason this file's
 * docstring already gives about the Signals link: a qualification with its link taken out is a
 * qualification shortened, and the sentence here is what says the list is of vendors and not of
 * the calls made to them.
 */
function VendorsListLink({ repoId }: { repoId: string }) {
  // A button rather than a sentence carrying a link (owner direction 2026-08-18); the
  // explanation rides the ⓘ, and the qualification it carried — no route computes the
  // operations a repository calls — moves with it rather than being dropped.
  return (
    <div className="flex items-center gap-row">
      <Button asChild variant="outline" size="sm">
        <Link to={`/repositories/${encodeURIComponent(repoId)}/vendors`}>
          Vendors attached to this repository
        </Link>
      </Button>
      <InfoHint label="About the vendors list">
        Which API vendors this repository is bound to, and how much is open against each. A
        vendor appears there once INDEX finds a call site binding this repository to it. It is a
        list of vendors, never of the individual operations called — no route computes the
        operations a repository calls, so nothing here can be read as an inventory of them.
      </InfoHint>
    </div>
  )
}

export interface CodebasePageProps {
  readonly question?: string
}

export function CodebasePage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />

  return (
    <section className="flex flex-col gap-8">
      {/* Getting started leads, by the owner's direction: the workspace identity and the full
          loop's probed prerequisites are the first thing on the Overview. */}
      <GettingStartedCard repoId={repoId} />
      {/* The dependency graph — the screen's centrepiece, because it is the thing no
          competitor can draw: this codebase's actual API surface. It lived on the fleet screen,
          which the sole-codebase install now skips past, so it moves to the one Overview
          rather than becoming unreachable. */}
      <OverviewGraphPanel repoId={repoId} />
      {/* The technical census — what this codebase is made of, measured with the index pass,
          by the owner's direction that the Overview carries real engineering information. */}
      <CodebaseFactsCard repoId={repoId} />
      <PageHeaderRegion repoId={repoId} />
      {/* The two halves of the route's own question, beside one another */}
      <div className="grid gap-8 xl:grid-cols-2">
        <OpenFindingsCard repoId={repoId} />
        <IndexCoverageCard repoId={repoId} />
      </div>
      <VendorsListLink repoId={repoId} />
      <ChangeUnitsTable repoId={repoId} />
      <ObservedTelemetryCard repoId={repoId} />
    </section>
  )
}

function PageHeaderRegion({ repoId }: { repoId: string }) {
  return (
    <div className="flex flex-col gap-section">
      <ControlBar
        action={
          <Button asChild variant="outline" size="sm">
            <Link to={`/repositories/${encodeURIComponent(repoId)}/observed`}>
              Signals for this repository
            </Link>
          </Button>
        }
      >
        <div className="flex min-w-0 flex-col gap-field">
          <span className="furniture text-meta text-ink-muted">Scope</span>
          <span className="text-body">
            This repository alone. The codebase overview shows all repositories watched by Sync.
          </span>
        </div>
      </ControlBar>
    </div>
  )
}
