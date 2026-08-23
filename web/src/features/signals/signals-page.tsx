/**
 * Signals: every integration attached to one repository's graph, grouped by the role it plays
 * (`docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:455-459`).
 *
 * Role names and relationship sentences live in `roles.ts`, never spelled here:
 * `tests/test_console_signals_roles.py` fails when this file names a role.
 *
 * Nothing in this tree gives the human-surface role an answer — no adapter, no configuration
 * table, no row names a delivery destination — so it renders a stated absence rather than an empty
 * table, which would claim a question had been asked. B94 tracks what would attach it.
 *
 * A null `telemetry_attached_at` renders "never attached" and never `0`; `signals-page.test.ts`
 * holds it.
 *
 * Owner ruling: the controls bar names which set the band counts and the three tables give up
 * their footers to it. The live alternative was the binding surface's — each set's footer under
 * its own rows — and no set here is the screen's subject the way call sites are there.
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

/** Labels below are `signal-source-panel.tsx`'s panel headings verbatim; a synonym leaves the bar
    and the band pointing at no table anyone can name. */
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
      // An empty set draws its account of the nought, not a table, so there is no page to move to.
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

/** A word rather than a dot: attachment is a fact about configuration, and a dot would claim a
    lifecycle state — whether anything reported recently — that this data does not hold. */
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
      {/* A role group contains panels, so the two cannot share a type step; the panel heading sits
          on the section step, which puts this one above it. */}
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

/** Its own read, kept out of `SignalsDetail` so a telemetry route that does not answer costs the
    tiles and not the three role panels beneath, which read different routes entirely. */
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
      <SignalsKpisRegion repoId={repoId} />

      {/* Owner direction 2026-08-18: what the screen draws moves behind the ⓘ, and only the
          absence-versus-zero sentence stays on screen. */}
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

      {/* Three across at `xl` only: the signal-source panels hold tables of seven to twelve
          columns, and a table that wide at a third of a narrower screen wraps every row. */}
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

      {/* Propless: it reads `repoId` from the path param itself. */}
      <ObservedVolumeCard />
    </section>
    </ScreenFrame>
  )
}
