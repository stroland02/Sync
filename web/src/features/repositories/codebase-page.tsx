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

import type { ReactNode } from "react"
import { Link, useParams } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useRepositoryObserved } from "@/api/queries"
import type { ObservedTelemetryResponse } from "@/api/types"
import { MetricPanel } from "@/components/metric-panel"
import { RungBadge } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { ErrorWindowsTable } from "@/features/telemetry/error-windows-table"
import { ObservedCallsTable } from "@/features/telemetry/observed-calls-table"
import { ObservedShapesTable } from "@/features/telemetry/observed-shapes-table"
import { IndexCoverageCard } from "@/features/repositories/index-coverage-card"
import { OpenFindingsCard } from "@/features/repositories/open-findings-card"
import { ChangeUnitsTable } from "@/features/fleet/change-units-table"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { ControlBar } from "@/layouts/control-bar"
import { FooterBar } from "@/layouts/footer-bar"
import { PageHeader } from "@/layouts/page-header"
import { UnknownRoute } from "@/layouts/unknown-route"
import { useOffsetParam } from "@/lib/use-offset-param"

const DEFAULT_QUESTION =
  "Is this repository actually covered, and what does Sync not see in it?"

/** A section inside the telemetry panel. Furniture register, `h3` under the panel's own `h2`. */
function TelemetrySection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-section">
      <h3 className="furniture text-meta text-ink-muted">{title}</h3>
      {children}
    </div>
  )
}

/**
 * The page-level rung for the telemetry half, in prose rather than through `ProvenanceStrip`
 * — this payload carries no feed-fetch timestamp or context-savings figure to fill that
 * component's envelope with, the same reasoning `binding-surface-page.tsx` documents.
 *
 * It stays a paragraph beneath the table rather than moving into `FooterBar`'s `left` slot, because
 * the branch that matters most is the one with no rows and therefore no footer at all.
 */
function TelemetryRungNote({ data }: { data: ObservedTelemetryResponse }) {
  if (data.calls.total === 0) {
    return (
      <p className="max-w-prose text-body text-muted-foreground">
        No call has ever been observed for this repository — silence, not a measured zero:
        nothing here says whether a traffic source was ever watching.
      </p>
    )
  }
  const rungs = new Set(data.calls.items.map((call) => call.binding_rung))
  if (rungs.size === 1) {
    const [only] = rungs
    return (
      <p className="max-w-prose text-body text-muted-foreground">
        Every observed call below rests on the <RungBadge rung={only} /> rung.
      </p>
    )
  }
  return (
    <p className="max-w-prose text-body text-muted-foreground">
      Mixed: the observed calls below carry more than one rung — some correlate to a known
      operation and some do not. The rung column on each row says which is which.
    </p>
  )
}

function ObservedTelemetryCard({ repoId }: { repoId: string }) {
  const [callsOffset, setCallsOffset] = useOffsetParam("calls_offset")
  const [shapesOffset, setShapesOffset] = useOffsetParam("shapes_offset")
  const [errorWindowsOffset, setErrorWindowsOffset] = useOffsetParam("error_windows_offset")
  const query = useRepositoryObserved(repoId, {
    callsLimit: DEFAULT_LIMIT,
    callsOffset,
    shapesLimit: DEFAULT_LIMIT,
    shapesOffset,
    errorWindowsLimit: DEFAULT_LIMIT,
    errorWindowsOffset,
  })

  return (
    <div className="flex min-w-0 flex-col gap-section">
      {query.isPending && <LoadingState what={`observed telemetry for ${repoId}`} />}
      {query.isError && (
        <ErrorState error={query.error} what={`observed telemetry for ${repoId}`} onRetry={() => void query.refetch()} />
      )}

      {query.isSuccess && (
        <MetricPanel
          label="Observed telemetry"
          caption={
            <p className="max-w-prose">
              What traffic showed up for this repository, what shape it had, and how often it
              failed. A row here is evidence a call site was exercised — it is not proof the
              binding correlating it to an operation is correct. The specification's own Signals
              level (design doc line 435) holds this traffic as the signal-source role's one panel,
              beside the vendor role and the human-surface role —{" "}
              <Link
                to={`/repositories/${encodeURIComponent(repoId)}/observed`}
                className="underline underline-offset-2"
              >
                see it grouped with the other two roles, on the Signals screen
              </Link>{" "}
              — rather than reading this card alone as the whole level.
            </p>
          }
        >
          <TelemetrySection title="Calls">
            {query.data.calls.total === 0 ? (
              <EmptyState
                headline="No call has been observed for this repository."
                detail="The API answered with an empty list. Either nothing has watched this repository's traffic, or nothing arrived while it was watching — this view cannot tell the two apart."
              />
            ) : (
              <>
                <ObservedCallsTable calls={query.data.calls.items} />
                <FooterBar
                  offset={callsOffset}
                  limit={DEFAULT_LIMIT}
                  shown={query.data.calls.items.length}
                  total={query.data.calls.total}
                  nextOffset={query.data.calls.next_offset}
                  busy={query.isFetching}
                  onOffsetChange={setCallsOffset}
                />
              </>
            )}
            <TelemetryRungNote data={query.data} />
          </TelemetrySection>

          <TelemetrySection title="Shapes">
            <p className="max-w-prose text-body text-muted-foreground">
              What the operations this repository calls have looked like on the wire, scoped
              to the vendor/operation pairs this repository's own calls above name — a shape
              is a vendor-wide fact, not a per-repository one, so nothing here belongs to this
              repository alone.
            </p>
            {query.data.shapes.total === 0 ? (
              <EmptyState
                headline="No shape recorded for this repository's operations."
                detail="Either no traffic for these operations has been shaped yet, or this repository's calls did not correlate to any operation."
              />
            ) : (
              <>
                <ObservedShapesTable shapes={query.data.shapes.items} />
                <FooterBar
                  offset={shapesOffset}
                  limit={DEFAULT_LIMIT}
                  shown={query.data.shapes.items.length}
                  total={query.data.shapes.total}
                  nextOffset={query.data.shapes.next_offset}
                  busy={query.isFetching}
                  onOffsetChange={setShapesOffset}
                />
              </>
            )}
          </TelemetrySection>

          <TelemetrySection title="Error windows">
            <p className="max-w-prose text-body text-muted-foreground">
              Failure counts have no denominator in this table — a count is not a rate, and
              this view does not compute one.
            </p>
            {query.data.error_windows.total === 0 ? (
              <EmptyState
                headline="No error window recorded for this repository."
                detail="Either nothing has tracked errors for this repository, or nothing tracked ever recorded a window — this view cannot tell the two apart."
              />
            ) : (
              <>
                <ErrorWindowsTable windows={query.data.error_windows.items} />
                <FooterBar
                  offset={errorWindowsOffset}
                  limit={DEFAULT_LIMIT}
                  shown={query.data.error_windows.items.length}
                  total={query.data.error_windows.total}
                  nextOffset={query.data.error_windows.next_offset}
                  busy={query.isFetching}
                  onOffsetChange={setErrorWindowsOffset}
                />
              </>
            )}
          </TelemetrySection>
        </MetricPanel>
      )}
    </div>
  )
}

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
  return (
    <p className="max-w-prose text-body text-muted-foreground">
      Which API vendors this repository is bound to, and how much is open against each, is its own
      list —{" "}
      <Link
        to={`/repositories/${encodeURIComponent(repoId)}/vendors`}
        className="underline underline-offset-2"
      >
        the vendors attached to this repository
      </Link>
      . A vendor appears there once INDEX finds a call site binding this repository to it. It is a
      list of vendors and never of the individual operations called: no route computes the
      operations a repository calls, so nothing on this screen or below it can be read as an
      inventory of them.
    </p>
  )
}

export interface CodebasePageProps {
  readonly question?: string
}

export function CodebasePage({ question = DEFAULT_QUESTION }: CodebasePageProps) {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />

  return (
    <section className="flex flex-col gap-8">
      <PageHeaderRegion repoId={repoId} question={question} />
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

function PageHeaderRegion({ repoId, question }: { repoId: string; question: string }) {
  return (
    <div className="flex flex-col gap-section">
      <PageHeader
        trail={
          <Breadcrumbs
            trail={[{ label: "Repositories", to: "/" }, { label: repoId }]}
          />
        }
        title={<span className="font-mono">{repoId}</span>}
        question={question}
      />
      <ControlBar
        action={
          <Link
            to={`/repositories/${encodeURIComponent(repoId)}/observed`}
            className="text-body underline underline-offset-2"
          >
            Signals for this repository
          </Link>
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
