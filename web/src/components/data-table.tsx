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
 * `Table`, `TableBody`, `TableHeader` and `TableRow` are re-exported untouched so a caller has one
 * import for a table rather than two, and so the identifying column, the row hover and the sticky
 * shadow all come from the vendored component unmodified.
 */

import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"
import {
  Table,
  TableBody,
  TableCell as VendoredCell,
  TableHead as VendoredHead,
  TableHeader,
  TableRow,
} from "@/vendor/supabase/ui/table"

export { Table, TableBody, TableHeader, TableRow }

/**
 * A column heading in the furniture register: uppercase, open-tracked, the second ink level.
 *
 * The height comes from the vendored component's own `h-10`, which is `DESIGN.md`'s `row-lg`.
 */
export function TableHead({ className, ...props }: ComponentProps<typeof VendoredHead>) {
  return (
    <VendoredHead
      className={cn("furniture text-meta text-ink-muted", className)}
      {...props}
    />
  )
}

/**
 * A body cell at the console's row height.
 *
 * `px-section py-row text-body` is 20px of line box between two 8px paddings, which is the 36px
 * `DESIGN.md` assigns `row-md`. The horizontal value matches the vendored header's own so a
 * column's heading sits over its values rather than beside them.
 *
 * Measured in Chrome at 1280x800 across all seven tables on Fleet: header 40.0, single-line body
 * row 37.0 — the contract's 36 plus the 1px rule the vendored `TableRow` draws under it.
 */
export function TableCell({ className, ...props }: ComponentProps<typeof VendoredCell>) {
  return <VendoredCell className={cn("px-section py-row text-body", className)} {...props} />
}
