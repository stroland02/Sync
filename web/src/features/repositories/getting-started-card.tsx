/**
 * Getting started, first on the Overview â€” the owner's direction 2026-08-18.
 *
 * The first thing a new operator meets is the setup information: which codebase this console
 * is working with, and the six prerequisites of the full loop with each one's probed state.
 * The checklist is `/api/setup`'s answer rendered compactly â€” the long form with the inline
 * editors stays in Settings â†’ Setup, which the first button reaches â€” so this card is the
 * doorway, never a second place to configure a thing.
 *
 * It stays when everything is ready rather than vanishing: a region that disappears once
 * setup completes teaches an operator the page is unpredictable, and "everything the loop
 * needs is in place" is worth one compact row of words. No figure over the items, as
 * everywhere: ready, missing and unanswered are three facts nothing here sums.
 */

import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router"

import { InfoHint } from "@/components/info-hint"
import { ErrorState, LoadingState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { fetchSetup, type SetupItem } from "@/features/settings/api"

function StateWord({ state }: { state: SetupItem["state"] }) {
  const wording: Record<SetupItem["state"], string> = {
    ready: "ready",
    missing: "missing",
    unanswered: "not answered",
  }
  return (
    <span className="furniture shrink-0 rounded-control border border-line px-field py-field text-meta text-ink-muted">
      {wording[state]}
    </span>
  )
}

export function GettingStartedCard({ repoId }: { repoId: string }) {
  const query = useQuery({
    queryKey: ["setup", repoId],
    queryFn: ({ signal }) => fetchSetup(repoId, signal),
  })

  return (
    <div className="flex flex-col gap-section rounded-surface border border-line bg-surface p-section">
      <div className="flex flex-wrap items-center justify-between gap-section">
        <div className="flex min-w-0 flex-col gap-field">
          <div className="flex items-center gap-row">
            <h2 className="text-section">Getting started</h2>
            <InfoHint label="About getting started">
              Sync is installed beside a codebase and indexes it into the graph; every figure on
              every screen is scoped to the workspace named here. The items on the right are the
              full loop&rsquo;s prerequisites â€” index, detect, remediate, verify, pull request â€”
              each probed when this page loads. Fixing any of them happens in Settings, never
              here, so there is one place for a setting and one answer to what it holds.
            </InfoHint>
          </div>
          <span className="truncate font-mono text-body text-ink" title={repoId}>
            {repoId}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-row">
          <Button asChild variant="outline" size="sm">
            <Link to="/settings">Setup checklist</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link to="/settings">Connect to Git</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link to="/settings">How these pages work</Link>
          </Button>
        </div>
      </div>

      {query.isPending && <LoadingState what="the setup checklist" />}
      {query.isError && (
        <ErrorState
          error={query.error}
          what="the setup checklist"
          onRetry={() => void query.refetch()}
        />
      )}
      {query.isSuccess && (
        <div className="grid auto-rows-fr gap-row border-t border-line pt-section sm:grid-cols-2 xl:grid-cols-3">
          {query.data.items.map((item) => (
            <div key={item.id} className="flex min-w-0 flex-col gap-field">
              <div className="flex flex-wrap items-center gap-row">
                <span className="text-body text-ink">{item.label}</span>
                <StateWord state={item.state} />
              </div>
              {item.state !== "ready" && item.fix !== null && (
                <span className="font-mono text-meta text-ink-muted">{item.fix}</span>
              )}
            </div>
          ))}
        </div>
      )}
      {query.isSuccess && query.data.items.every((item) => item.state === "ready") && (
        <p className="max-w-prose text-meta text-ink-muted">
          Everything the full loop needs is in place â€” indexed, staged, connected, and a merge
          policy in force.
        </p>
      )}
    </div>
  )
}
