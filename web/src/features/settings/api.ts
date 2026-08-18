/**
 * Settings API integration for repository automation and context.
 *
 * Scoped within features/settings to avoid modifying shared api/client.ts.
 */

import { ApiStatusError, MalformedResponseError, NotFoundError, UnreachableApiError } from "@/api/errors"

export interface RepoSettingsPayload {
  repo_id: string
  merge_policy: "never" | "when_checks_pass"
  merge_method: "squash" | "merge" | "rebase"
  base_branch: string
  /** The git remote the full loop addresses, or null when never configured. */
  remote_url: string | null
  refusal_reasons?: Record<string, string>
}

export interface UpdateRepoSettingsParams {
  merge_policy?: "never" | "when_checks_pass" | "immediate"
  merge_method?: "squash" | "merge" | "rebase"
  base_branch?: string
  /** Empty string clears the stored remote; absent leaves it untouched. */
  remote_url?: string
}

/** One prerequisite of the full loop, probed by the API at request time. */
export interface SetupItem {
  id: string
  label: string
  /** Probed states, never summed: ready / missing / unanswered are three different facts. */
  state: "ready" | "missing" | "unanswered"
  detail: string
  fix: string | null
}

export interface SetupResponse {
  repo_id: string | null
  items: SetupItem[]
}

export async function fetchSetup(
  repoId: string | null,
  signal?: AbortSignal,
): Promise<SetupResponse> {
  const path =
    repoId === null ? "/api/setup" : `/api/setup?repo_id=${encodeURIComponent(repoId)}`
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (!response.ok) {
    throw new ApiStatusError(response.status, path)
  }
  try {
    return (await response.json()) as SetupResponse
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}

export interface RepoContextPayload {
  repo_id: string
  context: string | null
  source: string
}

export async function fetchRepoSettings(
  repoId: string,
  signal?: AbortSignal,
): Promise<RepoSettingsPayload> {
  const path = `/api/repositories/${encodeURIComponent(repoId)}/settings`
  let response: Response
  try {
    response = await fetch(path, {
      headers: { Accept: "application/json" },
      signal,
    })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }

  if (response.status === 404) {
    throw new NotFoundError(`no repository ${repoId}`, repoId, path)
  }
  if (!response.ok) {
    throw new ApiStatusError(response.status, path)
  }

  try {
    return (await response.json()) as RepoSettingsPayload
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}

export async function updateRepoSettings(
  repoId: string,
  params: UpdateRepoSettingsParams,
  signal?: AbortSignal,
): Promise<RepoSettingsPayload> {
  const path = `/api/repositories/${encodeURIComponent(repoId)}/settings`
  let response: Response
  try {
    response = await fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(params),
      signal,
    })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }

  if (!response.ok) {
    throw new ApiStatusError(response.status, path)
  }

  try {
    return (await response.json()) as RepoSettingsPayload
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}
