import { QueryClient } from "@tanstack/react-query"

import { ApiStatusError, NotFoundError } from "@/api/errors"

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

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: shouldRetry,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
})
