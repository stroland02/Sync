/**
 * `file:line` anchors, read off the block channels a run actually produces.
 *
 * `diagnostics` is `tsc`'s own output and `replay_evidence` is the replay's; both are line-per-
 * record, and a reviewer reading either is looking for *where*. Pulling the path and line out of
 * the line turns a wall of text into a set of addressed records without changing a character of
 * what the tool said — the remainder of the line is carried through verbatim.
 *
 * **A line the tool did not anchor gets no anchor.** There is no repository root here, no source
 * map, and no way to attribute an unanchored continuation line to the diagnostic above it without
 * guessing; a guessed anchor is worse than none, because it sends a reviewer to a line the
 * compiler never named.
 *
 * `tsc` emits two forms depending on `--pretty`, and both are parsed: `path(line,col): ...` and
 * `path:line:col - ...`.
 */

export interface CodeAnchor {
  path: string
  line: number
  column: number | null
}

export interface CodeLine {
  /** What is left of the line once the anchor is lifted out. Unchanged when there is none. */
  text: string
  anchor: CodeAnchor | null
}

/** How many lines a block shows before a reader has to ask for the rest. */
export const VISIBLE_LINE_BUDGET = 12

const PAREN = /^(\S.*?)\((\d+),(\d+)\):\s*(.*)$/
const COLON = /^(\S+?):(\d+):(\d+)\s*(?:-\s*)?(.*)$/

function parse(raw: string): CodeLine {
  const paren = PAREN.exec(raw)
  if (paren !== null) {
    return {
      text: paren[4],
      anchor: { path: paren[1], line: Number(paren[2]), column: Number(paren[3]) },
    }
  }
  const colon = COLON.exec(raw)
  if (colon !== null) {
    return {
      text: colon[4],
      anchor: { path: colon[1], line: Number(colon[2]), column: Number(colon[3]) },
    }
  }
  return { text: raw, anchor: null }
}

/** One entry per line of the block, in the order the tool wrote them. */
export function codeLines(text: string): CodeLine[] {
  return text.replace(/\r\n/g, "\n").split("\n").map(parse)
}

/** Whether the block is long enough that collapsing it hides something. */
export function needsDisclosure(lines: CodeLine[]): boolean {
  return lines.length > VISIBLE_LINE_BUDGET
}

/** What renders: the whole block when expanded, the first `VISIBLE_LINE_BUDGET` lines otherwise. */
export function visibleLines(lines: CodeLine[], expanded: boolean): CodeLine[] {
  return expanded ? lines : lines.slice(0, VISIBLE_LINE_BUDGET)
}

/** The anchor as a reviewer writes it down: `path:line`. The column is not part of an address. */
export function anchorLabel(anchor: CodeAnchor): string {
  return `${anchor.path}:${anchor.line}`
}
