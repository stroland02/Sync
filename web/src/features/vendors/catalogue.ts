/**
 * The integrations catalogue: every registered adapter, what stands behind it, and whether this
 * codebase calls it.
 *
 * Extracted from `features/settings/integrations-catalogue-panel.tsx` at the second use rather
 * than the third — `CLAUDE.md` puts the boundary there because the third is where the two copies
 * have already drifted, and a drifted `state` vocabulary would be two screens disagreeing about
 * what "staged" means.
 *
 * **The three states are a classification, not a funnel.** *watched* means the index found a call
 * site binding this repository to the vendor; *staged* means an adapter has a cached spec and no
 * call site was found; *available* means an adapter is registered and neither has happened. A
 * vendor can sit at *available* forever without anything being wrong — whether it is watched is a
 * fact about the customer's code, not about how far Sync has got.
 */

import {
  ApiStatusError,
  MalformedResponseError,
  UnreachableApiError,
} from "@/api/errors"

export interface CatalogueRow {
  vendor_id: string
  tier: string
  source: string | null
  sdk_bindings: Record<string, Record<string, string>>
  staged: { tag: string | null; symbols: number | null; baked_at?: string } | null
  call_sites: number
  changes_recorded: number
  state: "watched" | "staged" | "available"
}

export interface Catalogue {
  repo_id: string | null
  integrations: CatalogueRow[]
  by_tier: Record<string, number>
  by_state: Record<string, number>
  total: number
}

export async function fetchCatalogue(
  repoId: string | null,
  signal?: AbortSignal,
): Promise<Catalogue> {
  const path =
    repoId === null
      ? "/api/integrations"
      : `/api/integrations?repo_id=${encodeURIComponent(repoId)}`
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (!response.ok) throw new ApiStatusError(response.status, path)
  try {
    return (await response.json()) as Catalogue
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}
