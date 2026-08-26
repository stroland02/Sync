/**
 * A list with its selected row's detail beside it, rather than over it.
 *
 * **M15 Task 2, and a correction of Task 1's own predecessor.** `CI-W514` shipped the call-site
 * detail as a modal `Sheet`, citing Nango's row → drawer convention. Nango's note does say drawer;
 * **Supabase's note says which drawer**, and the modal is the wrong one here:
 * `apps/design-system/.../modality.mdx` puts dialogs on short focused tasks and sheets on longer
 * forms, and their own list-detail (`UserPanel`) is not modal at all. It is a panel beside the
 * list, so the list stays readable and a reader moves down rows without closing anything.
 *
 * That difference is the whole point on a table: a modal over 165 call sites means open, read,
 * close, find your place, open the next. Beside them, the next row is one arrow key away.
 *
 * ## What the URL carries, and why push rather than replace
 *
 * The selected row is a search parameter, and writing it is a **history push** so **Back closes
 * the panel** rather than leaving the screen. That is the browser control every reader already
 * knows, and a panel that ignored it would train them to distrust Back on the rest of the console.
 *
 * The parameter is **absent** when nothing is selected rather than present and empty, so a screen
 * with no selection has one canonical URL — Supabase's `clearOnDefault`, which is the same rule
 * `use-filter-param.ts` already applies to facets.
 *
 * ## What this deliberately does not do
 *
 * **No focus trap and no inert background.** Those are modal behaviours, and this is not modal:
 * the list behind it is not background, it is the thing the reader is working through.
 */

import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/vendor/supabase/ui/sheet"
import { useCallback, useEffect } from "react"
import { X } from "lucide-react"
import { useSearchParams } from "react-router"

import type { ReactNode } from "react"

/**
 * The selected row, in the URL, written as a history entry.
 *
 * Separate from `useFilterParam` because the two want opposite history behaviour: narrowing a
 * table is a refinement a reader does not expect Back to undo one step at a time, while opening a
 * detail is a place they expect Back to leave.
 */
export function useSelectionParam(
  key: string,
): [string | null, (next: string | null) => void] {
  const [searchParams, setSearchParams] = useSearchParams()
  const raw = searchParams.get(key)
  const selected = raw === null || raw === "" ? null : raw

  const setSelected = useCallback(
    (next: string | null) => {
      setSearchParams(
        (prev) => {
          const updated = new URLSearchParams(prev)
          if (next === null || next === "") updated.delete(key)
          else updated.set(key, next)
          return updated
        },
        // Push, so Back closes the panel. Closing it writes another entry rather than popping,
        // which is what keeps Back predictable in both directions.
        { replace: false },
      )
    },
    [key, setSearchParams],
  )

  return [selected, setSelected]
}

/**
 * Move the selection with the arrow keys while the panel is open.
 *
 * Bound at the document because the reader's focus is wherever they left it — usually the row
 * they clicked — and a handler on the panel would only fire while the panel itself had focus,
 * which is precisely when they are not looking at the list.
 */
export function useSelectionKeys(
  ids: readonly string[],
  selected: string | null,
  onSelect: (next: string | null) => void,
): void {
  useEffect(() => {
    if (selected === null) return
    function onKey(event: KeyboardEvent) {
      // Never steal a key from somebody typing. A filter input is one tab away.
      const target = event.target as HTMLElement | null
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return
      if (event.key === "Escape") {
        onSelect(null)
        return
      }
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return
      const at = ids.indexOf(selected!)
      if (at === -1) return
      const next = event.key === "ArrowDown" ? at + 1 : at - 1
      // Stop at the ends rather than wrapping: a list that wraps silently sends a reader who
      // held the key back to the top believing they are still descending.
      if (next < 0 || next >= ids.length) return
      event.preventDefault()
      onSelect(ids[next])
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [ids, selected, onSelect])
}

/**
 * The control that closes a detail, wherever that detail is docked.
 *
 * Extracted at its second use: the graph's canvas dock cannot compose `DetailLayout` itself, whose
 * aside caps its height against a scrolling chassis a locked screen does not have. What it does
 * need is the same affordance under the same accessible name, so a reader who learned it on the
 * call-sites table finds it unchanged on the map.
 */
export function DetailClose({ onClose }: { onClose: () => void }) {
  return (
    <button
      type="button"
      onClick={onClose}
      aria-label="Close detail"
      className="shrink-0 rounded-control p-field text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink focus:outline-none focus:ring-1 focus:ring-ring"
    >
      <X aria-hidden="true" className="size-4" />
    </button>
  )
}

export function DetailLayout({
  list,
  detail,
  title,
  onClose,
  docked = false,
  subtitle,
}: {
  list: ReactNode
  /** `null` closes the panel and gives the list the whole width — undocked only. */
  detail: ReactNode | null
  title: string
  onClose: () => void
  /**
   * Drawer: the detail slides over the page from the right rather than taking a column from it.
   * Owner ruling 2026-08-25, after the docked column squeezed the table until file paths wrapped
   * one word per line. A reader working down a table wants the table at full width and the
   * detail on top of it, not a permanently narrowed list.
   */
  docked?: boolean
  /** One line under the title — the address, the id. Docked mode only. */
  subtitle?: ReactNode
}) {
  return (
    <div
      className={
        docked
          ? "flex min-h-0 min-w-0 flex-1 flex-col"
          : detail === null
            ? "min-w-0"
            : "grid min-w-0 gap-section xl:grid-cols-[minmax(0,1fr)_minmax(0,32rem)] xl:items-start"
      }
    >
      {/* Docked lives inside a locked screen, so the list scrolls itself. Without this the
          table grows to its content -- measured at 1601px inside a 925px pane -- and inflates
          the screen it was supposed to be bounded by. */}
      <div
        className={
          docked ? "flex min-h-0 min-w-0 flex-1 flex-col overflow-auto" : "min-w-0"
        }
      >
        {list}
      </div>
      {docked ? (
        <Sheet open={detail !== null} onOpenChange={(open) => { if (!open) onClose() }}>
          <SheetContent
            side="right"
            className="flex w-full flex-col gap-0 border-l border-line bg-surface p-0 sm:max-w-[42rem]"
          >
            <SheetHeader className="shrink-0 border-b border-line px-section py-row text-left">
              <SheetTitle className="min-w-0 break-all text-section">{title}</SheetTitle>
              {subtitle !== undefined && (
                <SheetDescription className="min-w-0 truncate font-mono text-meta text-ink-muted">
                  {subtitle}
                </SheetDescription>
              )}
            </SheetHeader>
            <div className="min-h-0 flex-1 overflow-auto px-section py-section">{detail}</div>
          </SheetContent>
        </Sheet>
      ) : (
        detail !== null && (
          <aside
            aria-label={title}
            // Sticky within its own column: the list is long, and a detail that scrolls away
            // while the reader is still in the list is a panel they scroll back up to read.
            className="flex min-w-0 flex-col gap-row rounded-surface border border-line bg-surface p-section xl:sticky xl:top-frame xl:max-h-[calc(100svh-8rem)] xl:overflow-y-auto"
          >
            <div className="flex items-start justify-between gap-row border-b border-line pb-row">
              <h2 className="min-w-0 break-all text-section">{title}</h2>
              <DetailClose onClose={onClose} />
            </div>
            {detail}
          </aside>
        )
      )}
    </div>
  )
}
