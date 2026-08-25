/**
 * The console's table anatomy, declared once over the vendored primitive.
 *
 * `vendor/supabase/ui/table.tsx` is consumed rather than edited, and it arrives with two things
 * this tree cannot use as they stand. Its header asks for a `heading-meta` class that Supabase
 * declares in globals we did not vendor; the console's equivalent is `.furniture`, which
 * `index.css` has carried since the design-system slice and which `DESIGN.md` ties to the scanned
 * label register. And its cell padding is Studio's rather than ours: `DESIGN.md` derives a
 * single-line body row at 36px from `--text-body`'s line box plus `--spacing-row` top and bottom,
 * and a header at 40px, which is the arithmetic `tests/test_console_design_tokens.py` holds
 * against `components/ui/table.tsx`.
 *
 * Both are one class string each, which is exactly why they belong here rather than on every
 * `TableHead` in nine levels. A feature that hand-spells them is a feature that will drift from
 * the other eight the first time somebody adjusts one of them.
 *
 * `Table` and `TableBody` are re-exported untouched so a caller has one import for a table.
 */

import type { ComponentProps, ReactNode } from "react"
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react"

import type { BindingSource } from "@/api/types"
import { cn } from "@/lib/utils"
import {
  Table,
  TableBody,
  TableCell as VendoredCell,
  TableHead as VendoredHead,
  TableHeader as VendoredHeader,
  TableRow as VendoredRow,
} from "@/components/ui/table"

export { Table, TableBody }

/**
 * A table header row rendered on the substrate's subtle surface strip.
 */
export function TableHeader({ className, ...props }: ComponentProps<typeof VendoredHeader>) {
  return (
    <VendoredHeader
      className={cn("[&_tr]:border-b [&_tr]:bg-surface-subtle", className)}
      {...props}
    />
  )
}

/**
 * A table row with distinct hover and selected states.
 */
export function TableRow({ className, ...props }: ComponentProps<typeof VendoredRow>) {
  return (
    <VendoredRow
      className={cn(
        // 36px as a floor, not a clamp. The design system asks for a strict 36px row, and a
        // single-line row is exactly that. Measured on the call-sites table, rows come out at
        // 39px -- and that is honest rather than drift: the leading cell stacks a file path over
        // a muted second line, so it carries two 16px line boxes inside the same 8px padding.
        // Clamping to 36px would clip the second line, which is the content the screen exists
        // to show. `min-h` holds the rhythm where a row has one line and yields where it has two.
        "min-h-[var(--row-md)] box-border border-b transition-colors hover:bg-surface-subtle data-[state=selected]:bg-surface-emphasis",
        className
      )}
      {...props}
    />
  )
}

/**
 * A column heading in the furniture register: uppercase, open-tracked, font-medium, the second ink level.
 *
 * The height comes from the vendored component's own `h-10`, which is `DESIGN.md`'s `row-lg`.
 * `font-medium` (500) overrides the UA-default `font-weight: 700`.
 *
 * `break-words` overrides the vendored `whitespace-nowrap`, and it is a correctness fix rather
 * than a preference. A heading that cannot wrap sets a floor under the table's width, and six
 * such headings inside a panel's padding is a table wider than the panel.
 */
export function TableHead({ className, ...props }: ComponentProps<typeof VendoredHead>) {
  return (
    <VendoredHead
      className={cn(
        "furniture whitespace-normal break-words px-row text-meta font-medium text-ink-muted",
        className
      )}
      {...props}
    />
  )
}

/**
 * A column header title supporting an optional suffix, provenance rung badge, or bounded indicator.
 */
export function TableHeadTitle({
  title,
  suffix,
  rung,
  bounded,
}: {
  title: ReactNode
  suffix?: ReactNode
  rung?: BindingSource | null
  bounded?: boolean
}) {
  return (
    <span className="inline-flex items-center gap-field.5">
      <span>{title}</span>
      {suffix ? <span className="font-normal text-muted-foreground">{suffix}</span> : null}
      {rung ? (
        <span
          className="rounded-control border border-line px-field py-0 font-mono text-meta font-normal text-muted-foreground"
          title={`Provenance: ${rung}`}
        >
          {rung}
        </span>
      ) : null}
      {bounded !== undefined ? (
        <span className="font-mono text-meta font-normal text-muted-foreground">
          {bounded ? "(bounded)" : "(unbounded)"}
        </span>
      ) : null}
    </span>
  )
}

/**
 * A body cell at the console's row height.
 *
 * `px-row py-row text-body` is 20px of line box between two 8px paddings, which is the 36px
 * `DESIGN.md` assigns `row-md`. The header spells the same horizontal value, so a column's heading
 * sits over its values rather than beside them.
 */
export function TableCell({ className, ...props }: ComponentProps<typeof VendoredCell>) {
  return (
    <VendoredCell className={cn("px-row py-row text-body break-words", className)} {...props} />
  )
}

/**
 * An empty table row spanning all columns, keeping the header structure visible while displaying an empty state.
 */
export function TableEmptyRow({
  colSpan,
  children,
  className,
}: {
  colSpan: number
  children: ReactNode
  className?: string
}) {
  return (
    <TableRow>
      <TableCell
        colSpan={colSpan}
        className={cn("p-card text-center text-muted-foreground", className)}
      >
        {children}
      </TableCell>
    </TableRow>
  )
}

/**
 * The box a long table lives in, so the scroll belongs to the table rather than to the page.
 *
 * The vendored `Table` already wraps itself in `ShadowScrollArea`, whose inner div is
 * `w-full overflow-auto` — the horizontal scroll exists. What was missing is the thing that
 * makes it *work*: a scroll container inside a flex or grid parent has a min-content floor,
 * so a fourteen-column table pushes its parent wider and the **page** scrolls while the
 * container never does. `min-w-0` removes that floor and `overflow-hidden` clips whatever
 * would otherwise escape the frame, which together are the guarantee the inner scroll needs.
 *
 * Both are layout, not appearance, and nothing here asserts them: jsdom loads no stylesheet,
 * so the test holds the containment (the table sits inside the frame) and the rendered
 * behaviour is measured in Chrome per `.claude/rules/console-dev-loop.md`.
 */
export function TableFrame({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      data-slot="table-frame"
      className={cn("min-w-0 overflow-hidden rounded-surface border border-line", className)}
    >
      {children}
    </div>
  )
}

/**
 * What a column holds, as a closed vocabulary.
 *
 * This is the one thing a spreadsheet-shaped table gains over a list, and it is a fact about
 * the column rather than a judgement about its values: a reader can tell a count from an
 * identifier that happens to be digits, or a duration from a timestamp, before reading a row.
 * `enum` is deliberately the label for every closed vocabulary the graph stores — a change
 * kind, a rung, a run outcome — because naming the specific vocabulary in the header would
 * duplicate what the cells already say.
 */
export type ColumnType =
  | "text"
  | "identifier"
  | "path"
  | "count"
  | "number"
  | "timestamp"
  | "duration"
  | "enum"

/** How each column type is spelled in the header. Exhaustive by construction. */
export const COLUMN_TYPE_LABEL: Record<ColumnType, string> = {
  text: "text",
  identifier: "id",
  path: "path",
  count: "count",
  number: "number",
  timestamp: "timestamp",
  duration: "duration",
  enum: "enum",
}

/** Which way a sorted column runs. Spelled as ARIA spells it, so `aria-sort` needs no mapping. */
export type SortDirection = "ascending" | "descending"

/** The one column a table is sorted by, and which way. Null means no column sort is applied. */
export interface ColumnSort<K extends string = string> {
  column: K
  direction: SortDirection
}

/**
 * The direction a click asks for next: ascending, then descending, then away again.
 *
 * The third state is not decoration. A table with no column sort is not unsorted — it is in
 * the order the query returned, which is itself a fact an operator reads (`ordering.tsx`
 * carries the argument). Without a way back to it, the first click on any header destroys an
 * arrangement the reader cannot restore.
 */
export function nextSortDirection(current: SortDirection | null): SortDirection | null {
  if (current === null) return "ascending"
  return current === "ascending" ? "descending" : null
}

/** What `aria-sort` a column header carries, given the table's one applied column sort. */
export function ariaSortFor(
  column: string,
  sort: ColumnSort | null
): "ascending" | "descending" | "none" {
  return sort !== null && sort.column === column ? sort.direction : "none"
}

/**
 * The applied arrangement, in one sentence, for a reader who chose nothing.
 *
 * A screen renders this beside its table. The no-sort branch names the query's own ordering
 * rather than calling the table unsorted, because "unsorted" is a claim the data does not
 * support: a reader who believes it reads a page boundary that moved as a record that changed.
 */
export function describeAppliedSort(
  sort: ColumnSort | null,
  columnLabel: (column: string) => string,
  queryOrdering: string
): string {
  if (sort === null) {
    return (
      `No column sort is applied: these rows are in ${queryOrdering}, which is an ordering ` +
      "rather than the absence of one."
    )
  }
  return `Ordered by ${columnLabel(sort.column)}, ${sort.direction}.`
}

/**
 * A typed column heading, sortable when the table can sort on it.
 *
 * The sort state travels on `aria-sort` as well as in the glyph, so which column is sorted and
 * which way is readable without seeing the arrow — the same rule that keeps a status colour
 * from travelling alone. A column with no `onSortChange` renders no control and no `aria-sort`
 * at all, because "sortable, currently unsorted" and "not sortable" are different facts and an
 * `aria-sort="none"` on both would collapse them.
 */
export function TableColumnHead<K extends string>({
  column,
  label,
  type,
  sort = null,
  onSortChange,
  rung,
  className,
}: {
  column: K
  label: ReactNode
  type: ColumnType
  sort?: ColumnSort<K> | null
  onSortChange?: (next: ColumnSort<K> | null) => void
  rung?: BindingSource | null
  className?: string
}) {
  const title = <TableHeadTitle title={label} suffix={COLUMN_TYPE_LABEL[type]} rung={rung} />

  if (onSortChange === undefined) {
    return <TableHead className={className}>{title}</TableHead>
  }

  const direction = sort !== null && sort.column === column ? sort.direction : null
  const Glyph =
    direction === "ascending" ? ArrowUp : direction === "descending" ? ArrowDown : ChevronsUpDown

  return (
    <TableHead className={className} aria-sort={ariaSortFor(column, sort)}>
      <button
        type="button"
        className="inline-flex w-full cursor-pointer items-center gap-field bg-transparent text-left"
        onClick={() => {
          const next = nextSortDirection(direction)
          onSortChange(next === null ? null : { column, direction: next })
        }}
      >
        {title}
        <Glyph aria-hidden="true" className="size-3 shrink-0 text-ink-muted" />
      </button>
    </TableHead>
  )
}
