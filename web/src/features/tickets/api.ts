/**
 * The ticket lane: the console's one write into remediation, and the read that renders it.
 *
 * Owner ruling 2026-08-19. A ticket is a *request* row — POSTing one records that an operator
 * asked and returns; `sync tickets` is the process that executes, so a dead runner shows up as
 * a ticket parked at `requested`, never as an HTTP timeout pretending to be progress. The
 * Findings page is the manual lane, the watch loop the automatic one, and the Detectors page
 * splits the two by `source`.
 */

import {
  ApiStatusError,
  MalformedResponseError,
  NotFoundError,
  UnreachableApiError,
} from "@/api/errors"
import type { Ticket, TicketsResponse } from "@/api/types"

export async function createTicket(findingId: string, signal?: AbortSignal): Promise<Ticket> {
  const path = `/api/findings/${encodeURIComponent(findingId)}/ticket`
  let response: Response
  try {
    response = await fetch(path, {
      method: "POST",
      headers: { Accept: "application/json" },
      signal,
    })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (response.status === 404) throw new NotFoundError(`finding ${findingId} is not open`, findingId, path)
  if (!response.ok) throw new ApiStatusError(response.status, path)
  try {
    return (await response.json()) as Ticket
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}

export async function fetchTickets(
  repoId: string,
  source: "operator" | "watch" | null = null,
  signal?: AbortSignal,
): Promise<TicketsResponse> {
  const base = `/api/repositories/${encodeURIComponent(repoId)}/tickets`
  const path = source === null ? base : `${base}?source=${source}`
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (!response.ok) throw new ApiStatusError(response.status, path)
  try {
    return (await response.json()) as TicketsResponse
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}
