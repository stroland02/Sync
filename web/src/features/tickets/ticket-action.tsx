/**
 * The finding rail's ticket row: the console's one write, and the state it left behind.
 *
 * Four states and each is a different claim: no ticket yet (the button), requested (queued for
 * the runner — a runner that never picks it up leaves it here, which is the honest reading of a
 * dead runner), in progress (a runner claimed it; the workflow page carries the narrative), and
 * done (the run's own outcome, worn on the outcome's tone). The row polls while mounted because
 * its whole point is to move while a reader watches.
 */

import { useCreateTicket, useTickets } from "@/api/queries"
import type { Ticket } from "@/api/types"
import { OutcomeTag, Tag } from "@/components/tag"
import { Absent } from "@/components/status"
import { Button } from "@/components/ui/button"

export const POLL_MS = 15_000

/** The newest ticket standing against one finding, or null. */
export function newestTicketFor(tickets: readonly Ticket[], findingId: string): Ticket | null {
  const mine = tickets.filter((ticket) => ticket.finding_id === findingId)
  if (mine.length === 0) return null
  return mine.reduce((a, b) => (a.requested_at >= b.requested_at ? a : b))
}

export function TicketAction({ repoId, findingId }: { repoId: string; findingId: string }) {
  const query = useTickets(repoId, null, { refetchIntervalMs: POLL_MS })
  const create = useCreateTicket(repoId)

  const ticket = query.isSuccess ? newestTicketFor(query.data.tickets, findingId) : null

  return (
    <div className="flex flex-col gap-field" data-testid="ticket-action">
      {ticket === null || ticket.status === "done" ? (
        <>
          <Button
            variant="outline"
            className="w-full justify-start"
            disabled={create.isPending || query.isPending}
            onClick={() => create.mutate(findingId)}
          >
            {create.isPending ? "Creating the ticket…" : "Create remediation ticket"}
          </Button>
          <p className="text-body text-ink-muted">
            Records the request; the runner picks it up and the workflow page carries what it
            does.
          </p>
        </>
      ) : (
        <div className="flex flex-wrap items-center gap-row">
          <Tag tone="neutral">
            {ticket.status === "requested" ? "ticket: initiated" : "ticket: in progress"}
          </Tag>
          <span className="text-meta text-ink-muted">
            {ticket.status === "requested"
              ? "queued — no runner has picked it up yet"
              : "a runner claimed it; the workflow below is live"}
          </span>
        </div>
      )}

      {ticket !== null && ticket.status === "done" && (
        <div className="flex flex-wrap items-center gap-row">
          <OutcomeTag outcome={ticket.outcome ?? "unknown"} />
          {ticket.outcome === "opened" && ticket.detail !== null ? (
            <a
              href={ticket.detail}
              target="_blank"
              rel="noreferrer"
              className="text-meta underline underline-offset-2"
            >
              the pull request
            </a>
          ) : (
            <span className="text-meta text-ink-muted">
              {ticket.detail ?? <Absent>the run recorded no detail</Absent>}
            </span>
          )}
        </div>
      )}

      {create.isError && (
        <p className="text-meta text-critical-ink">
          The ticket was not recorded: {String(create.error)}
        </p>
      )}
    </div>
  )
}
