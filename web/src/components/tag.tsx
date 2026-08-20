/**
 * One tag anatomy for every closed vocabulary the console renders.
 *
 * **M15 Task 3**, taken from Nango's note (§4): *a closed tag vocabulary as components, rather
 * than ad-hoc chips per screen*. Measured before building — severity was spelled as bare text on
 * six screens, change kind on four, adapter tier on two, and `RungBadge` was the only one that
 * was a component at all. That is the same value rendered several ways, which is the drift
 * `CLAUDE.md` calls the most expensive kind because it is silent.
 *
 * ## Coloured, by the owner's re-ruling of 2026-08-19
 *
 * This file shipped monochrome the same morning, on the argument that a coloured severity ramp
 * reads as a judgement about *this codebase* while severity is the vendor's own published label.
 * The owner reversed it on the running console: a reader triaging a table scans state faster
 * than words, and the label's provenance is the tooltip's job. What survives of the old ruling
 * is its discipline: **a tone comes only from the four reserved status colours plus neutral, it
 * never travels without the word and a shape** (the same icons `components/status.tsx` reserves,
 * so one tone has one glyph everywhere), and a value outside a vocabulary renders neutral rather
 * than guessing. The provenance rung is untouched — it stays monochrome by
 * `console-surface.md`'s own rule, because evidence class is not a state.
 *
 * ## Every member carries what it means
 *
 * A vocabulary a reader has to learn elsewhere is a vocabulary they guess at. Each tag takes a
 * `title` from its own dictionary, so hovering says what `response-optional-property-removed`
 * actually is without leaving the row.
 */

import type { ReactNode } from "react"
import { CircleCheck, CircleX, OctagonAlert, TriangleAlert } from "lucide-react"

import type { StatusTone } from "@/components/status"
import { cn } from "@/lib/utils"

/** A tag's tone: one of the reserved status colours, or the neutral hairline it always had. */
export type TagTone = StatusTone | "neutral"

const TONE_CLASS: Record<TagTone, string> = {
  neutral: "border-line text-ink",
  good: "border-good-ink/30 bg-good-surface text-good-ink",
  warning: "border-warning-ink/30 bg-warning-surface text-warning-ink",
  serious: "border-serious-ink/30 bg-serious-surface text-serious-ink",
  critical: "border-critical-ink/30 bg-critical-surface text-critical-ink",
}

// The same glyph per tone as `Status`, so one tone has one shape everywhere — the non-colour
// channel that keeps a toned tag legible to a reader the hue does not reach.
const TONE_ICON = {
  good: CircleCheck,
  warning: TriangleAlert,
  serious: OctagonAlert,
  critical: CircleX,
} as const

export function Tag({
  children,
  title,
  tone = "neutral",
  className,
}: {
  children: ReactNode
  /** What this member means. Omitted only where the label is already the whole meaning. */
  title?: string
  tone?: TagTone
  className?: string
}) {
  const Icon = tone === "neutral" ? null : TONE_ICON[tone]
  return (
    <span
      title={title}
      data-tone={tone}
      className={cn(
        "furniture inline-flex shrink-0 items-center gap-1.5 rounded-control border px-field py-0.5 font-mono text-meta",
        TONE_CLASS[tone],
        className,
      )}
    >
      {Icon !== null && <Icon aria-hidden="true" className="size-3 shrink-0" />}
      {children}
    </span>
  )
}

/**
 * What each severity means, in the vendor's terms rather than in a risk ordering of ours.
 *
 * The vocabulary is `sync.core.models.SEVERITY_ORDER` and this dictionary is keyed loosely: a
 * value outside it renders as itself with no description, which is the honest answer for a
 * severity this console has not caught up with — the same rule `lib/format.ts` applies to an
 * unrecognised rung.
 */
const SEVERITY_MEANING: Record<string, string> = {
  breaking:
    "The vendor published this as a breaking change. It breaks this codebase only where a call site binds to the operation it changed.",
  warning: "Published as a warning: behaviour changed in a way the vendor expects most callers to survive.",
  deprecation: "Published as a deprecation: still works, and the vendor has said it will not forever.",
  addition: "Published as an addition. Nothing that worked stops working.",
  info: "Published as informational.",
}

/**
 * Severity onto the ramp, in `SEVERITY_ORDER`'s own descending order so the hues rank exactly
 * as the vocabulary does — a mapping that crossed that ordering would colour a milder value
 * hotter than a graver one, which is a wrong claim no tooltip repairs. Exported for the test
 * that holds the two orderings together.
 */
export const SEVERITY_TONE: Record<string, TagTone> = {
  breaking: "critical",
  warning: "serious",
  deprecation: "warning",
  addition: "good",
  info: "neutral",
}

export function SeverityTag({ severity }: { severity: string }) {
  return (
    <Tag tone={SEVERITY_TONE[severity] ?? "neutral"} title={SEVERITY_MEANING[severity]}>
      {severity}
    </Tag>
  )
}

/**
 * A run's disposition onto the ramp: opened is the loop closing, abandoned is the loop giving
 * up (kept data, but a graver state than a warning), reported is open-and-unpatched. In-flight
 * and anything the console has not caught up with stay neutral — colouring an unknown value
 * would be a confident wrong verdict, the failure `run-outcome.tsx` exists to replace.
 */
export const OUTCOME_TONE: Record<string, TagTone> = {
  opened: "good",
  abandoned: "serious",
  reported: "warning",
}

export function OutcomeTag({ outcome }: { outcome: string }) {
  return <Tag tone={OUTCOME_TONE[outcome] ?? "neutral"}>{outcome}</Tag>
}

/**
 * A vendor change kind — an oasdiff rule id, of which there are over two hundred.
 *
 * No dictionary, deliberately: `signal-stage.md` records that the authoritative list is whatever
 * `oasdiff checks` emits for the pinned binary, never a hand-maintained copy. A table of two
 * hundred descriptions here would be that copy, and it would be wrong the first time oasdiff
 * shipped a rule. The id is rendered as itself — and neutral, because two hundred members is a
 * vocabulary no ramp can rank; the severity tag beside it carries the state.
 */
export function ChangeKindTag({ kind }: { kind: string }) {
  return <Tag>{kind}</Tag>
}

const TIER_MEANING: Record<string, string> = {
  coded: "An adapter written in Sync.",
  generated: "Served from a manifest the vendor's own SDK repository commits.",
  mcp: "Captures of a watched MCP server.",
  unregistered:
    "The graph holds history keyed by this vendor and no adapter serves it any more.",
}

/** Tiers are mechanisms — identity, not state — so the one that is a gap wears the ramp and
 * the live three stay neutral. */
export function AdapterTierTag({ tier }: { tier: string }) {
  return (
    <Tag tone={tier === "unregistered" ? "warning" : "neutral"} title={TIER_MEANING[tier]}>
      {tier}
    </Tag>
  )
}

/**
 * What each binding status means, and why `unchecked` is the member that earns the other two.
 *
 * The owner's question was *why do we not show safe APIs*. This is the answer, and the reason it
 * can be given honestly is `intake_attempt`: a vendor with no successful intake has never had its
 * specification read, so its calls are unexamined rather than fine. Without that third member,
 * `clean` would be an all-clear the console never earned.
 */
const BINDING_STATUS_MEANING: Record<string, string> = {
  at_risk:
    "An open finding names this operation. A vendor change meets a call this codebase makes, at the call sites listed against it.",
  clean:
    "The vendor's specification was read and nothing in it binds to this call. A measured answer about this operation, not an absence of one.",
  unchecked:
    "No successful intake for this integration, so its specification has never been read. Not the same as clean: nothing here has been examined, and a decline or a failed fetch is not evidence about the call.",
}

const BINDING_STATUS_LABEL: Record<string, string> = {
  at_risk: "at risk",
  clean: "clean",
  unchecked: "not checked",
}

/**
 * A binding status onto the ramp, following the owner's re-ruling above.
 *
 * **`at_risk` is `serious` rather than `critical`, and that is the honest half.** It means an open
 * finding names this operation — of *any* severity — so wearing the same tone as `breaking` would
 * claim a grade the status does not carry. The severity tag beside it is what ranks the finding.
 *
 * **`unchecked` is toned at all, which is the point of the member.** It is not a milder `clean`:
 * nothing about these calls has been examined, and the one way this feature could fail its reader
 * is by being skimmed past as though it were. A warning tone and the word *not checked* both say
 * so, which is the rule that a tone never travels without its word.
 */
export const BINDING_STATUS_TONE: Record<string, TagTone> = {
  at_risk: "serious",
  unchecked: "warning",
  clean: "good",
}

export function BindingStatusTag({ status }: { status: string }) {
  return (
    <Tag tone={BINDING_STATUS_TONE[status] ?? "neutral"} title={BINDING_STATUS_MEANING[status]}>
      {BINDING_STATUS_LABEL[status] ?? status}
    </Tag>
  )
}

/**
 * Where a change unit's finding count sits — not a severity, and not a score.
 *
 * A count is a count; this exists so a table can render one in the tag register beside its
 * siblings rather than as loose text that reads as a different kind of thing.
 */
export function CountTag({ count, unit }: { count: number; unit: string }) {
  return (
    <Tag className="tabular-nums">
      {count.toLocaleString()} {unit}
    </Tag>
  )
}
