/**
 * The ⓘ beside a heading: explanation on demand, for prose the screen does not need in front
 * of the data.
 *
 * Owner direction, 2026-08-18: a reader is here for their own data, so field descriptions and
 * how-this-panel-works prose move behind a hover, with the fuller account living in Settings →
 * Pages. **What may move here is explanation. What may not is a claim** — the protected honesty
 * sentences (`docs/superpowers/plans/2026-08-05-sync-console-architecture.md:102-207`), a
 * count's scope, and any absence-versus-zero distinction stay on screen, because a tooltip is a
 * disclosure and those sentences are barred from disclosures by a thrice-recorded ruling.
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
  /** What this hint explains, for the accessible name — "About index coverage". */
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
            className="inline-flex shrink-0 items-center justify-center rounded-control text-ink-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
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
