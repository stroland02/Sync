/**
 * The top bar's stats slot — the page's instrument panel, moved into the chrome.
 *
 * Owner ruling, 2026-08-25: the KPI bars every page opened with live in the top bar now, on
 * every page, and the workspace identity that used to occupy that corner is gone — switching
 * codebases is Settings work, not chrome work. The mechanism mirrors the status band's portal:
 * the chassis owns a slot, publishers render into it through context, and a publisher rendered
 * outside the chassis (a bare unit test, a screen on its own) falls back to its in-page form
 * rather than losing the facts.
 *
 * Held in state behind a callback ref for the reason `screen-frame.tsx` gives: a plain ref is
 * `null` on the first render and the slot would never mount.
 */

import { createContext, useContext, useState, type ReactNode } from "react"

const TopbarStatsTargetContext = createContext<HTMLElement | null>(null)

/** The slot element, or `null` where no chassis is mounted — publishers fall back inline. */
export function useTopbarStatsTarget(): HTMLElement | null {
  return useContext(TopbarStatsTargetContext)
}

export function TopbarStatsProvider({
  target,
  children,
}: {
  target: HTMLElement | null
  children: ReactNode
}) {
  return (
    <TopbarStatsTargetContext.Provider value={target}>
      {children}
    </TopbarStatsTargetContext.Provider>
  )
}

/** One measured figure in the bar: furniture label, mono value, the note one hover away. */
export function TopbarStat({
  label,
  value,
  note,
}: {
  label: string
  value: ReactNode
  note?: string
}) {
  // One instrument cell: the bar divides its full width evenly and every cell centers its
  // label over its value -- the owner's 2026-08-25 form. `min-w-0` + truncate so a long value
  // (a path, a date) shortens inside its cell instead of pushing the others off the bar.
  return (
    <span
      title={note}
      className="flex h-full min-w-0 flex-1 flex-col items-center justify-center px-row text-center"
    >
      <span className="truncate font-furniture text-ink-secondary">{label}</span>
      <span className="min-w-0 max-w-full truncate font-mono text-body font-medium text-ink">
        {value}
      </span>
    </span>
  )
}

/** Mounted once in the chassis header. Everything published lands here, in mount order. */
export function TopbarStatsSlot({ onTarget }: { onTarget: (el: HTMLElement | null) => void }) {
  return (
    <div
      ref={onTarget}
      data-topbar-stats
      className="flex h-12 shrink-0 items-stretch divide-x divide-line overflow-hidden border-b border-line bg-secondary empty:hidden"
    />
  )
}

export function useTopbarStatsState() {
  return useState<HTMLElement | null>(null)
}
