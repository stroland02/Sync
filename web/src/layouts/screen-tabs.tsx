/**
 * The sibling-screen strip in the identity band.
 *
 * Chassis-owned rather than per-screen: six screens each declared their own copy of a strip that
 * names *the other screens*, so a route rename had six edit sites and any one of them could be
 * missed. The group a route belongs to is a fact about the registry, and it is read from there.
 *
 * Links, deliberately not the vendored `Tabs`: that component owns selection state and renders
 * every panel's subtree, which here would mount several data-fetching screens to show one. Which
 * tab is current is a fact of the URL rather than state that dies on navigation, and a reader can
 * send someone the tab they are looking at.
 */

import { Link, useLocation } from "react-router"

import { scopeFromLocation } from "@/layouts/scope-switchers"
import { chipSurface } from "@/lib/selectable-surface"

interface SiblingGroup {
  readonly label: string
  readonly members: readonly { readonly label: string; readonly path: string }[]
}

/**
 * Paths are the registry's own, parameterised. `screen-tabs.test.tsx` holds every one against
 * `ROUTES`, so a group naming an address no route declares fails rather than rendering a dead tab.
 */
export const SIBLING_GROUPS: readonly SiblingGroup[] = [
  {
    label: "Findings",
    members: [
      { label: "Findings", path: "/repositories/:repoId/findings" },
      { label: "Trends", path: "/repositories/:repoId/metrics" },
    ],
  },
  {
    label: "Solutions",
    members: [
      { label: "Solutions", path: "/repositories/:repoId/solutions" },
      { label: "Corpus", path: "/repositories/:repoId/precedent" },
    ],
  },
  {
    label: "Vendors",
    members: [
      { label: "Vendors", path: "/repositories/:repoId/vendors" },
      { label: "Changes", path: "/repositories/:repoId/integration-changes" },
    ],
  },
]

function href(path: string, repoId: string): string {
  return path.replace(":repoId", encodeURIComponent(repoId))
}

/**
 * The group whose member the address IS, never one it merely starts with: `/findings/:findingId`
 * is a detail screen under Findings and not a third tab beside it.
 */
export function groupFor(pathname: string, repoId: string | null): SiblingGroup | null {
  if (repoId === null) return null
  return (
    SIBLING_GROUPS.find((group) =>
      group.members.some((member) => href(member.path, repoId) === pathname)
    ) ?? null
  )
}

export function ScreenTabs() {
  const { pathname, search } = useLocation()
  const { repoId } = scopeFromLocation(pathname, search)
  const group = groupFor(pathname, repoId)
  if (group === null || repoId === null) return null

  return (
    <nav aria-label={`${group.label} screens`} className="flex shrink-0 items-center gap-field">
      {group.members.map((member) => {
        const to = href(member.path, repoId)
        const current = to === pathname
        return (
          <Link
            key={member.path}
            to={to}
            aria-current={current ? "page" : undefined}
            className={`rounded-control border px-row py-field text-body ${chipSurface(current)}`}
          >
            {member.label}
          </Link>
        )
      })}
    </nav>
  )
}
