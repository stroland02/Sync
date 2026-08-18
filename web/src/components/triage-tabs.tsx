/**
 * Triage over a set too large to read: tabs across the top, each carrying its own count, a slot
 * for the controls that narrow the set, and an empty state that says what was checked.
 *
 * The arrangement is a convention of the form — `.claude/rules/interface-originality.md` permits
 * a tabbed count header the way it permits a table. What is ours is what goes in the counts and
 * what the panel says when there is nothing in it.
 *
 * **Two distinctions live in the types rather than in a caller's discipline, because both fail
 * silently when a caller gets them wrong.**
 *
 * A count is `{ kind: "counted", value }` or `{ kind: "unanswered", why }`. There is no `number`
 * to pass, so a view that never asked the question cannot render `0` by accident — it renders the
 * console's absence marker, and the reason travels with it. A confirmed zero renders `0`, which is
 * a different fact and looks like one.
 *
 * What was checked is a **required prop**, not an optional garnish, and its `checked` arm takes a
 * non-empty tuple:
 *
 * ```ts
 * const checks: TriageChecks =
 *   detectors.length === 0
 *     ? { kind: "unchecked", why: "no scan has run against this repository yet" }
 *     : { kind: "checked", ran: [detectors[0], ...detectors.slice(1)], at: scannedAt }
 * ```
 *
 * A caller holding a `string[]` from a payload has to write that branch to compile, and the branch
 * is the honest one: an empty detector list *is* "nothing has checked this". That is the whole
 * reason the tuple is spelled `[string, ...string[]]` rather than `string[]`. An empty findings
 * list after a real scan and an empty one before any scan are different facts, and keeping them
 * apart is why this console exists — `docs/superpowers/plans/2026-08-18-page-information-architecture.md:122-123`.
 *
 * **What this component refuses to render**, each because the data does not hold it:
 *
 * - **No total across the tabs.** Every count on screen is one the caller was given; nothing here
 *   sums them. A sum over a set where one member is unanswered is not a number anybody measured.
 * - **No colour on a tab or a count.** Selection is carried by the tab role and `aria-selected`.
 *   A hue applied to a count would be grading a kind, and a colour that grades is the traffic
 *   light this product refuses.
 * - **No dot, badge tone or pulse.** A tab label is a change kind, a source, or a reason code —
 *   a recorded value from a closed vocabulary, legible as words.
 */

import type { ReactNode } from "react"

import { Absent } from "@/components/status"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/vendor/supabase/ui/tabs"
import { formatTimestamp } from "@/lib/format"

/**
 * How many rows a tab accounts for — or that nobody answered the question.
 *
 * `why` is required on the unanswered arm. An absence marker with no reason behind it is the
 * defect this console spent six rounds closing: a reader cannot tell "we did not ask" from
 * "the route failed" from "this view cannot see it", and all three arrive as one glyph.
 */
export type TriageCount =
  | { readonly kind: "counted"; readonly value: number }
  | { readonly kind: "unanswered"; readonly why: string }

/** One tab: a value from a closed vocabulary, and what it accounts for. */
export interface TriageTab {
  /** The vocabulary value itself — a change kind, a signal source, an abandon reason code. */
  readonly id: string
  /** How that value is written for a reader. */
  readonly label: string
  readonly count: TriageCount
}

/**
 * What ran over this scope, which is the fact an empty list is meaningless without.
 *
 * `ran` is a non-empty tuple on purpose: a caller whose detector list came back empty has not
 * checked anything, and must say so through the other arm rather than by passing `[]`.
 */
export type TriageChecks =
  | {
      readonly kind: "checked"
      readonly ran: readonly [string, ...string[]]
      /** When the check ran, ISO 8601. `null` renders the absence marker, never a guess. */
      readonly at?: string | null
    }
  | { readonly kind: "unchecked"; readonly why: string }

/** What the active tab's panel is showing, which is four different answers and not two. */
export type TriagePanelState =
  | "records"
  | "empty-after-check"
  | "empty-before-any-check"
  | "count-unanswered"

/**
 * Which of the four the panel owes its reader.
 *
 * Exported because it is a derivation with a wrong answer, and `.claude/rules/console-dev-loop.md`
 * puts those under test rather than under review.
 */
export function triagePanelState(count: TriageCount, checks: TriageChecks): TriagePanelState {
  if (count.kind === "unanswered") return "count-unanswered"
  if (count.value > 0) return "records"
  return checks.kind === "checked" ? "empty-after-check" : "empty-before-any-check"
}

/** The count as it sits on its tab: a figure, or the one absence marker with its reason. */
function TabCount({ count }: { count: TriageCount }) {
  if (count.kind === "unanswered") {
    return (
      <span className="text-ink-muted">
        <Absent />
        <span className="sr-only"> count not answered: {count.why}</span>
      </span>
    )
  }
  return <span className="text-ink-muted tabular-nums">{count.value.toLocaleString()}</span>
}

function Panel({ headline, children }: { headline: string; children: ReactNode }) {
  return (
    <div className="max-w-prose rounded-surface border border-line bg-surface p-section">
      <p className="text-emphasis text-ink">{headline}</p>
      <div className="mt-field flex flex-col gap-field text-body text-ink-muted">{children}</div>
    </div>
  )
}

function EmptyAfterCheck({
  noun,
  label,
  checks,
}: {
  noun: string
  label: string
  checks: Extract<TriageChecks, { kind: "checked" }>
}) {
  const at = formatTimestamp(checks.at)
  return (
    <Panel headline={`No ${noun} under ${label}.`}>
      <p>
        This is a counted zero rather than an absence: the query was answered and it came back with
        nothing under this value.
      </p>
      <p>
        Checked by{" "}
        {checks.ran.map((detector, index) => (
          <span key={detector}>
            {index > 0 ? ", " : ""}
            <span className="font-mono text-ink">{detector}</span>
          </span>
        ))}
        .
      </p>
      <p>
        {at === null ? (
          <>
            <Absent>no time recorded for that check</Absent> — the payload carries which detectors
            ran but not when, so this zero cannot be dated.
          </>
        ) : (
          <>Last checked {at}.</>
        )}
      </p>
    </Panel>
  )
}

function EmptyBeforeAnyCheck({
  noun,
  checks,
}: {
  noun: string
  checks: Extract<TriageChecks, { kind: "unchecked" }>
}) {
  return (
    <Panel headline={`Nothing has checked for ${noun} here.`}>
      <p>
        <Absent>this is not a zero</Absent>. No detector has run over this scope, so the console has
        nothing to report either way — an empty list after a real scan would be a different fact,
        and this view will not show you one in place of the other.
      </p>
      <p>{checks.why}</p>
    </Panel>
  )
}

function CountUnanswered({ noun, count }: { noun: string; count: Extract<TriageCount, { kind: "unanswered" }> }) {
  return (
    <Panel headline="This tab's count was not answered.">
      <p>
        The marker on the tab is the absence marker and not a zero: the query that would count{" "}
        {noun} under this value did not return, so nothing here knows how many there are.
      </p>
      <p>{count.why}</p>
    </Panel>
  )
}

/**
 * `children` is the active tab's records, rendered by the caller. Only the active tab's panel is
 * mounted, so a caller renders one table rather than one per tab.
 */
export function TriageTabs({
  legend,
  noun,
  tabs,
  activeId,
  onSelect,
  checks,
  filters,
  children,
}: {
  /** What the tabs divide, named for a screen reader — "Findings by kind". */
  legend: string
  /** What is being counted, in the plural, for the empty state's own sentences. */
  noun: string
  tabs: readonly TriageTab[]
  activeId: string
  onSelect: (id: string) => void
  /** Required. An empty state that cannot say what was checked is the one this replaces. */
  checks: TriageChecks
  /** The controls that narrow the active tab's set. Deliberately outside the tablist. */
  filters?: ReactNode
  children?: ReactNode
}) {
  return (
    <Tabs value={activeId} onValueChange={onSelect} className="flex min-w-0 flex-col gap-section">
      <div className="flex min-w-0 flex-wrap items-end justify-between gap-section">
        <TabsList aria-label={legend} className="min-w-0 flex-wrap gap-section">
          {tabs.map((tab) => (
            <TabsTrigger key={tab.id} value={tab.id} className="gap-row px-row">
              <span>{tab.label}</span>
              <TabCount count={tab.count} />
            </TabsTrigger>
          ))}
        </TabsList>
        {filters !== undefined && (
          <div className="flex min-w-0 flex-wrap items-end gap-row">{filters}</div>
        )}
      </div>
      {tabs.map((tab) => (
        <TabsContent key={tab.id} value={tab.id} className="mt-0 min-w-0">
          <TriagePanel noun={noun} tab={tab} checks={checks}>
            {children}
          </TriagePanel>
        </TabsContent>
      ))}
    </Tabs>
  )
}

function TriagePanel({
  noun,
  tab,
  checks,
  children,
}: {
  noun: string
  tab: TriageTab
  checks: TriageChecks
  children?: ReactNode
}) {
  const state = triagePanelState(tab.count, checks)

  if (state === "records") return <>{children}</>

  if (state === "empty-after-check" && checks.kind === "checked") {
    return <EmptyAfterCheck noun={noun} label={tab.label} checks={checks} />
  }

  if (state === "empty-before-any-check" && checks.kind === "unchecked") {
    return <EmptyBeforeAnyCheck noun={noun} checks={checks} />
  }

  // The count was not answered, so the panel cannot claim the set is empty. It says that, and
  // still renders whatever the caller has — a notice above real rows is honest; a blank panel is
  // the failure mode this whole component exists to remove.
  return (
    <div className="flex min-w-0 flex-col gap-section">
      {tab.count.kind === "unanswered" && <CountUnanswered noun={noun} count={tab.count} />}
      {children}
    </div>
  )
}
