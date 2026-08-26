/**
 * Triage over a set too large to read: which of four answers a narrowed panel owes its reader, and
 * the three panels that say so when there are no records.
 *
 * **`TriageTabs` was deleted here on 2026-08-26 and this file renamed with it.** It owned a Radix
 * `Tabs` root that mounted one panel per severity kind to render a single table, and its one caller
 * — the Findings screen — no longer wraps its table in anything: the severity strip is now a
 * `ChipTabs` in the frame's controls band, and the table fills a viewport-locked pane beneath it.
 * A component with no caller is deleted rather than deprecated (`CLAUDE.md`). What is kept is the
 * half with a wrong answer — `triagePanelState` and the three panels — because the derivation is
 * what the tabs were carrying and the chips are not equipped to carry.
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
 * **What these refusals now govern is the chip strip**, since that is where the counts went:
 *
 * - **No total across the chips.** Every count on screen is one the caller was given; nothing here
 *   sums them. A sum over a set where one member is unanswered is not a number anybody measured.
 * - **No colour on a chip or a count.** A hue applied to a count would be grading a kind, and a
 *   colour that grades is the traffic light this product refuses.
 * - **No dot, badge tone or pulse.** A chip label is a change kind, a source, or a reason code —
 *   a recorded value from a closed vocabulary, legible as words.
 */

import type { ReactNode } from "react"

import { Absent } from "@/components/status"
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
    <Panel headline="This narrowing's count was not answered.">
      <p>
        The marker on the chip is the absence marker and not a zero: the query that would count{" "}
        {noun} under this value did not return, so nothing here knows how many there are.
      </p>
      <p>{count.why}</p>
    </Panel>
  )
}

/**
 * The panel a narrowed set owes its reader when it holds no records — or nothing at all.
 *
 * Returns `null` for `"records"`, which is the whole reason it is a component rather than a
 * caller's ternary: a screen renders it unconditionally above its table and the four-way decision
 * stays in `triagePanelState`, where the test can reach it. A caller writing its own branch is a
 * caller that will eventually write three of them and have two disagree.
 *
 * `count` is the active narrowing's own count and `label` is what that narrowing is called, so the
 * counted-zero panel says *No open findings under breaking* rather than *no records*.
 */
export function TriageEmpty({
  noun,
  label,
  count,
  checks,
}: {
  /** What is being counted, in the plural — "open findings". */
  noun: string
  /** The active narrowing, as a reader sees it written on its chip. */
  label: string
  count: TriageCount
  checks: TriageChecks
}) {
  const state = triagePanelState(count, checks)

  if (state === "records") return null
  if (state === "empty-after-check" && checks.kind === "checked") {
    return <EmptyAfterCheck noun={noun} label={label} checks={checks} />
  }
  if (state === "empty-before-any-check" && checks.kind === "unchecked") {
    return <EmptyBeforeAnyCheck noun={noun} checks={checks} />
  }
  // The count was not answered, so nothing here may claim the set is empty. It says that, and the
  // caller still renders whatever rows it has — a notice above real rows is honest; a blank panel
  // is the failure mode this module exists to remove.
  return count.kind === "unanswered" ? <CountUnanswered noun={noun} count={count} /> : null
}

