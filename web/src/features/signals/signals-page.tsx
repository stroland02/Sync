/**
 * Signals: a catalogue of what is attached to one repository's graph, grouped by the role it plays.
 *
 * `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:435` places this
 * level under API Services, and `:455-459` (section *M5 — The integration layer*) defines the
 * three roles. Both the role names and their relationship sentences live in `roles.ts` rather
 * than in this file, because the header below states which roles have an integration attached
 * and which do not, and a header that restated the roster would be the same fact in two places.
 *
 * **A group per role is not a promise that every role has one.** This deployment has two: the
 * static index gives the vendor role a real answer (which API services this repository's code
 * calls), and `observed_call` / `observed_shape` / `observed_error_window` give the signal-source
 * role a real answer (what traffic showed up, and how it behaved). Nothing in this tree gives the
 * third role an answer at all — no adapter, no configuration table, no row anywhere
 * names a Slack channel, a Linear issue, a Notion page, or a GitHub pull request as a configured
 * destination. Sync *does* open pull requests, at the Solution Workflow's own Pull Request level
 * (`:442`) — but that is the product delivering its remediation output through a hardcoded
 * mechanism, not an integration this graph tracks the way it tracks an API service or a
 * signal source. There is nothing to query, which is why that group is not an empty table: an
 * empty table would claim a question was asked.
 *
 * Grouped by role because the graph attaches at three different points, not because three
 * columns read as balanced. A call site, a traffic row and a delivery would each join the graph
 * differently if the third one existed, and showing them as one undifferentiated "integrations"
 * list would erase the distinction the data actually carries.
 *
 * B94 records what is still missing and why it is blocked rather than merely undone: the level
 * is complete as an honest account of this deployment, and incomplete as the specification's
 * Signals level, until M5 attaches a delivery destination and gives the correlation join something
 * to render across all three.
 *
 * ## Ported onto the chassis and the vendored substrate by M7-W175
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-signals.md` is the mapping table this port was
 * gated on. Read that before porting a level, not this docstring.
 *
 * **The chassis arrives here in the same work item as the substrate, because this level never had
 * it.** The screen opened on a bare 22px heading while the route's own question — the only sentence
 * anywhere that names all three roles in one breath — sat unread in `lib/routes.ts`.
 * `routeQuestion` now renders it, and it does so without this file spelling a role name, which is
 * what `tests/test_console_signals_roles.py` requires.
 *
 * **The M7 plan's catalogue direction lands as a grid inside each role rather than across all
 * three.** One card per integration, grouped by role, with the unattached role's card in the same
 * grid rhythm as its peers rather than as a full-bleed block at the foot of the screen. The
 * signal-source role is the exception and it is measured rather than assumed: its three panels each
 * hold a table of seven to twelve columns, and a table that wide at a third of the width wraps every
 * row.
 *
 * **No `ControlBar`.** The one thing a bar could carry here is the scope, and the scope is already
 * stated by the breadcrumb, by the mono `h1`, and by the paragraph below. A fourth copy is a fact
 * that will disagree with itself.
 *
 * **A chip beside each role, and no dot anywhere.** `ATTACHED` / `NOT ATTACHED` is the absence
 * vocabulary `.claude/rules/console-surface.md` permits as a badge, drawn monochrome. A dot would
 * claim a lifecycle state this data does not hold: attachment is a fact about configuration and
 * says nothing about whether anything reported recently. A source that has not reported is rendered
 * as the sentence it already has.
 *
 * ## Layout extracted from the mock, 2026-08-18 (`docs/superpowers/plans/2026-08-18-mock-layout-
 * extraction.md`)
 *
 * `docs/console-mock/index.html`'s `isSignals` section (line 519) draws three role cards side by
 * side in one `grid-template-columns:repeat(3, minmax(0,1fr))` row, each a bordered card with an
 * eyebrow-plus-title header and a footer note pinned to the card's bottom edge with `margin-top:
 * auto`. That is the structure this file now uses in place of the three stacked full-width
 * sections it had before: one `RoleGroup` per grid column rather than one per vertical block.
 *
 * The mock's fixture draws exactly one integration per role card, with a fixed row-list of its
 * recent reports. Real data does not hold that shape — the vendor role can carry zero, one, or
 * several vendors — so `RoleGroup` takes the mock's *card* (border, radius, eyebrow, title slot,
 * footer note) rather than the mock's *row list*: `AttachmentChip` and the relationship sentence
 * fill the header where the mock puts an integration's own name, and the same real components
 * this level already rendered (`SubjectCatalogue`, `SignalSourcePanel`, `NotAttachedState`) fill
 * the body, unmodified. The two protected intro paragraphs stay above the grid — the mock's
 * fixture screen has no equivalent sentence, and the layout gains the room for them rather than
 * dropping them to match a drawing with no data behind it.
 *
 * ## Onto `ScreenFrame`
 *
 * Three sets page here and a status band renders one pager, so the owner ruled that the controls
 * bar names which set the band counts and the three tables give up their footers to it. The live
 * alternative was the binding surface's — keep one set's footer under its own rows — and no set
 * here is the screen's subject the way call sites are there.
 *
 * A null `telemetry_attached_at` renders "never attached" and never `0`; `signals-page.test.ts`
 * holds it.
 *
 * **The screen still names its repository nowhere** — no breadcrumb, no scope line, no identity
 * band. Deferred with this port rather than by it: identity is the chassis band's, and inventing
 * one here would be a fourth copy of a scope three other surfaces already state.
 */

import { useParams } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useRepositoryObserved } from "@/api/queries"
import type { ItemPage, ObservedTelemetryResponse } from "@/api/types"
import { ErrorState, LoadingState } from "@/components/states"
import { Absent } from "@/components/status"
import { Button } from "@/components/ui/button"
import { ObservedVolumeCard } from "@/features/dashboards/observed-volume-card"
import { SignalsKpis } from "@/features/signals/signals-kpis"
import type { ReactNode } from "react"

import { InfoHint } from "@/components/info-hint"

import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { formatTimestamp } from "@/lib/format"
import { describeRecordWindow } from "@/lib/record-window"
import { useFacetParam } from "@/lib/use-facet-param"
import { useOffsetParam } from "@/lib/use-offset-param"
import { SignalSourcePanel } from "@/features/telemetry/signal-source-panel"
import { NotAttachedState } from "@/features/signals/not-attached-state"
import {
  ATTACHED_ROLES,
  HUMAN_SURFACE_ROLE,
  SIGNAL_SOURCE_ROLE,
  UNATTACHED_ROLES,
  VENDOR_ROLE,
  type SignalRole,
} from "@/features/signals/roles"
import { SubjectCatalogue } from "@/features/signals/subject-catalogue"
import { UnknownRoute } from "@/layouts/unknown-route"


function names(roles: readonly SignalRole[]): string {
  return roles.map((entry) => entry.role).join(", ")
}

/** Labels are `signal-source-panel.tsx`'s panel headings verbatim: a heading is what binds the
    bar and the band to a table, and a synonym leaves the pager pointing at nothing nameable. */
const SET_KEYS = ["calls", "shapes", "error_windows"] as const

type SetKey = (typeof SET_KEYS)[number]

const SET_COPY: Record<SetKey, { label: string; singular: string; plural: string }> = {
  calls: { label: "Observed calls", singular: "observed call", plural: "observed calls" },
  shapes: { label: "Response shapes", singular: "response shape", plural: "response shapes" },
  error_windows: { label: "Error windows", singular: "error window", plural: "error windows" },
}

interface SignalSet {
  key: SetKey
  label: string
  singular: string
  plural: string
  offset: number
  onOffsetChange: (offset: number) => void
}

/** A shape rather than the query object, so a pending read cannot reach a success branch's
    arithmetic and every answer has to be written out. */
export type ObservedState =
  | { kind: "pending" }
  | { kind: "errored" }
  | { kind: "answered"; data: ObservedTelemetryResponse; fetching: boolean }

function pageOf(data: ObservedTelemetryResponse, key: SetKey): ItemPage<unknown> {
  if (key === "calls") return data.calls
  if (key === "shapes") return data.shapes
  return data.error_windows
}

/** A stale bookmark can name a set this screen does not hold; it opens on the first one. */
function toSetKey(raw: string | null): SetKey {
  return SET_KEYS.find((key) => key === raw) ?? "calls"
}

/**
 * What the band says about the set the bar has selected.
 *
 * The payload reports `0` for all three sets from a repository nothing ever watched, so a count
 * printed on the never-attached branch is a measured quiet over traffic nobody looked at (B157).
 */
export function signalsStatus(
  set: SignalSet,
  state: ObservedState,
  repoId: string
): StatusSegment[] {
  if (state.kind === "pending") {
    return [{ kind: "none", why: `asking what traffic ${repoId} has had recorded` }]
  }
  if (state.kind === "errored") {
    return [{ kind: "none", why: `the observed telemetry for ${repoId} did not answer` }]
  }

  const attachedAt = state.data.telemetry_attached_at
  if (attachedAt === null) {
    return [
      {
        kind: "records",
        label: set.label,
        text:
          "Nothing ever watched this repository, so there is nothing here to count — the absence " +
          "of a measurement rather than a measurement of nought.",
      },
      { kind: "figure", label: "Telemetry attached", value: null, scope: "never attached" },
    ]
  }

  const page = pageOf(state.data, set.key)
  return [
    {
      kind: "records",
      label: set.label,
      text: describeRecordWindow(
        set.offset,
        page.items.length,
        { count: page.total, boundReached: false },
        set.singular,
        set.plural
      ),
      // No pager over a set with no rows: the panel draws its account of the nought rather than a
      // table there, so there is no page for the buttons to move to.
      paging:
        page.total === 0
          ? undefined
          : {
              offset: set.offset,
              limit: DEFAULT_LIMIT,
              shown: page.items.length,
              total: page.total,
              nextOffset: page.next_offset,
              busy: state.fetching,
              onOffsetChange: set.onOffsetChange,
            },
    },
    { kind: "figure", label: "Telemetry attached", value: formatTimestamp(attachedAt) },
    {
      kind: "note",
      text:
        "Three sets are on screen and each pages on its own offset. The bar above carries every " +
        "set's total; this count and its pager describe the selected set alone, and a set moved " +
        "to a later page stays on it until it is selected again.",
    },
  ]
}

/** A set's total, or which silence this one is — the two are never the same ink. */
function setTotal(state: ObservedState, key: SetKey): ReactNode {
  if (state.kind === "pending") return <Absent>still asking</Absent>
  if (state.kind === "errored") return <Absent>did not answer</Absent>
  if (state.data.telemetry_attached_at === null) return <Absent>never attached</Absent>
  return pageOf(state.data, key).total.toLocaleString()
}

function SetSelector({
  sets,
  selected,
  onSelect,
  state,
}: {
  sets: readonly SignalSet[]
  selected: SetKey
  onSelect: (key: SetKey) => void
  state: ObservedState
}) {
  return (
    <div
      role="group"
      aria-label="Which set the status band counts"
      className="flex items-center gap-field overflow-x-auto"
    >
      <span className="furniture shrink-0 text-meta text-ink-muted">Counted below</span>
      {sets.map((set) => (
        <Button
          key={set.key}
          size="sm"
          // The pressed state is a fill, and a fill never travels alone.
          aria-pressed={set.key === selected}
          variant={set.key === selected ? "secondary" : "ghost"}
          onClick={() => onSelect(set.key)}
          className="shrink-0 text-meta"
        >
          {set.label} ({setTotal(state, set.key)})
        </Button>
      ))}
    </div>
  )
}

/**
 * Whether anything of this role is attached, as a word.
 *
 * The recipe is `RungBadge`'s: the furniture register, a hairline, no fill, no hue. Two members,
 * both legible without colour, and the vocabulary is absence — which is one of the three
 * `.claude/rules/console-surface.md` permits a badge to carry.
 */
function AttachmentChip({ attached }: { attached: boolean }) {
  return (
    <span className="furniture shrink-0 rounded-control border border-line px-field py-field text-meta text-ink-muted">
      {attached ? "Attached" : "Not attached"}
    </span>
  )
}

function RoleGroup({ role, children }: { role: SignalRole; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-section rounded-surface border border-line bg-card p-section">
      {/* A role group contains panels, so the two cannot share a step: levelling them renders a
          container and its contents at one weight. The role name was `--text-section` while a
          panel heading was furniture; M7-W188 moved the panel heading onto the section step, so
          the role name moves up to `--text-page` to keep the ordering it always had. */}
      <div className="flex flex-col gap-field">
        <div className="flex flex-wrap items-center gap-row">
          <h2 className="text-page">{role.role}</h2>
          <AttachmentChip attached={role.source !== null} />
        </div>
        <p className="text-body text-muted-foreground">{role.relationship}</p>
      </div>
      {children}
    </div>
  )
}

export interface SignalsPageProps {
  readonly question?: string
}

export function SignalsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />
  return <SignalsDetail repoId={repoId} />
}

/**
 * The strip's own read, kept out of `SignalsDetail` so a telemetry route that does not answer
 * costs the tiles and not the three role panels beneath, which read different routes entirely.
 */
function SignalsKpisRegion({ repoId }: { repoId: string }) {
  const query = useRepositoryObserved(repoId)
  if (query.isPending) return <LoadingState what="the observed telemetry totals" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the observed telemetry totals"
        onRetry={() => void query.refetch()}
      />
    )
  }
  return <SignalsKpis observed={query.data} />
}

function SignalsDetail({ repoId }: { repoId: string }) {
  // The same URL offsets and the same query key `SignalSourcePanel` reads below, so the bar and
  // the band describe the pages on screen rather than opening a second request for them.
  const [callsOffset, setCallsOffset] = useOffsetParam("calls_offset")
  const [shapesOffset, setShapesOffset] = useOffsetParam("shapes_offset")
  const [errorWindowsOffset, setErrorWindowsOffset] = useOffsetParam("error_windows_offset")
  // In the URL beside the offsets rather than in component state: Back restoring one without the
  // other leaves a set on page three with nothing on screen saying which rows it holds.
  const [selectedParam, setSelectedParam] = useFacetParam("signals_set")
  const observed = useRepositoryObserved(repoId, {
    callsLimit: DEFAULT_LIMIT,
    callsOffset,
    shapesLimit: DEFAULT_LIMIT,
    shapesOffset,
    errorWindowsLimit: DEFAULT_LIMIT,
    errorWindowsOffset,
  })

  const sets: SignalSet[] = [
    { key: "calls", ...SET_COPY.calls, offset: callsOffset, onOffsetChange: setCallsOffset },
    { key: "shapes", ...SET_COPY.shapes, offset: shapesOffset, onOffsetChange: setShapesOffset },
    {
      key: "error_windows",
      ...SET_COPY.error_windows,
      offset: errorWindowsOffset,
      onOffsetChange: setErrorWindowsOffset,
    },
  ]
  const selectedKey = toSetKey(selectedParam)
  const selected = sets.find((set) => set.key === selectedKey) ?? sets[0]

  const state: ObservedState = observed.isSuccess
    ? { kind: "answered", data: observed.data, fetching: observed.isFetching }
    : observed.isError
      ? { kind: "errored" }
      : { kind: "pending" }

  return (
    <ScreenFrame
      controls={
        <SetSelector
          sets={sets}
          selected={selectedKey}
          onSelect={(key) => setSelectedParam(key === "calls" ? null : key)}
          state={state}
        />
      }
      status={signalsStatus(selected, state, repoId)}
    >
    <section className="flex flex-col gap-8">
      {/* Dashboard S1. Every tile distinguishes "no source attached" from "attached and quiet",
          which is the distinction this whole rung exists to make and the one an empty page
          otherwise erases. */}
      <SignalsKpisRegion repoId={repoId} />

      {/* What the screen draws moves behind the ⓘ (owner direction 2026-08-18); the sentence
          that stays visible is the absence-versus-zero one, because which roles have anything
          behind them is a claim, not an explanation, and a tooltip is a disclosure. */}
      <div className="flex items-center gap-row">
        <h2 className="text-section">Attached by role</h2>
        <InfoHint label="About signals">
          Every integration attached to this repository&rsquo;s graph, grouped by the role it plays.
          Roles with something attached here: {names(ATTACHED_ROLES)}.
          {UNATTACHED_ROLES.length > 0 && <> Roles with none: {names(UNATTACHED_ROLES)}.</>} A role
          with nothing attached was never asked — there is no adapter, no configuration table and no
          row to ask, which is a different fact from an attached integration that was asked and had
          nothing to report. A group with no rows is a quiet integration rather than a missing one.
        </InfoHint>
      </div>

      {/* `repeat(3, minmax(0,1fr))`: the mock's own three-across row for the three M5 roles,
          rather than the three stacked full-width sections this screen drew before the
          2026-08-18 layout extraction. `xl:` guards the same content from collapsing three
          data-heavy cards into an unreadable single column below that breakpoint -- the mock
          renders at a fixed desktop width and does not have to make that call. */}
      <div className="grid auto-rows-fr gap-section xl:grid-cols-3">
        <RoleGroup role={VENDOR_ROLE}>
          <SubjectCatalogue repoId={repoId} />
        </RoleGroup>

        <RoleGroup role={SIGNAL_SOURCE_ROLE}>
          <SignalSourcePanel repoId={repoId} />
        </RoleGroup>

        <RoleGroup role={HUMAN_SURFACE_ROLE}>
          <NotAttachedState detail={HUMAN_SURFACE_ROLE.absence} />
        </RoleGroup>
      </div>

      {/* Dashboard 7. Propless: it reads `repoId` from the path param, as this page does, because
          telemetry attaches per repository and a fleet-wide version of the question has no single
          answer. It holds two refusals of its own -- it states what it counted over rather than
          summing a page, and it prints the figure instead of drawing a slope through one day. */}
      <ObservedVolumeCard />
    </section>
    </ScreenFrame>
  )
}
