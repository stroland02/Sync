/**
 * One tag anatomy for every closed vocabulary the console renders.
 *
 * **M15 Task 3**, taken from Nango's note (§4): *a closed tag vocabulary as components, rather
 * than ad-hoc chips per screen*. Measured before building — severity was spelled as bare text on
 * six screens, change kind on four, adapter tier on two, and `RungBadge` was the only one that
 * was a component at all. That is the same value rendered several ways, which is the drift
 * `CLAUDE.md` calls the most expensive kind because it is silent.
 *
 * ## Monochrome, and that is a decision rather than an omission
 *
 * `DESIGN.md` permits a badge to carry colour when it is *a recorded value from a closed
 * vocabulary, legible without its colour*, and three already do: run outcome, error state,
 * absence. Severity is such a value, so a coloured severity badge would be permitted by the
 * letter — and it is refused anyway.
 *
 * The reason is what a reader would take from it. A severity ramp from `info` to `breaking` reads
 * as a judgement about *this codebase*, and severity is the **vendor's own published label**: a
 * change published as breaking breaks this codebase only where a call site binds to it. Colouring
 * it would assert a risk ordering the graph has not computed — one step from the traffic light
 * this console refuses, arriving as a gradient rather than a dot.
 *
 * So a tag is the word, in the furniture register, inside a hairline. What distinguishes members
 * is the word, which is what a reader can act on.
 *
 * ## Every member carries what it means
 *
 * A vocabulary a reader has to learn elsewhere is a vocabulary they guess at. Each tag takes a
 * `title` from its own dictionary, so hovering says what `response-optional-property-removed`
 * actually is without leaving the row.
 */

import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export function Tag({
  children,
  title,
  className,
}: {
  children: ReactNode
  /** What this member means. Omitted only where the label is already the whole meaning. */
  title?: string
  /** Accepted and ignored: the colour axis was reverted on the owner's ruling (2026-08-19
   * night), and callers that pass a tone render monochrome rather than breaking. */
  tone?: string
  className?: string
}) {
  return (
    <span
      title={title}
      className={cn(
        "furniture inline-flex shrink-0 items-center rounded-control border border-line px-field py-0.5 font-mono text-meta text-ink",
        className,
      )}
    >
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

export function SeverityTag({ severity }: { severity: string }) {
  return <Tag title={SEVERITY_MEANING[severity]}>{severity}</Tag>
}

/**
 * A vendor change kind — an oasdiff rule id, of which there are over two hundred.
 *
 * No dictionary, deliberately: `signal-stage.md` records that the authoritative list is whatever
 * `oasdiff checks` emits for the pinned binary, never a hand-maintained copy. A table of two
 * hundred descriptions here would be that copy, and it would be wrong the first time oasdiff
 * shipped a rule. The id is rendered as itself.
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

export function AdapterTierTag({ tier }: { tier: string }) {
  return <Tag title={TIER_MEANING[tier]}>{tier}</Tag>
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


/** A run outcome in the tag register — monochrome, the word carries the state. */
export function OutcomeTag({ outcome }: { outcome: string }) {
  return <Tag>{outcome}</Tag>
}
