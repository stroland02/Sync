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
        "has-aria-expanded:bg-surface-subtle data-[state=selected]:bg-surface-emphasis data-[interactive=true]:cursor-pointer data-[interactive=true]:transition-colors data-[interactive=true]:hover:bg-surface-subtle",
        className
      )}
      {...props}
    />
  )
}

// Padding is the same on every cell, header or body: 8px inline from the shared `--spacing-row`
// token, 10px block. The row height is a consequence of that padding plus each cell's own type
// step, not a separately chosen number -- a header row (`--text-meta`, 16px line height) lands
// at 36px and a body row (`--text-body`, 20px line height) lands at 40px from the identical
// padding declaration.
function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        "px-row py-2.5 text-left align-middle text-meta font-medium break-words text-foreground [&:has([role=checkbox])]:pr-0",
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
        "px-row py-2.5 text-body align-middle break-words [&:has([role=checkbox])]:pr-0",
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
