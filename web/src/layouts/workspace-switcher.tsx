/**
 * The connected codebases, switchable from the environment badge.
 *
 * **Owner report, 2026-08-19: switching workspaces did not work.** The diagnosis is narrower and
 * worse than "stale data" — *there was no switcher at all*. `useChassisIdentity` reads the
 * workspace from the route and falls back to the sole repository only when there is exactly one,
 * so the moment a second codebase was indexed the fallback stopped applying and the only way to
 * change workspace was to hand-edit the address bar. The badge beside it was a link into Settings.
 *
 * ## What switching has to preserve
 *
 * **The screen, not just the workspace.** A reader looking at Call sites for one codebase wants
 * Call sites for the other, not the Overview. So the current path is rebuilt with the new
 * workspace substituted, using the registry's own matcher rather than a string replace — a
 * `repoId` containing a slash is percent-encoded in the address, and naive substitution on the
 * encoded form breaks on the first repository named `host/owner/name`, which is all of them.
 *
 * **A route the new workspace cannot build falls back to its Overview.** Findings detail is
 * addressed by a finding id that belongs to one workspace; carrying it across would land on a
 * 404 that reads as a broken switcher rather than as a finding that is not there.
 *
 * **Every query re-reads, and that is React Query's doing rather than this component's.** Every
 * keyed read in `api/queries.ts` carries `repoId` in its key, so changing the route changes the
 * key and the data follows. That was already true; nothing was reaching it.
 */

import { Check, ChevronsUpDown } from "lucide-react"
import { useLocation, useNavigate } from "react-router"

import { useRepositories } from "@/api/queries"
import { ROUTES, boundParams, destinationHref } from "@/lib/routes"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/vendor/supabase/ui/dropdown-menu"

/**
 * The same screen under a different workspace, or that workspace's Overview.
 *
 * Exported for its own test: this is a derivation with a wrong answer, and
 * `console-dev-loop.md` puts those under test rather than under review.
 */
export function switchedPath(pathname: string, nextRepoId: string): string {
  const route = ROUTES.find((entry) => destinationHref(entry, boundParams(pathname)) === pathname)
  const bound = { ...boundParams(pathname), repoId: nextRepoId }
  if (route !== undefined) {
    const href = destinationHref(route, bound)
    // `destinationHref` returns null when a parameter is missing, which cannot happen here --
    // every parameter came from the current address and only `repoId` was replaced. A route
    // needing a finding or a vendor keeps the one it had, which is why the caller decides
    // whether that subject still exists in the new workspace.
    if (href !== null && route.params.every((name) => name === "repoId")) return href
  }
  return `/repositories/${encodeURIComponent(nextRepoId)}`
}

export function WorkspaceSwitcher({ current }: { current: string | null }) {
  const repositories = useRepositories()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const repoIds = repositories.data?.repo_ids ?? []

  // One workspace is not a choice, and a control that opens onto a single option reads as
  // broken. The badge renders its own text; this adds the affordance only when there is
  // somewhere to go.
  if (repoIds.length < 2) return null

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Switch codebase"
          className="inline-flex shrink-0 items-center rounded-control text-ink-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <ChevronsUpDown aria-hidden="true" className="size-3.5" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[18rem]">
        <DropdownMenuLabel className="furniture text-meta text-ink-muted">
          Connected codebases
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {repoIds.map((repoId) => (
          <DropdownMenuItem
            key={repoId}
            onSelect={() => navigate(switchedPath(pathname, repoId))}
            className="gap-row font-mono text-meta"
          >
            <Check
              aria-hidden="true"
              className={"size-3.5 shrink-0 " + (repoId === current ? "" : "invisible")}
            />
            <span className="min-w-0 break-all">{repoId}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
