/**
 * Every open finding's call site, across every vendor a repository is covered for -- the real
 * data `FileTreeCanvas` draws. No new backend route: `GET /api/vendors/{id}` already accepts
 * `repo_id`, so this composes `fetchRepositoryCoverage` (which vendors) with one
 * `fetchVendorFindings` call per vendor (each vendor's rows), rather than adding a fetch
 * function to the shared `api/client.ts` for one screen.
 *
 * `SCOPE_NOTE` on the canvas itself already says this is open findings, not every indexed call
 * site -- this hook is where that scope is actually drawn from, so the two must not drift apart.
 */

import { useQuery } from "@tanstack/react-query"

import { fetchRepositoryCoverage, fetchVendorFindings } from "@/api/client"
import type { RiskRow } from "@/api/types"

/** Large enough that a repository's whole open-finding set for one vendor is one page in practice; `total` on the returned page still says if it was not. */
const ALL_ROWS_LIMIT = 10_000

export function useRepositoryRiskRows(repoId: string) {
  return useQuery({
    queryKey: ["repositories", repoId, "risk-rows"],
    queryFn: async ({ signal }) => {
      const coverage = await fetchRepositoryCoverage(repoId, signal)
      const vendorIds = Object.keys(coverage.by_vendor)
      const pages = await Promise.all(
        vendorIds.map((vendorId) =>
          fetchVendorFindings(vendorId, { repoId, limit: ALL_ROWS_LIMIT }, signal)
        )
      )
      const rows: RiskRow[] = pages.flatMap((page) => page.items)
      const truncated = pages.some((page) => page.total > page.items.length)
      return { rows, truncated, vendorCount: vendorIds.length }
    },
  })
}
