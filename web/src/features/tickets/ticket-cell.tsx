/**
 * One finding's place in the solutions workflow, sized for a table cell.
 *
 * The same four claims `TicketAction` makes in the finding rail, compressed: no ticket yet
 * (the send button — the console's one write, which records the request and nothing more),
 * requested (queued; a runner that never picks it up leaves it here, which is the honest
 * reading of a dead runner), in progress (a runner holds it), and done (the run's own outcome,
 * with the pull request one press away when there is one).
 */

import { useCreateTicket } from "@/api/queries"
import type { Ticket } from "@/api/types"
import { OutcomeTag, Tag } from "@/components/tag"
import { Absent } from "@/components/status"
import { Button } from "@/components/ui/button"
import { newestTicketFor } from "@/features/tickets/ticket-action"

export function TicketCell({
  repoId,
  findingId,
  tickets,
}: {
  repoId: string
  findingId: string
  /** The workspace's tickets, fetched once by the page; null while that read is in flight. */
  tickets: readonly Ticket[] | null
}) {
  const create = useCreateTicket(repoId)

  if (tickets === null) {
    return <Absent>not read yet</Absent>
  }

  const ticket = newestTicketFor(tickets, findingId)

  if (ticket === null || (ticket.status === "done" && ticket.outcome === "abandoned")) {
    return (
      <div className="flex items-center gap-row">
        {ticket !== null && <OutcomeTag outcome={ticket.outcome ?? "unknown"} />}
        <Button
          variant="outline"
          size="sm"
          disabled={create.isPending}
          onClick={() => create.mutate(findingId)}
        >
          {create.isPending
            ? "Sending…"
            : ticket !== null
              ? "Send again"
              : "Send to workflow"}
        </Button>
      </div>
    )
  }

  if (ticket.status === "requested") {
    return <Tag tone="neutral">queued</Tag>
  }
  if (ticket.status === "picked_up") {
    return <Tag tone="neutral">in progress</Tag>
  }

  return (
    <div className="flex items-center gap-row">
      <OutcomeTag outcome={ticket.outcome ?? "unknown"} />
      {ticket.outcome === "opened" && ticket.detail !== null && (
        <a
          href={ticket.detail}
          target="_blank"
          rel="noreferrer"
          className="text-meta underline underline-offset-2"
        >
          PR
        </a>
      )}
    </div>
  )
}
