/**
 * A bounded window of source, numbered from where it sits in its file, with the subject line
 * marked.
 *
 * Renders only what the graph captured — the component takes text, never a path to fetch, so
 * no screen can grow a "show more" that reads past the window the index recorded. The mark is
 * a background step plus a marker character, never colour alone.
 *
 * Three states, because absence has two causes the API distinguishes (`source_served`):
 * a window, "withheld by policy", and "not captured by the index pass that wrote this row".
 * The caller says which nothing it has; this renders whichever it is handed.
 */

export function CodeSnippet({
  code,
  startLine,
  markLine,
  label,
}: {
  /** The captured window, exactly as the index recorded it. */
  code: string
  /** 1-based file line of the window's first line. */
  startLine: number
  /** The 1-based file line to mark, or null for an unmarked window. */
  markLine?: number | null
  /** What this window is, for the accessible name — "Call site, src/billing.ts". */
  label: string
}) {
  const lines = code.split("\n")
  return (
    <div
      role="figure"
      aria-label={label}
      className="overflow-x-auto rounded-control border border-line bg-surface"
    >
      <table className="w-full border-collapse font-mono text-meta leading-relaxed">
        <tbody>
          {lines.map((text, index) => {
            const fileLine = startLine + index
            const marked = markLine != null && fileLine === markLine
            return (
              <tr
                key={fileLine}
                data-line={fileLine}
                data-marked={marked || undefined}
                className={marked ? "bg-surface-emphasis" : undefined}
              >
                <td
                  aria-hidden="true"
                  className="select-none border-r border-line px-row text-right text-ink-muted"
                >
                  {marked ? "▸" : ""} {fileLine}
                </td>
                <td className="whitespace-pre px-row text-ink">{text}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/**
 * The sentence for a missing window, naming which nothing it is. Shared so two screens cannot
 * describe one policy in two ways.
 */
export function absentSnippetReason(sourceServed: boolean): string {
  return sourceServed
    ? "No window captured for this row — it was indexed before snippet capture existed. The next index pass captures one."
    : "This deployment does not serve source (SYNC_SERVE_SOURCE is off), so the recorded shape below is the whole answer."
}
