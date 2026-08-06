/**
 * The remediation graph as a sequence of nodes, each with its own state and its own output.
 *
 * Not a progress bar, and the difference is the point. A bar says "sixty per cent" and can
 * only go forwards; this graph loops — a `patch` that failed verification is due again, and
 * a bar would render that as progress. A sequence says which node ran, which one the graph
 * owes a visit, which never started, and what each one produced. That is what a reviewer
 * has to see before trusting a pull request.
 */

import { motion } from "framer-motion"
import { useEffect, useRef, useState } from "react"

import type {
  NodeStanding,
  WorkflowNode,
  WorkflowNodeName,
  WorkflowNodeStatus,
} from "@/api/types"
import { NodeEvidence } from "@/features/workflows/evidence"
import { STANDING_LABEL, STANDING_SENTENCE } from "@/features/workflows/node-standing"
import { CHANGE_WASH_DURATION, EASE_STANDARD, useReducedMotion } from "@/lib/motion"

/**
 * What each node does, for a reader who has not read `sync.remediate.nodes`.
 *
 * Typed against `WorkflowNodeName` rather than `string` so that renaming or dropping a node
 * in `WORKFLOW_NODE_ORDER` without updating this object fails the build, instead of quietly
 * rendering `UNKNOWN_NODE` for a node that is not actually unknown.
 */
const PURPOSE: Record<WorkflowNodeName, string> = {
  locate: "Read the finding's call site and vendor change out of the graph, then route the change kind to a remediation tier.",
  prepare: "Clone the repository and install its dependencies with the manager its lockfile names, then ask the language adapter whether a patch here can be verified at all.",
  patch: "Edit the call site. Every re-entry is a fresh attempt, carrying the feedback from whichever stage rejected the last one.",
  static_verify: "Compile the tree a push would carry, with untracked and ignored paths held out, using the clone's own tsc.",
  replay: "Execute the patched call path against a mock of the vendor's new response.",
  push_branch: "Push the branch to the customer's repository.",
  await_ci: "Wait on the customer's own CI. This is the long pole of the whole run.",
  open_pr: "Open the pull request, carrying the spec diff, the changelog entry, the call sites and the CI run as evidence.",
}

/**
 * What a node this file has never heard of says about itself.
 *
 * A payload's `node.name` is a plain `string` -- the transport does not promise it is one of
 * `WorkflowNodeName` -- so a lookup falls back here rather than indexing `PURPOSE` directly.
 * Naming the gap is the point: the payload is still honest, this file is the part that has
 * fallen behind.
 */
const UNKNOWN_NODE =
  "This node is not one the console knows about — the remediation graph has changed since this view was written."

/** `PURPOSE[name]`, or `UNKNOWN_NODE` when the payload names a node this file does not. */
function purposeFor(name: string): string {
  return name in PURPOSE ? PURPOSE[name as WorkflowNodeName] : UNKNOWN_NODE
}

interface Appearance {
  glyph: string
  markerClass: string
  nameClass: string
}

/**
 * How a standing is drawn. The words it is drawn beside are `STANDING_LABEL`'s, not this
 * file's — three appearances carry five standings, because `due` and `due_again` are the same
 * mark and differ in what they say, and so are the two kinds of never-visited.
 */
function appearanceOf(standing: NodeStanding): Appearance {
  switch (standing) {
    case "ran":
      return {
        glyph: "✓",
        markerClass: "border-foreground text-foreground",
        nameClass: "text-foreground",
      }
    case "due":
    case "due_again":
      return {
        glyph: "▶",
        markerClass: "border-foreground bg-foreground text-background",
        nameClass: "text-foreground font-semibold",
      }
    case "not_reached_yet":
    case "never_reached":
      return {
        glyph: "○",
        markerClass: "border-border text-muted-foreground",
        nameClass: "text-muted-foreground",
      }
  }
}

/**
 * A ~600ms wash over a node whose status just changed under a poll — a checkpoint was
 * written. Compares `status` across renders rather than reacting to the poll itself, so an
 * unchanged refetch, or this component's own first mount, washes nothing.
 */
function ChangeWash({ status }: { status: WorkflowNodeStatus }) {
  const reduceMotion = useReducedMotion()
  const mounted = useRef(false)
  const previous = useRef(status)
  const [changeCount, setChangeCount] = useState(0)

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true
      previous.current = status
      return
    }
    if (previous.current !== status) {
      previous.current = status
      setChangeCount((count) => count + 1)
    }
  }, [status])

  if (reduceMotion || changeCount === 0) return null

  return (
    <motion.span
      key={changeCount}
      aria-hidden="true"
      className="absolute inset-0 rounded-full bg-foreground/15"
      initial={{ opacity: 1 }}
      animate={{ opacity: 0 }}
      transition={{ duration: CHANGE_WASH_DURATION, ease: EASE_STANDARD }}
    />
  )
}

function Step({ node, isLast }: { node: WorkflowNode; isLast: boolean }) {
  const look = appearanceOf(node.standing)

  return (
    <li className="grid grid-cols-[auto_1fr] gap-section">
      <div className="flex flex-col items-center">
        <span
          aria-hidden="true"
          className={`relative flex size-7 shrink-0 items-center justify-center rounded-full border text-meta ${look.markerClass}`}
        >
          <ChangeWash status={node.status} />
          {look.glyph}
        </span>
        {!isLast && <span aria-hidden="true" className="w-px flex-1 bg-border" />}
      </div>

      <div className={isLast ? "" : "pb-section"}>
        <div className="flex flex-wrap items-baseline gap-x-row gap-y-field">
          <h3 className={`font-mono text-body ${look.nameClass}`}>{node.name}</h3>
          <p className="text-meta text-muted-foreground">{STANDING_LABEL[node.standing]}</p>
        </div>
        <p className="mt-field max-w-prose text-body text-muted-foreground">
          {purposeFor(node.name)}
        </p>
        {node.standing === "due_again" && (
          <p className="mt-field max-w-prose text-body">{STANDING_SENTENCE.due_again}</p>
        )}
        <NodeEvidence name={node.name} evidence={node.evidence} />
      </div>
    </li>
  )
}

export function NodeSequence({ nodes }: { nodes: WorkflowNode[] }) {
  return (
    <ol className="flex flex-col">
      {nodes.map((node, index) => (
        <Step key={node.name} node={node} isLast={index === nodes.length - 1} />
      ))}
    </ol>
  )
}
