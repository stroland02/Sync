import { QueryCache, QueryClient } from "@tanstack/react-query"

import { ApiStatusError, NotFoundError } from "@/api/errors"
import { describeFailure } from "@/lib/describe-failure"
import { reportError } from "@/lib/error-log"

/**
 * Retrying a 404 delays an answer the API already gave.
 *
 * "That finding is not open" and "your request was malformed" are settled the first time
 * they are said. Only a transport failure or a 5xx is worth asking again, and once is
 * enough — the operator is waiting on the screen that tells them the API is down.
 */
function shouldRetry(failureCount: number, error: Error): boolean {
  if (error instanceof NotFoundError) return false
  if (error instanceof ApiStatusError && error.status < 500) return false
  return failureCount < 1
}

/**
 * Every query failure passes through here, including a background poll's — the one case
 * an inline `isError` branch never sees, because nothing is re-rendering to show it.
 */
export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => {
      const failure = describeFailure(error)
      if (failure) reportError(failure)
    },
  }),
  defaultOptions: {
    queries: {
      retry: shouldRetry,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
})
