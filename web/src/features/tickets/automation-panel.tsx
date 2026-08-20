/**
 * The automatic lane: findings the watch loop ticketed on its own policy, and where each went.
 *
 * The Detectors page's opening answer by the owner's ruling of 2026-08-19 — this page is where
 * a reader sees what the platform did *without* a human: detected, ticketed, ran the solution
 * workflow, opened the pull request. The manual lane (an operator pressing the button on a
 * finding) deliberately does not appear here; the Findings page owns that act, and pooling the
 * lanes would erase this page's question.
 *
 * An empty table under an attached watch loop is a real answer (nothing met the policy); the
 * caption says the lane's precondition rather than letting the empty read as broken.
 */

import { Link } from "react-router"

import { useTickets } from "@/api/queries"
import { OutcomeTag, Tag } from "@/components/tag"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { ErrorState, LoadingState } from "@/components/states"
import { TableEmptyState } from "@/components/table-empty"
import { formatTimestamp } from "@/lib/format"

const POLL_MS = 15_000

export function AutomationPanel({ repoId }: { repoId: string }) {
  const query = useTickets(repoId, "watch", { refetchIntervalMs: POLL_MS })

  if (query.isPending) return <LoadingState what="the automatic lane's tickets" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the automatic lane's tickets"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const tickets = query.data.tickets

  return (
    <MetricPanel
      label="Automatic lane"
      hint={
        <InfoHint label="About the automatic lane">
          Tickets the watch loop created on its own policy — no human pressed anything. Each row
          is one finding carried from detection to a solution workflow and, where the run
          succeeded, to a pull request. Tickets an operator created live on the finding itself
          and in the Solutions funnel, never here: this page answers what ran unattended.
        </InfoHint>
      }
      caption="Findings the watch loop ticketed by policy, newest first — the loop running unattended."
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Finding</TableHead>
            <TableHead>Requested</TableHead>
            <TableHead>Stage</TableHead>
            <TableHead>Outcome</TableHead>
            <TableHead>Where it went</TableHead>
          </TableRow>
        </TableHeader>
        {tickets.length === 0 ? (
          <TableEmptyState
            columns={5}
            headline="The watch loop has ticketed nothing here."
            detail="Either no finding met a subscription's policy, or the loop has not run since one did. An operator's own tickets are on the findings they ticketed, not here."
          />
        ) : (
          <TableBody>
            {tickets.map((ticket) => (
              <TableRow key={ticket.id}>
                <TableCell className="font-mono">
                  <Link
                    to={`/repositories/${encodeURIComponent(repoId)}/findings/${encodeURIComponent(ticket.finding_id)}`}
                    className="underline underline-offset-2"
                  >
                    {ticket.finding_id.slice(0, 12)}
                  </Link>
                </TableCell>
                <TableCell className="text-meta text-ink-muted">
                  {formatTimestamp(ticket.requested_at)}
                </TableCell>
                <TableCell>
                  <Tag tone="neutral">
                    {ticket.status === "requested"
                      ? "initiated"
                      : ticket.status === "picked_up"
                        ? "in progress"
                        : "complete"}
                  </Tag>
                </TableCell>
                <TableCell>
                  {ticket.outcome !== null ? <OutcomeTag outcome={ticket.outcome} /> : null}
                </TableCell>
                <TableCell className="text-meta">
                  {ticket.outcome === "opened" && ticket.detail !== null ? (
                    <a
                      href={ticket.detail}
                      target="_blank"
                      rel="noreferrer"
                      className="underline underline-offset-2"
                    >
                      pull request
                    </a>
                  ) : (
                    <Link
                      to={`/repositories/${encodeURIComponent(repoId)}/findings/${encodeURIComponent(ticket.finding_id)}/workflow`}
                      className="underline underline-offset-2"
                    >
                      workflow
                    </Link>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        )}
      </Table>
    </MetricPanel>
  )
}
