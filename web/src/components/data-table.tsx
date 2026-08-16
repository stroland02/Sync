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

import type { BindingSource } from "@/api/types"
import { cn } from "@/lib/utils"
import {
  Table,
  TableBody,
  TableCell as VendoredCell,
  TableHead as VendoredHead,
  TableHeader as VendoredHeader,
  TableRow as VendoredRow,
} from "@/vendor/supabase/ui/table"

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
        "border-b transition-colors hover:bg-surface-subtle data-[state=selected]:bg-surface-emphasis",
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
    <span className="inline-flex items-center gap-1.5">
      <span>{title}</span>
      {suffix ? <span className="font-normal text-muted-foreground">{suffix}</span> : null}
      {rung ? (
        <span
          className="rounded-control border border-line px-1 py-0 font-mono text-meta font-normal text-muted-foreground"
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
