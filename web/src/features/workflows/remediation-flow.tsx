/**
 * Where remediation work stops: findings in, outcomes out, and the gap between.
 *
 * **Attrition, counted in findings.** Every screen counts a stage — findings here, runs there,
 * pull requests on this page — and a table shows a codebase with 24 findings and no attempts
 * identically to one with 24 findings and 24 abandonments. The solutions funnel beside this one
 * draws attrition too, over tickets; this is the only one whose unit is findings.
 *
 * ## Counted in findings, and only findings
 *
 * `sankey-flow.tsx` refuses a diagram whose units change, and this is the caller that provoked
 * the rule. Sync's own graph carries **8,723 vendor changes**, which produced **13 change units**,
 * which carry **24 open findings**. Those are three different things: one change can bind nothing,
 * one unit can carry eleven findings. Drawing them as one flow would make each boundary a
 * widening or a narrowing that means nothing.
 *
 * So the diagram starts at findings — the first stage where one row is one unit of work the
 * pipeline acts on — and the change-to-finding fan-out is stated as a figure beside it rather
 * than drawn as a band.
 *
 * **A terminal node is not a failure.** *Not yet attempted* is the ordinary state of a deployment
 * whose remediation loop has not run, and it is drawn like every other destination — no colour
 * saying otherwise, because this console does not have a worse-versus-better axis.
 */

import { useQuery } from "@tanstack/react-query"

import { useOverview } from "@/api/queries"
import { fetchRemediationActivity } from "@/features/workflows/remediation-activity"
import type { FlowLink, FlowNode } from "@/components/charts/sankey-flow"
import { SankeyFlow } from "@/components/charts/sankey-flow"
import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { Absent } from "@/components/status"
import { ErrorState, LoadingState } from "@/components/states"

/** What a terminal status means to a reader, in the diagram's own words. */
const OUTCOME_LABEL: Record<string, string> = {
  pr_opened: "opened a pull request",
  abandoned: "abandoned",
  reported: "reported, not patched",
  in_flight: "no outcome recorded",
}

export function RemediationFlow({
  repoId,
  frame = "plain",
}: {
  repoId: string
  frame?: "plain" | "board"
}) {
  const overview = useOverview(repoId)
  const activity = useQuery({
    queryKey: ["corpus-activity"],
    queryFn: ({ signal }) => fetchRemediationActivity(signal),
  })

  if (overview.isPending || activity.isPending) {
    return <LoadingState what="the remediation flow" />
  }
  if (overview.isError) {
    return (
      <ErrorState
        error={overview.error}
        what="the remediation flow"
        onRetry={() => void overview.refetch()}
      />
    )
  }
  if (activity.isError) {
    return (
      <ErrorState
        error={activity.error}
        what="the remediation flow"
        onRetry={() => void activity.refetch()}
      />
    )
  }

  const findings = overview.data.total_findings

  // Attempts by terminal status, summed across tiers. The corpus is fleet-wide and the findings
  // count is this workspace's, so these are only comparable while the deployment holds one
  // workspace -- which the hint states rather than the diagram implying.
  const byOutcome = new Map<string, number>()
  for (const counts of Object.values(activity.data.by_tier)) {
    for (const [status, n] of Object.entries(counts)) {
      byOutcome.set(status, (byOutcome.get(status) ?? 0) + n)
    }
  }
  const attempted = [...byOutcome.values()].reduce((sum, n) => sum + n, 0)
  // Clamped at zero: with a fleet-wide corpus and a scoped finding count, attempts can exceed
  // findings, and a negative band is not a thing a Sankey can draw.
  const untouched = Math.max(findings - attempted, 0)

  const nodes: FlowNode[] = [{ id: "open", label: "Open findings" }]
  const links: FlowLink[] = []

  if (attempted > 0) {
    nodes.push({ id: "attempted", label: "Attempted" })
    links.push({ source: "open", target: "attempted", value: attempted })
    for (const [status, n] of [...byOutcome].sort(([a], [b]) => a.localeCompare(b))) {
      nodes.push({ id: status, label: OUTCOME_LABEL[status] ?? status })
      links.push({ source: "attempted", target: status, value: n })
    }
  }
  if (untouched > 0) {
    nodes.push({ id: "untouched", label: "Not yet attempted" })
    links.push({ source: "open", target: "untouched", value: untouched })
  }

  const hint = (
    <InfoHint label="About the remediation flow">
      Where the pipeline&rsquo;s work stops. Counted in <em>findings</em> throughout and in nothing
      else — the vendor changes upstream are a different unit, since one change can bind nothing
      here and one change unit can carry a dozen findings, so the fan-out between them is stated
      as a figure rather than drawn as a band. A destination is not a failure: <em>not yet
      attempted</em> is the ordinary state of a deployment whose remediation loop has not run.
      Attempt counts come from the corpus, which stores no repository and is therefore fleet-wide,
      while the finding count is this workspace&rsquo;s — comparable only while this deployment
      holds one workspace.
    </InfoHint>
  )

  return (
    <MetricPanel
      frame={frame}
      label="Where remediation work stops"
      hint={hint}
      caption="Open findings and what became of them, counted in findings — not in tickets and not in runs. The funnel below counts tickets, which is a different unit over a different set."
    >
      {findings === 0 ? (
        <span className="text-body">
          <Absent>no open finding to follow</Absent>
        </span>
      ) : (
        <SankeyFlow nodes={nodes} links={links} unit="findings" height={220} />
      )}
    </MetricPanel>
  )
}
