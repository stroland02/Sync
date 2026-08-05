/**
 * Which caught errors belong on the central failure surface.
 *
 * `NotFoundError` is the graph telling the truth about a closed finding or an unstarted
 * run — `states.tsx` already renders that as an answer, not a failure, and this function
 * exists so nothing else re-litigates the same judgement on the same error type.
 */

import {
  ApiStatusError,
  MalformedResponseError,
  NotFoundError,
  UnreachableApiError,
} from "@/api/errors"
import type { FailureInput } from "@/lib/error-log"

/** `null` means the error is an expected answer, not a failure — report nothing. */
export function describeFailure(error: unknown): FailureInput | null {
  if (error instanceof NotFoundError) return null

  if (error instanceof UnreachableApiError) {
    return { summary: "The API is unreachable.", path: error.path, detail: error.message }
  }
  if (error instanceof ApiStatusError) {
    return {
      summary: `The API answered with HTTP ${error.status}.`,
      path: error.path,
      status: error.status,
      detail: error.message,
    }
  }
  if (error instanceof MalformedResponseError) {
    return {
      summary: "The API answered with a body that is not JSON.",
      path: error.path,
      detail: error.message,
    }
  }
  if (error instanceof Error) {
    return { summary: "An unexpected error occurred.", detail: error.stack ?? error.message }
  }
  return { summary: "An unexpected value was thrown.", detail: String(error) }
}
