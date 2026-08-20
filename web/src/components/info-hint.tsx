/**
 * The â“˜ beside a heading: explanation on demand, for prose the screen does not need in front
 * of the data.
 *
 * Owner direction, 2026-08-18, amended 2026-08-19: a reader is here for their own data, so field
 * descriptions and how-this-panel-works prose move behind a hover.
 *
 * **What may move here is the argument. What may not is the claim.** The amendment replaced a rule
 * protecting twenty-four specific sentences from ever reaching a tooltip â€” it blocked ordinary
 * cleanup and seven of them cited deleted files. What survives is stricter about the thing that
 * mattered: a reader who never hovers must still be able to tell what a figure covers and whether
 * it was measured. *not measured yet* Â· *all workspaces* Â· *static evidence* stay on screen in the
 * fewest honest words; why each distinction exists comes here. `web/CLAUDE.md` carries it.
 *
 * A real button, not a bare icon: Radix opens a tooltip on focus as well as hover, so the
 * keyboard path exists only if the trigger is focusable. The `aria-label` names what the hint
 * explains rather than saying "info".
 */

import { Info } from "lucide-react"
import type { ReactNode } from "react"

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/vendor/supabase/ui/tooltip"

export function InfoHint({
  label,
  children,
  side = "bottom",
}: {
  /** What this hint explains, for the accessible name â€” "About index coverage". */
  label: string
  /** The explanation itself. Prose, no interactive content: a tooltip closes on the way to it. */
  children: ReactNode
  side?: "top" | "bottom" | "left" | "right"
}) {
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={label}
            className="inline-flex shrink-0 items-center justify-center rounded-control text-ink-muted transition-colors hover:text-ink focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <Info aria-hidden="true" className="size-3.5" />
          </button>
        </TooltipTrigger>
        <TooltipContent
          side={side}
          className="max-w-[24rem] px-section py-row text-left text-body font-normal normal-case leading-snug text-ink"
        >
          {children}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
