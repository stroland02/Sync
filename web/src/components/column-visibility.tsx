/**
 * Which columns a table shows, chosen by the reader and remembered.
 *
 * **M15 Task 1.** A wide screen makes room for columns; it does not decide which ones matter. The
 * call-sites payload carries fifteen recorded fields and no reader wants all fifteen at once —
 * one is auditing provenance, another is hunting loops, and the useful set differs per question.
 *
 * ## What this is careful about
 *
 * **A column cannot be hidden into a lie.** Some columns are the screen's claim rather than a
 * detail of it: the provenance rung is not hideable anywhere in this console, by a rule older than
 * this component (`console-surface.md`: *never a hideable column*). So a column declares whether
 * it may be hidden, and the control does not offer the ones that may not.
 *
 * **The last visible column cannot be hidden.** A table with no columns is not a preference, it
 * is a broken screen, and the reader who did it has no way back except clearing storage.
 *
 * **Choices are remembered per table, not globally.** A reader who hid `SDK version` on call sites
 * did not ask to hide it on findings. The key carries the table's own id.
 *
 * **A stored choice is filtered against the current columns on read.** A column removed in a later
 * release leaves its id in somebody's `localStorage` forever; reading that back as authoritative
 * would resurrect a column that no longer exists, or hide one that does.
 */

import { useCallback, useMemo, useState } from "react"
import { Columns3 } from "lucide-react"

import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/vendor/supabase/ui/dropdown-menu"

export interface ColumnSpec {
  readonly id: string
  readonly label: string
  /**
   * `false` where the column is the screen's claim rather than a detail of it — a provenance
   * rung, a scope, an absence marker. Defaults to hideable.
   */
  readonly hideable?: boolean
  /** `false` to start hidden. A column off by default is still listed, so it is discoverable. */
  readonly defaultVisible?: boolean
}

function storageKey(tableId: string): string {
  return `sync.columns.${tableId}`
}

/**
 * Read the stored choice, reconciled against the columns that exist now.
 *
 * Returns the visible set. A column the store does not mention takes its default, which is what
 * makes a newly added column appear for a reader who chose before it existed.
 */
function readStored(tableId: string, columns: readonly ColumnSpec[]): Set<string> {
  const defaults = new Set(
    columns.filter((column) => column.defaultVisible !== false).map((column) => column.id),
  )
  let stored: unknown
  try {
    stored = JSON.parse(window.localStorage.getItem(storageKey(tableId)) ?? "null")
  } catch {
    // A corrupt value is not worth a broken table. The defaults are always a valid answer.
    return defaults
  }
  if (!Array.isArray(stored)) return defaults

  const known = new Set(columns.map((column) => column.id))
  const chosen = new Set(stored.filter((id): id is string => typeof id === "string" && known.has(id)))
  // A column that may not be hidden is visible whatever the store says -- the rule outranks the
  // preference, and a stored set written before the rule existed must not defeat it.
  for (const column of columns) {
    if (column.hideable === false) chosen.add(column.id)
  }
  // A column that may not be hidden is visible whatever the store says -- the rule outranks the
  // preference, and a stored set written before the rule existed must not defeat it.

  return chosen.size > 0 ? chosen : defaults
}

export function useColumnVisibility(tableId: string, columns: readonly ColumnSpec[]) {
  const [visible, setVisible] = useState<Set<string>>(() => readStored(tableId, columns))

  const toggle = useCallback(
    (id: string) => {
      setVisible((current) => {
        const next = new Set(current)
        if (next.has(id)) {
          // The last one standing stays. A table with no columns is a broken screen rather than
          // a preference, and the reader who did it has no way back except clearing storage.
          if (next.size === 1) return current
          next.delete(id)
        } else {
          next.add(id)
        }
        try {
          window.localStorage.setItem(storageKey(tableId), JSON.stringify([...next]))
        } catch {
          // Private browsing, a full quota. The choice still applies for this session; it just
          // does not outlive it, which is better than refusing to apply it at all.
        }
        return next
      })
    },
    [tableId],
  )

  const isVisible = useCallback((id: string) => visible.has(id), [visible])
  return { visible, isVisible, toggle }
}

export function ColumnVisibilityMenu({
  columns,
  isVisible,
  onToggle,
}: {
  columns: readonly ColumnSpec[]
  isVisible: (id: string) => boolean
  onToggle: (id: string) => void
}) {
  const hideable = useMemo(() => columns.filter((column) => column.hideable !== false), [columns])
  const pinned = useMemo(() => columns.filter((column) => column.hideable === false), [columns])

  if (hideable.length === 0) return null

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Choose columns"
          className="inline-flex shrink-0 items-center gap-field rounded-control border border-line px-field py-field text-meta text-ink-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <Columns3 aria-hidden="true" className="size-3.5" />
          Columns
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[14rem]">
        <DropdownMenuLabel className="furniture text-meta text-ink-muted">
          Columns
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {hideable.map((column) => (
          <DropdownMenuCheckboxItem
            key={column.id}
            checked={isVisible(column.id)}
            onCheckedChange={() => onToggle(column.id)}
            onSelect={(event) => event.preventDefault()}
            className="text-meta"
          >
            {column.label}
          </DropdownMenuCheckboxItem>
        ))}
        {pinned.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-meta font-normal text-ink-muted">
              {/* Named rather than silently absent: a reader looking for the rung in this menu
                  should learn it cannot be hidden, not conclude the menu is incomplete. */}
              Always shown: {pinned.map((column) => column.label).join(", ")}
            </DropdownMenuLabel>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/**
 * `readStored`, exported for its test.
 *
 * The reconciliation is the part with a wrong answer -- a stored id for a deleted column, a
 * pinned column a stale set omits -- and it is not reachable through the hook without a renderer.
 */
export const readStoredForTest = readStored
