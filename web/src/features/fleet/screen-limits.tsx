/**
 * What this screen cannot tell you, permanently — not a footnote and not behind a
 * disclosure. Every figure below has an honest scope; this panel is the standing set of
 * things no figure on this screen can answer at all, at the same visual weight as the
 * figures themselves.
 */

import { MetricPanel } from "@/components/metric-panel"

const LIMITS: readonly { headline: string; detail: string }[] = [
  {
    headline: "A repository the index never indexed is invisible.",
    detail:
      "It has no row in the repository list below — the same absence as a repository " +
      "nobody ever configured. Nothing in this data tells the two apart.",
  },
  {
    headline: "The repair record's denominator excludes the earliest failures.",
    detail:
      "Three abandonment classes never write a migration_outcome row: an abandonment " +
      "before any attempt, one with no tier applied, and one whose state was missing its " +
      "finding, site or change. Those runs are real — the runs table above still names " +
      "them through an abandon reason — but they leave no attempt for the repair record " +
      "to count.",
  },
  {
    headline: "“Last checkpoint” is staleness, not liveness.",
    detail:
      "There is no heartbeat and no process registry. A run waiting on the customer's CI " +
      "writes no checkpoint for as long as that takes, by design, and a run that has " +
      "actually died looks identical here. Nothing on this screen guesses which is which.",
  },
  {
    headline: "Findings cannot be ordered by severity across every vendor yet.",
    detail:
      "GET /api/overview counts open findings per vendor; no route yet accepts the " +
      "severity filter the frozen surface already offers. Until one does, the vendor " +
      "panel above orders by open finding count, not by how severe those findings are.",
  },
]

export function ScreenLimitsCard() {
  return (
    <MetricPanel
      label="What this screen cannot tell you"
      caption={
        <p className="max-w-prose">
          Four standing limits of the data behind this page, not gaps in how it is drawn.
        </p>
      }
    >
      {/* Each headline sits at `text-emphasis`, which is heavier than the furniture register
          the panel name above it takes, and that inversion is deliberate rather than a leftover.
          A panel name is scanned and a standing limit is read, which DESIGN.md assigns as two
          roles rather than two weights on one scale -- `metric-panel.tsx` states the rule. The
          failure this guards against is the older one: a limit rendered smaller than the figures
          it limits reads as a footnote, and a limit nobody reads limits nothing.
          `tracking-normal` cancels the heading tracking `text-emphasis` carries from the ramp,
          because four `dt`s in a column are in-row emphasis repeated, not four headings. */}
      {/* One column, not two. M7-W163 moved this panel beside the figures it qualifies rather
          than under them, which is what this file's own docstring always claimed — and at a third
          of the content width `sm:grid-cols-2` put four paragraphs into two 190px columns.
          Measured at 1440x900: eleven lines of prose in a column narrower than the sentence it
          carries. A limit nobody reads limits nothing. */}
      <dl className="grid gap-section">
        {LIMITS.map((limit) => (
          <div key={limit.headline} className="flex flex-col gap-field">
            <dt className="text-emphasis tracking-normal text-foreground">{limit.headline}</dt>
            <dd className="max-w-prose text-body text-muted-foreground">{limit.detail}</dd>
          </div>
        ))}
      </dl>
    </MetricPanel>
  )
}
