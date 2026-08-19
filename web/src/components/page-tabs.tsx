/**
 * Link-tabs across the top of a destination that holds more than one screen.
 *
 * The owner's consolidation of 2026-08-18: ten rail entries became seven, with the screens
 * that answer one kind of question grouped under one destination. Each tab is a real route
 * with its own address — a reader can share the tab they are looking at, and which one is
 * active is a fact of the URL rather than component state that dies on navigation.
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

/** The tabs under Logs: event streams, one row per occurrence. */
export function logsTabs(repoId: string): PageTab[] {
  const encoded = encodeURIComponent(repoId)
  return [
    { label: "Runs", to: `/repositories/${encoded}/runs` },
    { label: "Signals", to: `/repositories/${encoded}/observed` },
  ]
}

/** The tabs under Metrics: measured state and the aggregates over it. */
export function metricsTabs(repoId: string): PageTab[] {
  const encoded = encodeURIComponent(repoId)
  return [
    { label: "Findings", to: `/repositories/${encoded}/findings` },
    { label: "Detectors", to: `/repositories/${encoded}/detectors` },
    { label: "Trends", to: `/repositories/${encoded}/metrics` },
  ]
}

/** The tabs under Integrations: what this codebase uses, and what those vendors published. */
export function integrationsTabs(repoId: string): PageTab[] {
  const encoded = encodeURIComponent(repoId)
  return [
    { label: "Integrations", to: `/repositories/${encoded}/vendors` },
    { label: "Changes", to: `/repositories/${encoded}/integration-changes` },
  ]
}
