import * as React from "react"

import { cn } from "@/lib/utils"

function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div
      data-slot="table-container"
      className="relative w-full overflow-x-auto"
    >
      <table
        data-slot="table"
        className={cn("w-full caption-bottom text-sm", className)}
        {...props}
      />
    </div>
  )
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return (
    <thead
      data-slot="table-header"
      className={cn("[&_tr]:border-b", className)}
      {...props}
    />
  )
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return <tbody data-slot="table-body" className={cn(className)} {...props} />
}

function TableFooter({ className, ...props }: React.ComponentProps<"tfoot">) {
  return (
    <tfoot
      data-slot="table-footer"
      className={cn(
        "border-t bg-muted/50 font-medium [&>tr]:last:border-b-0",
        className
      )}
      {...props}
    />
  )
}

// No row responds to the pointer by default: a highlight on a row that leads nowhere is a
// promise made forty times a screen. `interactive` is how a caller that wires a row to
// navigation (a click handler, a wrapping `<Link>`) opts back in.
//
// No transition on the hover fill. The gate is frequency, not duration: a row hover is the
// most frequent interaction in this console, crossed on every pointer move over every table,
// all day. Sentry's own row primitive, which owns the same job, declares no transition either
// -- its written rule is that frequent interactions should avoid animation altogether
// (`motion.mdx:39`, cited in DESIGN.md's Motion section). An occasional surface, like an
// overlay arriving, still gets one; a row does not.
function TableRow({
  className,
  interactive = false,
  ...props
}: React.ComponentProps<"tr"> & { interactive?: boolean }) {
  return (
    <tr
      data-slot="table-row"
      data-interactive={interactive ? "true" : undefined}
      className={cn(
        "has-aria-expanded:bg-surface-subtle data-[state=selected]:bg-surface-emphasis data-[interactive=true]:cursor-pointer data-[interactive=true]:hover:bg-surface-subtle",
        className
      )}
      {...props}
    />
  )
}

// Padding is `--spacing-row` on both axes of both cells. The row height is *not* a consequence
// of it: DESIGN.md's Row height section chooses the height from the scale first and derives the
// padding from it, so a body row lands at `row-md` (36px: `--text-body`'s 20px line box plus 8px
// top and bottom) and a header declares `row-lg` outright.
//
// This comment and DESIGN.md used to say opposite things, and the code followed this one. It read
// "10px block... the row height is a consequence of that padding, not a separately chosen
// number", which produced a 36px header and a 40px body row -- the two heights the contract
// assigns, in each other's slots. Both sentences are now the same rule, and
// `tests/test_console_design_tokens.py` multiplies these classes out against DESIGN.md's tables
// so the two cannot drift apart again silently.
//
// Declared and unconsumed today, on purpose, not by oversight: `aria-[sort]:text-foreground`
// renders a column at primary ink whenever it carries an `aria-sort` attribute -- a recorded
// fact about which ordering produced the rows beneath it, not a judgement, matching Sentry's
// own `&[aria-sort] { color: content.primary }`. No table in this console sorts yet, so nothing
// sets the attribute today, which makes the selector a no-op in both directions: it never fires
// (nothing sets `aria-sort`), and if it did fire it would repaint text that is already
// `text-foreground` by this component's own default -- that default is a separate, earlier
// decision this change does not revisit.
//
// The retiring condition, not just the intent: `docs/superpowers/plans/2026-08-05-sync-console-
// architecture.md` section 21.6 names the primitive this is waiting on -- a sortable header cell
// that owns `aria-sort` and the sort control together (Sentry's
// `sortableHeaderCell.tsx`), listed there as "added, and it is cheap" but not yet built. This
// selector stops being a no-op the day that primitive lands and a caller passes
// `aria-sort="ascending" | "descending" | "none"` through it -- not before, and deleting the
// selector now would be removing a rule Task 13 already argued for and priced, only to have the
// header-cell task re-add the identical line.
//
// `h-10` is `row-lg`, and padding alone could not reach it: 12px of `--text-meta` on a 16px line
// box plus the 8px row token is 32px, and the only value that would make it 40 is a 12px vertical
// padding the contract does not name. In table layout a declared height is a minimum, so a header
// label that wraps still grows past it.
function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        "h-10 px-row py-row text-left align-middle text-meta font-medium break-words text-foreground aria-[sort]:text-foreground [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  )
}

// Cells wrap by default rather than force the table wider than its container: a row that
// grows taller costs less than a table the viewport has to scroll to read. `break-words`
// (not `break-all`) only splits a token — an id, a hash — when it would not otherwise fit,
// so short mono content still reads as one unbroken run. `Table`'s `overflow-x-auto` wrapper
// stays as a fallback for a column a caller deliberately keeps unbreakable with its own
// `whitespace-nowrap`, not as the table's normal-case behaviour.
function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn(
        "px-row py-row text-body align-middle break-words [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  )
}

function TableCaption({
  className,
  ...props
}: React.ComponentProps<"caption">) {
  return (
    <caption
      data-slot="table-caption"
      className={cn("mt-section text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
}
