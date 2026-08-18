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
  refusal_reasons?: Record<string, string>
}

export interface UpdateRepoSettingsParams {
  merge_policy?: "never" | "when_checks_pass" | "immediate"
  merge_method?: "squash" | "merge" | "rebase"
  base_branch?: string
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
    throw new UnreachableApiError(path, cause)
  }

  if (response.status === 404) {
    throw new NotFoundError(path, { error: "not_found", resource: "repository", identifier: repoId })
  }
  if (!response.ok) {
    throw new ApiStatusError(path, response.status, await response.text())
  }

  try {
    return (await response.json()) as RepoSettingsPayload
  } catch (cause) {
    throw new MalformedResponseError(path, cause)
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
    throw new UnreachableApiError(path, cause)
  }

  if (!response.ok) {
    const errorBody = await response.text()
    throw new ApiStatusError(path, response.status, errorBody)
  }

  try {
    return (await response.json()) as RepoSettingsPayload
  } catch (cause) {
    throw new MalformedResponseError(path, cause)
  }
}
