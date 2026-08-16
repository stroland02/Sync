/**
 * The reserved status treatment: an icon, a word, and the mark — never the mark alone.
 *
 * Good, warning, serious and critical are the only four colours this console spends on a
 * judgement. A run's disposition and the provenance rung are identity and evidence, not a
 * verdict, and neither one reaches for this palette.
 */

import type { ComponentType, ReactNode, SVGProps } from "react"
import { CircleCheck, CircleX, OctagonAlert, TriangleAlert } from "lucide-react"

import { ABSENT } from "@/lib/format"
import { cn } from "@/lib/utils"

export type StatusTone = "good" | "warning" | "serious" | "critical"

type LucideIcon = ComponentType<SVGProps<SVGSVGElement>>

const ICON: Record<StatusTone, LucideIcon> = {
  good: CircleCheck,
  warning: TriangleAlert,
  serious: OctagonAlert,
  critical: CircleX,
}

const INK_CLASS: Record<StatusTone, string> = {
  good: "text-good-ink",
  warning: "text-warning-ink",
  serious: "text-serious-ink",
  critical: "text-critical-ink",
}

const SURFACE_CLASS: Record<StatusTone, string> = {
  good: "border-good-ink/30 bg-good-surface",
  warning: "border-warning-ink/30 bg-warning-surface",
  serious: "border-serious-ink/30 bg-serious-surface",
  critical: "border-critical-ink/30 bg-critical-surface",
}

/** An icon and a word wearing one status's reserved ink. Colour never ships without both. */
export function Status({
  tone,
  label,
  className,
}: {
  tone: StatusTone
  label: string
  className?: string
}) {
  const Icon = ICON[tone]
  return (
    <span className={cn("inline-flex items-center gap-1.5", INK_CLASS[tone], className)}>
      <Icon aria-hidden="true" className="size-4 shrink-0" />
      {label}
    </span>
  )
}

/** The tint and border a panel takes when its headline carries a status. */
export function statusSurfaceClass(tone: StatusTone): string {
  return SURFACE_CLASS[tone]
}

/** The console's one absence marker, rendered the same way everywhere it appears. */
export function Absent({ children }: { children?: ReactNode }) {
  return (
    <span className="text-ink-muted">
      {ABSENT}
      {children ? <> {children}</> : null}
    </span>
  )
}

/**
 * A formatted value, or the absence marker when the formatter had nothing to format.
 *
 * `orAbsent`, `formatTimestamp` and `formatElapsed` in `@/lib/format` return `string | null`
 * rather than a glyph, so a call site has no bare string to render by accident and no class
 * to remember to attach. This is the one place `null` turns into `<Absent>`; everywhere else
 * a `string | null` from those helpers should pass straight through here.
 */
export function Formatted({ value }: { value: string | null }) {
  return value === null ? <Absent /> : value
}
