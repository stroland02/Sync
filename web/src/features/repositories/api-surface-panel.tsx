/**
 * How much of this codebase's API surface is at risk, clean, or unexamined.
 *
 * **The owner's question, 2026-08-19: *why do we not show safe APIs?*** Every other panel on this
 * console counts problems, so a codebase where nothing is wrong renders as a screen full of
 * nothing — indistinguishable from one nobody has looked at. This is the panel that tells those
 * two apart, and it is the only one here whose good news is a number rather than an absence.
 *
 * ## Bars, because two of the three members are usually zero
 *
 * `web/CLAUDE.md` learned this expensively on the provenance donut: **a donut cannot draw a zero**,
 * and it shipped as a closed ring that read as broken. A bar of length zero still has a row, a
 * label and a count. The same rule applies here and for the same reason — a healthy codebase has
 * `at_risk: 0`, which is exactly the figure a reader came to see.
 *
 * ## Counted over operations, not call sites
 *
 * *How much of my API surface is safe* is a question about breadth. Forty call sites to one
 * operation is one thing to know about, and counting sites would let a single heavily-called
 * operation dominate the answer. The payload states the grain and the panel repeats it on screen.
 *
 * ## What the panel refuses
 *
 * **No percentage and no ratio.** "94% clean" is a health figure, and `web/CLAUDE.md` rejects one
 * on the record three times: a scalar that averages *we could not check* with *we checked and it
 * passed* collapses the distinction this product exists to make. The counts stand as counts.
 */

import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { RankedBars } from "@/components/ranked-bars"
import { BindingStatusTag } from "@/components/tag"
import { BINDING_STATUSES } from "@/api/types"

/** The words the panel uses, matching the tag's so one status reads one way on every screen. */
const LABEL: Record<string, string> = {
  at_risk: "At risk",
  unchecked: "Not checked",
  clean: "Clean",
}

/**
 * The bars, in `BINDING_STATUSES`' own order and always all three.
 *
 * A member missing from the payload is rendered at zero **here and only here**: the payload is
 * explicit that an absent key was not measured at nought, and what makes filling it honest is
 * that this panel only renders at all once the repository has call sites. Given a surface exists,
 * every operation in it has exactly one of these three statuses, so a member the grouping did not
 * return really is a measured zero rather than an unasked question.
 */
export function surfaceBars(counts: Record<string, number>) {
  return BINDING_STATUSES.map((status) => ({
    key: LABEL[status] ?? status,
    value: counts[status] ?? 0,
  }))
}

export function ApiSurfacePanel({ counts }: { counts: Record<string, number> }) {
  const operations = Object.values(counts).reduce((sum, n) => sum + n, 0)

  // No call sites at all: never indexed, or indexed and found to call nothing. Three zeroes here
  // would claim this codebase's operations had been examined and found clean.
  if (operations === 0) {
    return (
      <MetricPanel
        label="API surface"
        hint={
          <InfoHint label="About the API surface">
            Every operation this codebase calls, and whether the vendor&rsquo;s specification has
            been read against it. Empty here means the index holds no call site for this
            workspace &mdash; either no pass has run, or one ran and found no call to an
            integration Sync can watch.
          </InfoHint>
        }
        metric={{ value: "—", unit: "no operation indexed in this codebase" }}
      >
        <p className="max-w-prose text-meta text-ink-muted">
          Nothing here has been examined and found clean &mdash; there is nothing here yet. The
          Overview&rsquo;s Getting started says whether a pass has run.
        </p>
      </MetricPanel>
    )
  }

  return (
    <MetricPanel
      label="API surface"
      hint={
        <InfoHint label="About the API surface">
          Every operation this codebase calls, counted once each however many times it is called.
          <strong> Clean</strong> means the vendor&rsquo;s specification was read and nothing in it
          binds to the call — a measured answer, not an absent one.
          <strong> Not checked</strong> means no successful intake for that integration, so its
          specification has never been read: a decline or a failed fetch is not evidence about the
          call. There is no percentage here on purpose — a single figure averaging *we could not
          check* with *we checked and it passed* would collapse the distinction this panel exists
          to draw.
        </InfoHint>
      }
      metric={{
        value: operations.toLocaleString(),
        unit: `operation${operations === 1 ? "" : "s"} this codebase calls`,
      }}
    >
      <RankedBars
        label="By binding status"
        caption="Counted over the operations this codebase calls, one each however many times it is called."
        rows={surfaceBars(counts)}
        unit="operations"
        colourByKey={false}
      />
      <p className="flex flex-wrap items-center gap-field text-meta text-ink-muted">
        {BINDING_STATUSES.map((status) => (
          <BindingStatusTag key={status} status={status} />
        ))}
      </p>
    </MetricPanel>
  )
}
