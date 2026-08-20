/**
 * The solutions funnel: every ticket on the left, splitting right by where each stands.
 *
 * The owner's drawn shape (2026-08-19): one total flowing left to right into the lifecycle's
 * stages — initiated, in progress, and complete split by the run's own outcome. Counts, not
 * rates: each band is a number of tickets and the bands out of a node sum to what flowed in,
 * which is what `assertConserves` holds and the one promise a Sankey makes.
 *
 * Nothing renders below one ticket — a funnel of zero is a claim nobody measured anything, and
 * the caller's empty state says the honest sentence instead.
 */

import type { Ticket } from "@/api/types"
import type { FlowLink, FlowNode } from "@/components/charts/sankey-flow"
import { SankeyFlow } from "@/components/charts/sankey-flow"
import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"

/** The funnel's nodes and links from a ticket set — exported pure for its own test. */
export function ticketFunnel(tickets: readonly Ticket[]): {
  nodes: FlowNode[]
  links: FlowLink[]
} {
  const counts = {
    requested: 0,
    picked_up: 0,
    opened: 0,
    abandoned: 0,
    reported: 0,
    other: 0,
  }
  for (const ticket of tickets) {
    if (ticket.status === "requested") counts.requested += 1
    else if (ticket.status === "picked_up") counts.picked_up += 1
    else if (ticket.outcome === "opened") counts.opened += 1
    else if (ticket.outcome === "abandoned") counts.abandoned += 1
    else if (ticket.outcome === "reported") counts.reported += 1
    else counts.other += 1
  }

  const nodes: FlowNode[] = [{ id: "tickets", label: `Tickets (${tickets.length})` }]
  const links: FlowLink[] = []
  const stage = (
    id: string,
    label: string,
    value: number,
    tone?: "good" | "warning" | "serious" | "critical",
  ) => {
    if (value === 0) return
    nodes.push({ id, label: `${label} (${value})`, tone })
    links.push({ source: "tickets", target: id, value })
  }
  stage("initiated", "Initiated", counts.requested)
  stage("in-progress", "In progress", counts.picked_up)
  stage("opened", "Opened a PR", counts.opened, "good")
  stage("abandoned", "Abandoned", counts.abandoned, "serious")
  stage("reported", "Reported", counts.reported, "warning")
  stage("other", "Ended, outcome unrecognised", counts.other)
  return { nodes, links }
}

export function TicketFunnel({ tickets }: { tickets: readonly Ticket[] }) {
  if (tickets.length === 0) return null
  const { nodes, links } = ticketFunnel(tickets)

  return (
    <MetricPanel
      label="Solutions funnel"
      hint={
        <InfoHint label="About the solutions funnel">
          Every remediation ticket this workspace holds — operator-created and watch-created
          alike — flowing into where each stands now. A completed ticket wears the run&rsquo;s
          own outcome; an initiated one is waiting for a runner, which is a real place a ticket
          can honestly sit.
        </InfoHint>
      }
      caption="Counts of tickets, not rates; the bands out of the left node sum to the total."
    >
      <SankeyFlow nodes={nodes} links={links} unit="tickets" height={220} />
    </MetricPanel>
  )
}
