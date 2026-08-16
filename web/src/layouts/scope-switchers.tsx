/**
 * Which subject you are inside, said once, at the top, on every route.
 *
 * The console has nine levels in one hierarchy and, until this landed, no persistent statement of
 * where an operator was standing. A breadcrumb existed, but it rendered *inside* the page header,
 * inside the scrolling column, and on three routes inside a 360px column — so it left the screen on
 * the first scroll. `reports/2026-08-07-console-fidelity-gaps.md` Surface 1 measures that:
 * `[role=banner]` counted zero on every route.
 *
 * **The trail is derived from the address and holds no state of its own.** That is the rail's rule
 * applied one tier up, and it exists so no pick can survive a navigation: a bar that remembered a
 * repository would eventually name one while another repository's screen rendered beneath it, which
 * is the one disagreement a chassis must not have.
 *
 * **The value comes from the URL; the options come from a query, and the split is deliberate.** The
 * vendor list is *vendors with an open finding*, so a vendor with none is a real address the list
 * cannot see. Drawing the trail from the list would blank the bar on exactly that screen. It also
 * means a switcher never waits on a fetch to say where you are.
 *
 * **The trail stops at the vendor.** A finding's vendor is in the payload, not in the address, so
 * carrying the trail deeper would mean this bar issuing a query per route to restate an answer the
 * page below it already has. `layouts/breadcrumbs.tsx` keeps the full in-page path, including its
 * own root: a breadcrumb that started mid-hierarchy would no longer be one, and the scope trail and
 * the breadcrumb are two derivations with two jobs rather than one fact written twice.
 *
 * **Fleet is a link and not a switcher.** There is one fleet. A chevron opening a popover with a
 * single entry is the invented furniture the gap report refused on the right-hand side of this same
 * bar, and refusing it here costs nothing: the fleet's address is one click either way.
 */

import { useState } from "react"
import { ChevronsUpDown, Radar } from "lucide-react"
import { Link, matchPath, useLocation, useNavigate } from "react-router"

import { useOverview, useRepositories } from "@/api/queries"
import { Skeleton } from "@/components/skeleton"
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { ErrorState } from "@/components/states"
import { ROUTES } from "@/lib/routes"
import { cn } from "@/lib/utils"
import { Popover, PopoverContent, PopoverTrigger } from "@/vendor/supabase/ui/popover"

/**
 * The routes whose own screen reads `?repo_id=` as its scope, so switching a repository there
 * rewrites the scope instead of navigating away from the level.
 *
 * Declared rather than derived: nothing in the registry records that a screen accepts a scope, and
 * inferring it from a URL that happens to carry the key already would make the control behave
 * differently depending on how the operator arrived. `scope-switchers.test.tsx` asserts every entry
 * is still a path the registry declares, which is the drift that would otherwise be silent.
 */
export const REPO_SCOPED_PATHS: readonly string[] = [
  "/vendors/:vendorId",
  "/detectors",
  "/bindings/vendors/:vendorId/operations/:operationId",
]

/** The `repo_id` key three screens already carry a repository scope in. */
const REPO_KEY = "repo_id"

export interface Scope {
  repoId: string | null
  vendorId: string | null
}

interface Matched {
  path: string
  params: Record<string, string | undefined>
}

/**
 * The declared route an address is on, or null at an address no route declares.
 *
 * `matchPath` matches to the end, so `/findings/:findingId` cannot claim the workflow nested under
 * it and two routes can never both answer.
 */
function matchedRoute(pathname: string): Matched | null {
  for (const route of ROUTES) {
    const match = matchPath(route.path, pathname)
    if (match !== null) return { path: route.path, params: match.params }
  }
  return null
}

/** Substitutes a route's dynamic segments, encoding each: a repository id may hold a slash. */
function fillPath(path: string, params: Record<string, string | undefined>): string {
  return path.replace(/:([A-Za-z]+)/g, (_, name: string) =>
    encodeURIComponent(params[name] ?? "")
  )
}

/**
 * The repository and vendor an address is inside.
 *
 * A path parameter wins over the search key, because a repository in the path is the screen's
 * subject and one in the query string is a scope over somebody else's subject.
 */
export function scopeFromLocation(pathname: string, search: string): Scope {
  const matched = matchedRoute(pathname)
  const scoped = new URLSearchParams(search).get(REPO_KEY)
  return {
    repoId: matched?.params.repoId ?? scoped,
    vendorId: matched?.params.vendorId ?? null,
  }
}

/**
 * Where picking a repository goes.
 *
 * Three cases, in order. The address already names a repository as its subject, so the level is
 * kept and the subject swapped. The screen takes a repository *scope*, so the scope is rewritten
 * and the operator stays where they are — this is the switcher changing scope in place rather than
 * navigating. Neither, so the repository's own screen is the honest destination.
 */
export function repositoryHref(repoId: string, pathname: string, search: string): string {
  const matched = matchedRoute(pathname)
  if (matched !== null && "repoId" in matched.params) {
    return fillPath(matched.path, { ...matched.params, repoId })
  }
  if (matched !== null && REPO_SCOPED_PATHS.includes(matched.path)) {
    const params = new URLSearchParams(search)
    params.set(REPO_KEY, repoId)
    return `${pathname}?${params.toString()}`
  }
  return `/repositories/${encodeURIComponent(repoId)}`
}

/**
 * Where picking a vendor goes, carrying the repository scope with it.
 *
 * Always the vendor's own screen. Substituting a vendor into a binding surface would keep an
 * operation id that belongs to the vendor being left, which resolves to a screen about nothing.
 */
export function vendorHref(vendorId: string, repoId: string | null): string {
  const path = `/vendors/${encodeURIComponent(vendorId)}`
  return repoId === null ? path : `${path}?${REPO_KEY}=${encodeURIComponent(repoId)}`
}

/** A path divider, and nothing a screen reader should spell out. */
function Divider() {
  return (
    <span aria-hidden="true" className="text-ink-muted">
      /
    </span>
  )
}

const TRAIL_LINK =
  "max-w-40 truncate rounded-control px-field text-body text-foreground hover:bg-surface-subtle"

function Switcher({
  /** The level this control picks, capitalised: it names the control and its absence placeholder. */
  name,
  value,
  valueHref,
  options,
  pending,
  error,
  /** What the option list is counted over. A list that does not say its scope claims a wider one. */
  caption,
  /** What an empty list means. Absence is not zero, and a control is where that bites hardest. */
  absence,
  hrefFor,
  skeletonWidth,
}: {
  name: string
  value: string | null
  valueHref: string | null
  options: readonly string[]
  pending: boolean
  error: unknown
  caption: string
  absence: string
  hrefFor: (id: string) => string
  skeletonWidth: string
}) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const noun = name.toLowerCase()

  function pick(id: string) {
    setOpen(false)
    void navigate(hrefFor(id))
  }

  return (
    <span className="flex min-w-0 items-center gap-field">
      {value !== null && valueHref !== null ? (
        <Link to={valueHref} title={value} className={TRAIL_LINK}>
          {value}
        </Link>
      ) : pending ? (
        <Skeleton width={skeletonWidth} />
      ) : (
        <span className={cn(TRAIL_LINK, "text-ink-muted")}>{name}</span>
      )}

      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label={`Change ${noun}`}
            className="flex size-6 shrink-0 items-center justify-center rounded-control text-graphics hover:bg-surface-subtle hover:text-foreground"
          >
            <ChevronsUpDown aria-hidden="true" className="size-4" />
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-72 p-0">
          <p className="furniture border-b border-line px-row py-field text-meta text-ink-muted">
            {caption}
          </p>
          {error !== null && error !== undefined ? (
            <div className="p-row">
              <ErrorState error={error} what={`the ${noun} list`} />
            </div>
          ) : pending ? (
            <div className="p-row">
              <Skeleton width="w-full" />
            </div>
          ) : options.length === 0 ? (
            <p className="p-row text-body text-ink-muted">{absence}</p>
          ) : (
            <Command>
              <CommandInput placeholder={`Find a ${noun}…`} />
              <CommandList>
                <CommandEmpty>No {noun} on this list matches.</CommandEmpty>
                {options.map((id) => (
                  <CommandItem key={id} value={id} onSelect={() => pick(id)}>
                    <span className="truncate font-mono">{id}</span>
                  </CommandItem>
                ))}
              </CommandList>
            </Command>
          )}
        </PopoverContent>
      </Popover>
    </span>
  )
}

export function ScopeTrail() {
  const { pathname, search } = useLocation()
  const { repoId, vendorId } = scopeFromLocation(pathname, search)

  const repositories = useRepositories()
  const overview = useOverview()

  return (
    <nav aria-label="Scope" className="flex min-w-0 items-center gap-field">
      <Link
        to="/"
        aria-label="Fleet"
        className="flex shrink-0 items-center gap-field rounded-control px-field text-body text-foreground hover:bg-surface-subtle"
      >
        <Radar aria-hidden="true" className="size-4" />
        <span>Fleet</span>
      </Link>

      <Divider />

      <Switcher
        name="Repository"
        value={repoId}
        valueHref={repoId === null ? null : `/repositories/${encodeURIComponent(repoId)}`}
        options={repositories.data?.repo_ids ?? []}
        pending={repositories.isPending}
        error={repositories.error}
        caption="Every repository the index has seen a call site from"
        absence="The index has seen no repository. One that was configured but never indexed writes no call site, so it has no entry here either."
        hrefFor={(id) => repositoryHref(id, pathname, search)}
        skeletonWidth="w-28"
      />

      <Divider />

      <Switcher
        name="Vendor"
        value={vendorId}
        valueHref={vendorId === null ? null : vendorHref(vendorId, repoId)}
        options={overview.data?.vendors.map((vendor) => vendor.vendor_id) ?? []}
        pending={overview.isPending}
        error={overview.error}
        caption="Every vendor with an open finding"
        absence="No vendor has an open finding, so this list has nothing to switch to. A vendor with none is still reachable at its own address."
        hrefFor={(id) => vendorHref(id, repoId)}
        skeletonWidth="w-20"
      />
    </nav>
  )
}
