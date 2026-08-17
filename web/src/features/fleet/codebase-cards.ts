/**
 * What one repository card may claim, computed from an answer scoped to that repository.
 *
 * `/api/overview` echoes the scope it was computed for; a fleet-wide figure rendered
 * under a repository's name is a false claim about that repository, which is exactly
 * what this panel used to do. `openFindings` stays null until the scoped answer for
 * this repository has arrived — null is "not yet answered" and renders as the absence
 * marker, never as zero and never as "Clean".
 */

import type { OverviewResponse } from "@/api/types"

export type CodebaseFilter = "ALL" | "NEEDS_REVIEW" | "CLEAN"

export interface CodebaseCardFacts {
  repoId: string
  openFindings: number | null
  vendors: string[]
}

export function cardFacts(
  repoId: string,
  overview: OverviewResponse | undefined
): CodebaseCardFacts {
  if (overview === undefined || overview.repo_id !== repoId) {
    return { repoId, openFindings: null, vendors: [] }
  }
  return {
    repoId,
    openFindings: overview.total_findings,
    vendors: overview.vendors.map((v) => v.vendor_id),
  }
}

export function matchesFilter(facts: CodebaseCardFacts, filter: CodebaseFilter): boolean {
  if (filter === "NEEDS_REVIEW") return facts.openFindings !== null && facts.openFindings > 0
  if (filter === "CLEAN") return facts.openFindings === 0
  return true
}
