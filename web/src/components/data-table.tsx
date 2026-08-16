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
 *
 * `break-words` overrides the vendored `whitespace-nowrap`, and it is a correctness fix rather
 * than a preference. A heading that cannot wrap sets a floor under the table's width, and six
 * such headings inside a panel's padding is a table wider than the panel — measured at 1280x800
 * on `/vendors/:vendorId`, 974px of table in a 903px container, which put the rung column behind
 * a sideways scroll. `features/vendors/vendor-findings-table.tsx` orders its columns the way it
 * does specifically to keep that column visible at that width, so a nowrap heading defeats a
 * constraint the console already argued.
 */
export function TableHead({ className, ...props }: ComponentProps<typeof VendoredHead>) {
  return (
    <VendoredHead
      className={cn(
        "furniture whitespace-normal break-words px-row text-meta text-ink-muted",
        className,
      )}
      {...props}
    />
  )
}

/**
 * A body cell at the console's row height.
 *
 * `px-row py-row text-body` is 20px of line box between two 8px paddings, which is the 36px
 * `DESIGN.md` assigns `row-md`. The header spells the same horizontal value, so a column's heading
 * sits over its values rather than beside them.
 *
 * Measured in Chrome at 1280x800 across all seven tables on Fleet: header 40.0, single-line body
 * row 37.0 — the contract's 36 plus the 1px rule the vendored `TableRow` draws under it.
 *
 * **The horizontal value is `--spacing-row`, not the vendored `px-4`, and M7-W174 is what settled
 * it.** Fleet's ruling 8 chose the vendored 16px to keep a heading over its values; the constraint
 * it was protecting is that the two agree, not that they agree on Studio's number. Sixteen costs a
 * six-column table 96px of minimum width, and a six-column table inside a panel is the first thing
 * this console has that cannot afford it: measured at 1280x800 on `/vendors/:vendorId`, 953px of
 * table in a 903px container, with the last column clipped behind a sideways scroll.
 * `components/ui/table.tsx` — the anatomy `DESIGN.md`'s arithmetic is written against — has always
 * spelled `px-row`, so this is the substrate coming back to the contract rather than departing
 * from it.
 *
 * `break-words` is carried over from that same file, whose own comment states the trade: a row that
 * grows taller costs less than a table the viewport has to scroll to read. `break-words` rather
 * than `break-all`, so a token only splits when it would not otherwise fit and a short mono value
 * still reads as one run.
 */
export function TableCell({ className, ...props }: ComponentProps<typeof VendoredCell>) {
  return (
    <VendoredCell className={cn("px-row py-row text-body break-words", className)} {...props} />
  )
}
