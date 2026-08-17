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
 *
 * ## The block treatment, M7-W179
 *
 * A multi-line value is no longer a `pre` under a label in a definition list. It is a titled block
 * with its own label strip on the vendored card's plane — the one convention both direction notes
 * single out, and the only depth this narrative spends. Scalars stay a definition list, because
 * that is what they are; the blocks follow it, which is also the order every node's `FIELDS` entry
 * already declares them in.
 *
 * `features/pullrequests/evidence-bundle.tsx` imports this file, so the Pull Request level's
 * compiler output and replay evidence take the same strip. That is the substrate migration working
 * rather than a scope leak.
 */

import type { ReactNode } from "react"

import { Absent, Formatted } from "@/components/status"
import { orAbsent } from "@/lib/format"
import { asHttpUrl } from "@/lib/url"
import { Card, CardContent, CardHeader } from "@/vendor/supabase/ui/card"

export type FieldKind = "text" | "flag" | "url" | "block"

export interface Field {
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
 *
 * Exported for `activity.ts`: the activity timeline's `primaryDetail` reuses this field order
 * to pick a node's headline evidence value rather than inventing a second vocabulary.
 */
export const FIELDS: Record<string, Field[]> = {
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

/** A scalar as a string. Objects and arrays are not scalars and return null. */
function asScalarText(value: unknown): string | null {
  if (typeof value === "string") return value
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  return null
}

/** The scalar as a string, or null for absence. `orAbsent` owns what absent means; render through `<Formatted>`. */
function scalarOrAbsent(value: unknown): string | null {
  return orAbsent(asScalarText(value))
}

function Row({
  label,
  help,
  children,
}: {
  label: string
  help?: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-field">
      <dt className="furniture text-meta text-muted-foreground">{label}</dt>
      <dd className="flex flex-col gap-field text-body">
        {children}
        {help !== undefined && (
          <p className="max-w-prose text-meta text-muted-foreground">{help}</p>
        )}
      </dd>
    </div>
  )
}

// A node's evidence boolean is a fact this node recorded about itself — not a verdict on the
// run. `verifiable` describes the customer's repository, and `verify_ok: false` is often the
// retry loop sending a patch back, working as designed. `RunOutcome` is what carries the run's
// disposition, and this reaches for the reserved status palette only there — a node fact earns
// it only by composing into that outcome, never on its own.
function Flag({ field, value }: { field: Field; value: unknown }) {
  if (typeof value !== "boolean") {
    return (
      <span className="font-mono">
        <Formatted value={scalarOrAbsent(value)} />
      </span>
    )
  }
  const wording = value
    ? (field.trueLabel ?? "yes")
    : (field.falseLabel ?? "no")
  return (
    <span className="rounded-control border border-line px-field py-field text-meta">
      {value ? "PASS" : "FAIL"} — {wording}
    </span>
  )
}

/**
 * A multi-line value, kept multi-line.
 *
 * `tsc` output is line-per-diagnostic and unreadable folded into a paragraph, so the block
 * preserves its newlines and scrolls in its own box rather than widening the page. The box is the
 * card `BlockField` puts around it; this renders the text and the two kinds of nothing.
 */
function Block({ value }: { value: unknown }) {
  // Null is tested before stringifying, not after. `JSON.stringify(null)` is the string
  // "null", which is non-empty and would draw the word `null` inside a box styled as
  // compiler output — a reader could take that for something tsc said.
  if (value === null || value === undefined) {
    return <Absent />
  }
  const text = asScalarText(value)
  const rendered = text === null ? JSON.stringify(value, null, 2) : text
  if (rendered === undefined || rendered === "") {
    return <Absent />
  }
  return (
    <pre className="max-h-72 overflow-auto font-mono text-meta whitespace-pre-wrap">
      {rendered}
    </pre>
  )
}

function languageLabel(key: string): string {
  switch (key) {
    case "diagnostics":
      return "DIAGNOSTICS"
    case "diff":
    case "patch":
      return "DIFF"
    case "replay_evidence":
      return "JSON"
    default:
      return "OUTPUT"
  }
}

/**
 * A block with a label strip, which is what a reader recognises before reading a character of it.
 *
 * The label is in the strip and nowhere else — a `dt` above the card as well would be the same word
 * twice, one of them competing with the thing it names. That is why this sits outside the
 * definition list rather than inside it as a row: a card is not a `dt`/`dd` pair and pretending
 * otherwise would cost the semantics the list is there for.
 */
function BlockField({ field, value }: { field: Field; value: unknown }) {
  return (
    <div className="flex min-w-0 flex-col gap-field">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between border-b border-border bg-surface-subtle px-section py-row">
          <h4 className="furniture text-meta text-muted-foreground">{field.label}</h4>
          <span className="font-mono text-meta text-muted-foreground uppercase">
            {languageLabel(field.key)}
          </span>
        </CardHeader>
        <CardContent className="p-section">
          <Block value={value} />
        </CardContent>
      </Card>
      {field.help !== undefined && (
        <p className="max-w-prose text-meta text-muted-foreground">{field.help}</p>
      )}
    </div>
  )
}

function ExternalLink({ value }: { value: unknown }) {
  const href = asHttpUrl(value)
  if (href === null) {
    // Present but not a followable URL — show what the run recorded, do not repair it.
    return (
      <span className="font-mono text-body">
        <Formatted value={scalarOrAbsent(value)} />
      </span>
    )
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
      // Blocks never reach here: `NodeEvidence` routes them to `BlockField`, outside the list.
      return <Block value={value} />
    case "url":
      return <ExternalLink value={value} />
    case "text":
      return (
        <span className="font-mono text-body">
          <Formatted value={scalarOrAbsent(value)} />
        </span>
      )
  }
}

const NODE_STRATEGY_EXPLANATIONS: Record<string, string> = {
  locate:
    "Decision table evaluates breaking changes against AST call signatures to select deterministic AST transforms vs model generation.",
  prepare:
    "Isolates target codebase in clean workspace; enforces zero lifecycle scripts (--ignore-scripts) and checks compiler availability.",
  patch:
    "Generates type-safe edits preserving customer formatting; carries diagnostic feedback if prior tsc verification failed.",
  static_verify:
    "Executes in-place tsc compilation; checks dependency mtime stamps to ensure no local node_modules were altered.",
  replay:
    "Validates response serialization and client parsing behavior against modified vendor schemas.",
  push_branch:
    "Stages only verified modified call sites and creates targeted branch on remote forge.",
  await_ci:
    "Monitors forge webhook events and remote test suite progress on customer CI runners.",
  open_pr:
    "Bundles verification artifacts and commit history into verified pull request.",
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
  const scalars = named.filter((field) => field.kind !== "block")
  const blocks = named.filter((field) => field.kind === "block")
  const unnamed = Object.keys(evidence).filter(
    (key) => !fields.some((field) => field.key === key),
  )

  if (named.length === 0 && unnamed.length === 0) return null

  return (
    <div className="mt-section flex flex-col gap-section">
      {(scalars.length > 0 || unnamed.length > 0) && (
        <dl className="grid gap-section sm:grid-cols-2">
          {scalars.map((field) => (
            <Row key={field.key} label={field.label} help={field.help}>
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
      )}
      {blocks.map((field) => (
        <BlockField key={field.key} field={field} value={evidence[field.key]} />
      ))}
      {name in NODE_STRATEGY_EXPLANATIONS && (
        <details className="rounded-surface border border-border bg-surface-subtle p-field text-meta text-muted-foreground">
          <summary className="cursor-pointer font-mono font-medium text-muted-foreground hover:text-foreground">
            Reasoning & Strategy
          </summary>
          <p className="mt-field font-sans text-meta text-foreground">
            {NODE_STRATEGY_EXPLANATIONS[name]}
          </p>
        </details>
      )}
    </div>
  )
}
