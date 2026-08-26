/**
 * How the newest run stands, as one row of a fact list.
 *
 * **Extracted from `finding-page.tsx` at the second use** — the Findings inspector renders the same
 * row for the finding a reader has selected, and `CLAUDE.md` puts the factoring at the second use
 * rather than after two copies have drifted. Nothing here changed in the move; the finding page
 * imports it and renders exactly what it rendered before.
 *
 * Four kinds of nothing before there is anything to say, and they are not interchangeable: the
 * query is still in flight, the checkpointer holds no run for this finding, the request did not
 * produce an answer, or a run exists. `remediation.ts` is where they are told apart and why.
 *
 * The sentence under a retried finding points at the fleet's runs table rather than at a link this
 * route cannot serve: `GET /api/workflows/{finding_id}` answers with the newest generation only, and
 * `sync.dashboard.fleet.runs` is the query that lists every generation as its own row.
 */

import type { ReactNode } from "react"

import { Pending } from "@/features/findings/pending"
import { Absent } from "@/components/status"
import type { RemediationStanding, RemediationState } from "@/features/findings/remediation"

export function remediationFact(state: RemediationState): ReactNode {
  if (state.kind === "pending") return <Pending />
  if (state.kind === "none") {
    return <Absent>the checkpointer holds no run for this finding</Absent>
  }
  if (state.kind === "unavailable") return <Absent>the API did not answer</Absent>

  return (
    <div className="flex flex-col gap-field">
      <span>{standingWord(state.standing, state.outcome)}</span>
      {state.retried && (
        <span className="text-meta text-ink-muted">
          The newest of {state.generations} runs on this finding. The others are rows on the fleet's
          runs table; this level can see only that they exist.
        </span>
      )}
    </div>
  )
}

export function standingWord(standing: RemediationStanding, outcome: string | null): ReactNode {
  if (standing === "in-flight") return "In flight — no outcome written yet"
  if (standing === "opened") return "Opened a pull request"
  if (standing === "abandoned") return "Abandoned"
  if (standing === "reported") return "Reported, not patched"
  // Named rather than folded into whichever branch fell through last, which is the rule
  // `features/workflows/run-outcome.tsx` states at its own final branch: an unknown outcome
  // rendered as a known one is a confident wrong verdict.
  return (
    <>
      <span className="font-mono">{String(outcome)}</span> — an outcome this console has not caught
      up with
    </>
  )
}
