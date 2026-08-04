/**
 * One hook per route, so a component names the question and never the URL.
 *
 * Query keys mirror the graph hierarchy, which means invalidating a vendor invalidates
 * everything read under it.
 */

import { useQuery } from "@tanstack/react-query"

import {
  DEFAULT_LIMIT,
  fetchFinding,
  fetchOverview,
  fetchVendorChanges,
  fetchVendorFindings,
} from "@/api/client"
import type { ChangeParams, PageParams } from "@/api/client"

export function useOverview() {
  return useQuery({
    queryKey: ["overview"],
    queryFn: ({ signal }) => fetchOverview(signal),
  })
}

export function useVendorFindings(vendorId: string, params: PageParams = {}) {
  const limit = params.limit ?? DEFAULT_LIMIT
  const offset = params.offset ?? 0
  return useQuery({
    queryKey: ["vendors", vendorId, "findings", limit, offset],
    queryFn: ({ signal }) => fetchVendorFindings(vendorId, { limit, offset }, signal),
  })
}

export function useVendorChanges(vendorId: string, params: ChangeParams = {}) {
  const limit = params.limit ?? DEFAULT_LIMIT
  const offset = params.offset ?? 0
  const since = params.since
  return useQuery({
    queryKey: ["vendors", vendorId, "changes", limit, offset, since ?? null],
    queryFn: ({ signal }) => fetchVendorChanges(vendorId, { limit, offset, since }, signal),
  })
}

export function useFinding(findingId: string) {
  return useQuery({
    queryKey: ["findings", findingId],
    queryFn: ({ signal }) => fetchFinding(findingId, signal),
  })
}
