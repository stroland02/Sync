/**
 * The two text problems every chart in this console has, in one place because there are now
 * two charts. `CLAUDE.md` factors at the second use rather than the third: the third is where
 * the two copies have already drifted, and a drifted copy of `labelInkFor` is an illegible
 * label on one chart and not the other, which reads as a rendering bug rather than as a
 * duplicated rule.
 *
 * Both were `corpus-chart.tsx`'s, and its own comments carried the arguments below.
 */

/**
 * Below this share a segment rarely has room for a name and a count inside a bar this
 * console's size. Below the floor the value stays reachable through the legend, the tooltip,
 * and the table beneath the chart rather than being clipped — there is no layout pass
 * available here to measure the rendered text before the option is built, so this is a
 * documented approximation of a fit check, not a fit check.
 */
export const INLINE_LABEL_SHARE_FLOOR = 0.15

/**
 * Escapes a value the graph wrote before it reaches an echarts tooltip.
 *
 * A tooltip formatter returns an HTML string, so a detector name, a rung or a vendor
 * operation — every one of them a string this console did not author — is markup unless it is
 * escaped here first.
 */
export function escapeHtml(value: string): string {
  return value.replace(
    /[&<>"']/g,
    (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]!,
  )
}

let luminanceCtx: CanvasRenderingContext2D | null = null

/**
 * White or the chart's own ink, picked by the fill's luminance, so a label set inside a light
 * categorical segment (aqua, yellow) never renders illegible text on itself — the one case
 * `marks-and-anatomy.md` carries as an exception to "text never wears the data colour".
 *
 * `DESIGN.md`'s *Chart chrome* section carries the arithmetic, including the named exception:
 * slot 4 (`#008300`) clears 5.05:1 against neither ink, which is why every chart using this
 * also withholds an inline label from a segment too thin to hold one and restates the value in
 * a legend, a tooltip and a table.
 */
export function labelInkFor(fill: string, ink: string, labelOnLight: string): string {
  if (!luminanceCtx) luminanceCtx = document.createElement("canvas").getContext("2d")
  if (!luminanceCtx) return ink
  luminanceCtx.fillStyle = fill
  luminanceCtx.fillRect(0, 0, 1, 1)
  const [r, g, b] = luminanceCtx.getImageData(0, 0, 1, 1).data
  const linear = (channel: number) => {
    const s = channel / 255
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
  }
  const luminance = 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
  return luminance > 0.45 ? ink : labelOnLight
}
