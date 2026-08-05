/**
 * What each node produced, rendered as itself rather than as a key-value dump.
 *
 * This is the screen a reviewer came for. `diagnostics` is raw compiler output and has to
 * read as compiler output; `ci_url` is a run worth following and has to be a link; a
 * boolean gate has to say which way it went in words. A generic table of `key: value` would
 * technically show all of that and answer none of it.
 *
 * A key absent from the payload means the run never produced it, and nothing is drawn. A
 * key present holding null means the run produced null, and that draws the absence marker.
 * Collapsing those two would make "not run yet" and "ran, found nothing" the same cell.
 */

import type { ReactNode } from "react"

import { ABSENT, orAbsent } from "@/lib/format"
import { cn } from "@/lib/utils"

type FieldKind = "text" | "flag" | "url" | "block"

interface Field {
  key: string
  label: string
  kind: FieldKind
  /** What the value means, for a reader who does not know the graph's vocabulary. */
  help?: string
  /** Wording for a flag, because "yes" is not what `verify_ok: true` says. */
  trueLabel?: string
  falseLabel?: string
}

/**
 * The evidence each node carries, keyed and ordered as `_EVIDENCE_KEYS` in
 * `sync.dashboard.queries` writes it. Mirrored rather than derived: the payload cannot say
 * which of its keys is a URL and which is multi-line compiler output.
 */
const FIELDS: Record<string, Field[]> = {
  locate: [
    {
      key: "tier",
      label: "Tier",
      kind: "text",
      help: "Which remediation tier the decision table assigned to this change kind.",
    },
    {
      key: "routing_row",
      label: "Routing row",
      kind: "text",
      help: "The row of the decision table that assigned it.",
    },
  ],
  prepare: [
    {
      key: "prepare_ok",
      label: "Repository prepared",
      kind: "flag",
      trueLabel: "cloned and dependencies installed",
      falseLabel: "preparation failed",
    },
    {
      key: "verifiable",
      label: "Patch is verifiable",
      kind: "flag",
      trueLabel: "the language adapter can compile this tree",
      falseLabel: "the language adapter cannot verify a patch here",
    },
    {
      key: "verify_gap",
      label: "Why not verifiable",
      kind: "text",
      help: "The adapter's own reason. Empty when the adapter verifies.",
    },
  ],
  patch: [
    {
      key: "static_attempts",
      label: "Attempt",
      kind: "text",
      help: "How many times the patch node has run. Above one means verification sent it back.",
    },
    {
      key: "attempt_strategy",
      label: "Strategy",
      kind: "text",
      help: "Which remediator produced the edit for this attempt.",
    },
  ],
  static_verify: [
    {
      key: "verify_ok",
      label: "tsc verdict",
      kind: "flag",
      trueLabel: "the tree a push would carry compiles",
      falseLabel: "the compiler rejected the patched tree",
    },
    {
      key: "diagnostics",
      label: "Compiler output",
      kind: "block",
    },
  ],
  replay: [
    { key: "replay_outcome", label: "Replay outcome", kind: "text" },
    { key: "replay_reason", label: "Reason", kind: "text" },
    { key: "replay_evidence", label: "Replay evidence", kind: "block" },
  ],
  push_branch: [
    {
      key: "branch",
      label: "Branch",
      kind: "text",
      help: "The branch pushed to the customer's repository.",
    },
  ],
  await_ci: [
    {
      key: "ci_url",
      label: "CI run watched",
      kind: "url",
    },
    {
      key: "ci_attempts",
      label: "CI attempt",
      kind: "text",
      help: "How many times the run has waited on CI.",
    },
    { key: "attempt_ci_result", label: "Result", kind: "text" },
  ],
  open_pr: [
    { key: "pr_url", label: "Pull request", kind: "url" },
    { key: "pr_number", label: "Number", kind: "text" },
  ],
}

/**
 * A URL the payload gave, or null.
 *
 * The value originates in the customer's repository by way of the forge, which makes it
 * untrusted input arriving at a boundary. Anything that is not http or https renders as
 * text: a `javascript:` href in an anchor is a script the console would be running on
 * someone else's say-so. Nothing here constructs a URL the payload did not send.
 */
function asHttpUrl(value: unknown): string | null {
  if (typeof value !== "string" || value === "") return null
  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    return null
  }
  return parsed.protocol === "http:" || parsed.protocol === "https:" ? value : null
}

/** A scalar as a string. Objects and arrays are not scalars and return null. */
function asScalarText(value: unknown): string | null {
  if (typeof value === "string") return value
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  return null
}

/** The absence marker unless the value is a non-empty scalar. `orAbsent` owns what absent means. */
function scalarOrAbsent(value: unknown): string {
  return orAbsent(asScalarText(value))
}

function Row({
  label,
  help,
  className,
  children,
}: {
  label: string
  help?: string
  className?: string
  children: ReactNode
}) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <dt className="text-meta tracking-wide text-muted-foreground uppercase">{label}</dt>
      <dd className="flex flex-col gap-1 text-body">
        {children}
        {help !== undefined && <p className="text-meta text-muted-foreground">{help}</p>}
      </dd>
    </div>
  )
}

function Flag({ field, value }: { field: Field; value: unknown }) {
  if (typeof value !== "boolean") {
    return <span className="font-mono">{scalarOrAbsent(value)}</span>
  }
  const wording = value
    ? (field.trueLabel ?? "yes")
    : (field.falseLabel ?? "no")
  return (
    <span
      className={
        value
          ? "rounded border border-border px-1.5 py-0.5 text-meta"
          : "rounded border border-destructive px-1.5 py-0.5 text-meta text-destructive"
      }
    >
      {value ? "PASS" : "FAIL"} — {wording}
    </span>
  )
}

/**
 * A multi-line value, kept multi-line.
 *
 * `tsc` output is line-per-diagnostic and unreadable folded into a paragraph, so the block
 * preserves its newlines and scrolls in its own box rather than widening the page.
 */
function Block({ value }: { value: unknown }) {
  // Null is tested before stringifying, not after. `JSON.stringify(null)` is the string
  // "null", which is non-empty and would draw the word `null` inside a box styled as
  // compiler output — a reader could take that for something tsc said.
  if (value === null || value === undefined) {
    return <span className="text-muted-foreground">{ABSENT}</span>
  }
  const text = asScalarText(value)
  const rendered = text === null ? JSON.stringify(value, null, 2) : text
  if (rendered === undefined || rendered === "") {
    return <span className="text-muted-foreground">{ABSENT}</span>
  }
  return (
    <pre className="max-h-72 overflow-auto rounded border border-border bg-muted p-2 font-mono text-meta whitespace-pre-wrap">
      {rendered}
    </pre>
  )
}

function ExternalLink({ value }: { value: unknown }) {
  const href = asHttpUrl(value)
  if (href === null) {
    // Present but not a followable URL — show what the run recorded, do not repair it.
    return <span className="font-mono text-body">{scalarOrAbsent(value)}</span>
  }
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className="font-mono text-body underline underline-offset-2"
    >
      {href}
    </a>
  )
}

function FieldValue({ field, value }: { field: Field; value: unknown }) {
  switch (field.kind) {
    case "flag":
      return <Flag field={field} value={value} />
    case "block":
      return <Block value={value} />
    case "url":
      return <ExternalLink value={value} />
    case "text":
      return <span className="font-mono text-body">{scalarOrAbsent(value)}</span>
  }
}

/**
 * Everything one node produced.
 *
 * Keys the payload carries that this file does not name are still rendered, at the end and
 * generically. A transport that grows an evidence key should look unstyled here, not
 * invisible.
 */
export function NodeEvidence({
  name,
  evidence,
}: {
  name: string
  evidence: Record<string, unknown>
}) {
  const fields = FIELDS[name] ?? []
  const named = fields.filter((field) => field.key in evidence)
  const unnamed = Object.keys(evidence).filter(
    (key) => !fields.some((field) => field.key === key),
  )

  if (named.length === 0 && unnamed.length === 0) return null

  return (
    <dl className="mt-3 grid gap-3 sm:grid-cols-2">
      {named.map((field) => (
        <Row
          key={field.key}
          label={field.label}
          help={field.help}
          className={field.kind === "block" ? "sm:col-span-2" : undefined}
        >
          <FieldValue field={field} value={evidence[field.key]} />
        </Row>
      ))}
      {unnamed.map((key) => (
        <Row key={key} label={key}>
          <span className="font-mono text-body">
            {asScalarText(evidence[key]) ?? JSON.stringify(evidence[key])}
          </span>
        </Row>
      ))}
    </dl>
  )
}
