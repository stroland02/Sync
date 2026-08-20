/**
 * The connected codebases, switchable from the environment badge.
 *
 * **Owner report, 2026-08-19: switching workspaces did not work.** The diagnosis is narrower and
 * worse than "stale data" â€” *there was no switcher at all*. `useChassisIdentity` reads the
 * workspace from the route and falls back to the sole repository only when there is exactly one,
 * so the moment a second codebase was indexed the fallback stopped applying and the only way to
 * change workspace was to hand-edit the address bar. The badge beside it was a link into Settings.
 *
 * ## What switching has to preserve
 *
 * **The screen, not just the workspace.** A reader looking at Call sites for one codebase wants
 * Call sites for the other, not the Overview. So the current path is rebuilt with the new
 * workspace substituted, using the registry's own matcher rather than a string replace â€” a
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

export function WorkspaceSwitcher({
  current,
  children,
}: {
  current: string | null
  /** The badge's own text, which becomes the trigger's label. */
  children: React.ReactNode
}) {
  const repositories = useRepositories()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const repoIds = repositories.data?.repo_ids ?? []

  // With one workspace there is nowhere to go, so the badge stays plain text rather than a
  // control that opens onto a single option -- which reads as broken.
  if (repoIds.length < 2) {
    return <span className="flex min-w-0 items-center gap-row">{children}</span>
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        {/* The whole badge, not a chevron beside it. It used to be a `Link` into Settings with
            the trigger alongside, so pressing the text a reader thought was the switcher
            navigated them away -- the owner's report of 2026-08-19. */}
        <button
          type="button"
          aria-label="Switch codebase"
          className="flex min-w-0 items-center gap-row rounded-control px-field text-meta text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink focus:outline-none focus:ring-1 focus:ring-ring"
        >
          {children}
          <ChevronsUpDown aria-hidden="true" className="size-3.5 shrink-0" />
        </button>
      </DropdownMenuTrigger>
      {/* `sideOffset` clears the top bar's own border, and the alignment offset pulls the panel
          back under the badge rather than off the right edge of the window. */}
      <DropdownMenuContent
        align="end"
        alignOffset={-8}
        sideOffset={10}
        className="min-w-[20rem]"
      >
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
