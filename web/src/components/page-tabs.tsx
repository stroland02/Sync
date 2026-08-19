/**
 * Link-tabs across the top of a destination that holds more than one screen.
 *
 * The owner's consolidation of 2026-08-18, re-cut for the stage grouping of 2026-08-19: a tab
 * set holds the screens that answer one page's question, and a page whose stage earned it a
 * rail row of its own (Detectors, Telemetry) left the strip it was buried in. Each tab is a
 * real route with its own address — a reader can share the tab they are looking at, and which
 * one is active is a fact of the URL rather than component state that dies on navigation.
 *
 * Deliberately not the vendored `Tabs`: that component owns selection state and renders every
 * panel's subtree, which for these screens would mean four data-fetching pages mounted to show
 * one. These are links; the router mounts exactly the screen being read.
 */

import { Link, useLocation } from "react-router"

import { chipSurface } from "@/lib/selectable-surface"

export interface PageTab {
  readonly label: string
  readonly to: string
}

export function PageTabs({ label, tabs }: { label: string; tabs: readonly PageTab[] }) {
  const { pathname } = useLocation()
  return (
    <nav aria-label={label} className="flex flex-wrap items-center gap-row">
      {tabs.map((tab) => {
        const active = pathname === tab.to
        return (
          <Link
            key={tab.to}
            to={tab.to}
            aria-current={active ? "page" : undefined}
            className={`rounded-control border px-row py-field text-body ${chipSurface(active)}`}
          >
            {tab.label}
          </Link>
        )
      })}
    </nav>
  )
}

/** The tabs under Findings: the open findings, and the measured trends over them. */
export function findingsTabs(repoId: string): PageTab[] {
  const encoded = encodeURIComponent(repoId)
  return [
    { label: "Findings", to: `/repositories/${encoded}/findings` },
    { label: "Trends", to: `/repositories/${encoded}/metrics` },
  ]
}

/** The tabs under Solutions: what reached the forge, and the corpus those runs produced. */
export function solutionsTabs(repoId: string): PageTab[] {
  const encoded = encodeURIComponent(repoId)
  return [
    { label: "Solutions", to: `/repositories/${encoded}/solutions` },
    { label: "Corpus", to: `/repositories/${encoded}/corpus` },
  ]
}

/** The tabs under Vendors: what this codebase uses, and what those vendors published. */
export function vendorsTabs(repoId: string): PageTab[] {
  const encoded = encodeURIComponent(repoId)
  return [
    { label: "Vendors", to: `/repositories/${encoded}/vendors` },
    { label: "Changes", to: `/repositories/${encoded}/integration-changes` },
  ]
}
