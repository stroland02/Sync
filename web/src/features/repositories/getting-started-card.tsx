/**
 * Getting started — the first thing on the Overview, rebuilt as a stepper on the owner's
 * 2026-08-25 ruling: icons over sentences, one action, the next unmet prerequisite expanded.
 *
 * The card is `/api/setup`'s answer rendered as progress: every prerequisite is a chip whose
 * icon and word carry its probed state, and the first one that is not ready gets the wide row
 * with its fix line and the one button. Configuration still happens in Settings only — this is
 * the doorway, never a second place to hold a setting.
 *
 * "N of M ready" supersedes the earlier no-figure-over-the-items note deliberately (owner
 * ruling, same date): it is a measured count of probed answers, not a composite — and the three
 * states stay three, because `unanswered` rendering as `missing` would claim a probe that never
 * ran. It stays when everything is ready rather than vanishing: a region that disappears once
 * setup completes teaches an operator the page is unpredictable.
 */

import { useQuery } from "@tanstack/react-query"
import { CircleCheck, CircleDashed, TriangleAlert, Zap } from "lucide-react"
import { Link } from "react-router"

import { ErrorState, LoadingState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { fetchSetup, type SetupItem } from "@/features/settings/api"
import { cn } from "@/lib/utils"

const STATE = {
  ready: { icon: CircleCheck, ink: "text-good-ink", word: "ready" },
  missing: { icon: TriangleAlert, ink: "text-warning-ink", word: "missing" },
  unanswered: { icon: CircleDashed, ink: "text-ink-muted", word: "not answered" },
} as const

function StepChip({ item }: { item: SetupItem }) {
  const { icon: Icon, ink } = STATE[item.state]
  return (
    <Link
      to="/settings"
      title={`${item.label} — ${STATE[item.state].word}`}
      className="flex items-center gap-field rounded-control border border-line px-row py-field text-meta text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink focus:outline-none focus:ring-1 focus:ring-ring"
    >
      <Icon aria-hidden="true" className={cn("size-4 shrink-0", ink)} />
      {item.label}
    </Link>
  )
}

export function GettingStartedCard({ repoId }: { repoId: string }) {
  const query = useQuery({
    queryKey: ["setup", repoId],
    queryFn: ({ signal }) => fetchSetup(repoId, signal),
  })

  const items = query.isSuccess ? query.data.items : []
  const ready = items.filter((item) => item.state === "ready").length
  const next = items.find((item) => item.state !== "ready") ?? null

  return (
    <div className="flex flex-col gap-section rounded-surface border border-line bg-surface p-section">
      <div className="flex flex-wrap items-center justify-between gap-section">
        <div className="flex min-w-0 items-center gap-row">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-control bg-primary/15">
            <Zap aria-hidden="true" className="size-4 text-primary" />
          </span>
          <div className="flex min-w-0 flex-col">
            <h2 className="text-section">Getting started</h2>
            <span className="truncate font-mono text-meta text-ink-muted" title={repoId}>
              {repoId}
            </span>
          </div>
        </div>
        {query.isSuccess && (
          <div className="flex shrink-0 items-center gap-row">
            <span className="font-furniture text-ink-secondary">
              {ready} / {items.length} ready
            </span>
            <span
              role="img"
              aria-label={`${ready} of ${items.length} prerequisites ready`}
              className="h-1 w-24 overflow-hidden rounded-full bg-surface-emphasis"
            >
              <span
                className="block h-full rounded-full bg-primary"
                style={{ width: items.length === 0 ? 0 : `${(ready / items.length) * 100}%` }}
              />
            </span>
          </div>
        )}
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
        <div className="flex flex-wrap items-center gap-row">
          {items.map((item) => (
            <StepChip key={item.id} item={item} />
          ))}
        </div>
      )}

      {query.isSuccess && next !== null && (
        <div className="flex flex-wrap items-center justify-between gap-section rounded-control border border-line bg-surface-subtle px-section py-row">
          <div className="flex min-w-0 items-center gap-row">
            <TriangleAlert
              aria-hidden="true"
              className={cn("size-4 shrink-0", STATE[next.state].ink)}
            />
            <div className="flex min-w-0 flex-col">
              <span className="text-body text-ink">
                {next.label} — {STATE[next.state].word}
              </span>
              {next.fix !== null && (
                <span className="truncate font-mono text-meta text-ink-muted">{next.fix}</span>
              )}
            </div>
          </div>
          <Button asChild size="sm">
            <Link to="/settings">Fix in Settings →</Link>
          </Button>
        </div>
      )}

      {query.isSuccess && next === null && items.length > 0 && (
        <div className="flex items-center gap-row text-meta text-ink-muted">
          <CircleCheck aria-hidden="true" className="size-4 shrink-0 text-good-ink" />
          Everything the full loop needs is in place — indexed, staged, connected, and a merge
          policy in force.
        </div>
      )}
    </div>
  )
}
