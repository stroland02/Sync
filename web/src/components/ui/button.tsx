import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-lg border border-transparent bg-clip-padding text-sm font-medium whitespace-nowrap transition-colors outline-none select-none focus:border-ring focus:ring-3 focus:ring-ring active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground hover:bg-[color-mix(in_oklch,var(--color-primary),var(--color-foreground)_15%)]",
        outline:
          "border-border bg-background hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground dark:border-input dark:bg-input/30 dark:hover:bg-input/50",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-[color-mix(in_oklch,var(--color-secondary),var(--color-foreground)_5%)] aria-expanded:bg-secondary aria-expanded:text-secondary-foreground",
        ghost:
          "hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground dark:hover:bg-muted/50",
        // No focus-ring override. This variant used to recolour the ring to `critical-ink` at
        // 20% and its border at 40%, which composite to 1.40:1 and 2.03:1 against the button's
        // own surface — a focus signal below the 3:1 non-text floor on the one variant whose job
        // is to be hard to press by accident. The base ring is the same affordance everywhere,
        // and DESIGN.md's rule that colour claims a judgement argues against tinting it per
        // variant in the first place.
        destructive:
          "bg-critical-surface text-critical-ink hover:bg-[color-mix(in_oklch,var(--color-critical-surface),var(--color-surface)_25%)] dark:hover:bg-[color-mix(in_oklch,var(--color-critical-surface),var(--color-surface-sunken)_25%)]",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default:
          "h-8 gap-field px-row has-data-[icon=inline-end]:pr-row has-data-[icon=inline-start]:pl-row",
        xs: "h-6 gap-field rounded-[min(var(--radius-md),10px)] px-row text-meta in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-field has-data-[icon=inline-start]:pl-field [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-field rounded-[min(var(--radius-md),12px)] px-row text-meta in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-field has-data-[icon=inline-start]:pl-field [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-9 gap-field px-row has-data-[icon=inline-end]:pr-row has-data-[icon=inline-start]:pl-row",
        icon: "size-8",
        "icon-xs":
          "size-6 rounded-[min(var(--radius-md),10px)] in-data-[slot=button-group]:rounded-lg [&_svg:not([class*='size-'])]:size-3",
        "icon-sm":
          "size-7 rounded-[min(var(--radius-md),12px)] in-data-[slot=button-group]:rounded-lg",
        "icon-lg": "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
