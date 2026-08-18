/**
 * Tool output as addressed records rather than a wall of text.
 *
 * `tsc` writes one diagnostic per line and names the file and the line it is about; the replay
 * writes its evidence the same way. Lifting that address out and setting it beside the message
 * gives a reviewer the one thing they came for — *where* — without changing a character of what
 * the tool said.
 *
 * **Nothing here links out, and that is a limit rather than an oversight.** An anchor is an address
 * into the customer's own repository at the commit the run patched. This console holds no checkout
 * of that tree and no forge URL for it, so an anchor is rendered as text a reviewer copies. A link
 * would have to guess a host, a ref and a root, and a link that lands on the wrong line is worse
 * than an address that lands nowhere.
 *
 * Long spans collapse to `VISIBLE_LINE_BUDGET` with a control that states the full count. A
 * truncation a reader cannot see is the failure this avoids: `tsc` reporting sixty diagnostics and
 * the screen showing twelve, with nothing saying so, reads as a run that produced twelve.
 */

import { useState } from "react"

import {
  VISIBLE_LINE_BUDGET,
  anchorLabel,
  codeLines,
  needsDisclosure,
  visibleLines,
} from "@/features/workflows/code-anchors"

export function CodeBlock({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false)
  const lines = codeLines(text)
  const shown = visibleLines(lines, expanded)
  const disclose = needsDisclosure(lines)

  return (
    <div className="flex min-w-0 flex-col gap-row">
      <ol className="flex min-w-0 flex-col overflow-x-auto font-mono text-meta">
        {shown.map((line, index) => (
          <li
            key={index}
            className="flex min-w-0 flex-wrap items-baseline gap-row py-field whitespace-pre-wrap"
          >
            {line.anchor !== null && (
              <span className="shrink-0 text-foreground select-all">{anchorLabel(line.anchor)}</span>
            )}
            <span className="min-w-0 text-ink-muted">{line.text}</span>
          </li>
        ))}
      </ol>
      {disclose && (
        <div className="flex flex-wrap items-baseline gap-row">
          <button
            type="button"
            aria-expanded={expanded}
            onClick={() => setExpanded((value) => !value)}
            className="furniture text-meta text-ink-muted hover:text-foreground"
          >
            {expanded ? "Show fewer" : `Show all ${lines.length} lines`}
          </button>
          {!expanded && (
            <span className="text-meta text-ink-muted">
              {`Showing the first ${VISIBLE_LINE_BUDGET} of ${lines.length} lines the tool wrote.`}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
