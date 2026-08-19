/**
 * Pan/zoom/fit arithmetic for an SVG canvas addressed by a `viewBox`, shared by every canvas this
 * console draws. Extracted from `graph-layout.ts` when `file-tree-canvas.tsx` replaced
 * `dependency-canvas.tsx` -- this module has no opinion about what a node means.
 */

export interface Bounds {
  x: number
  y: number
  width: number
  height: number
}

export type Viewport = Bounds

/** The margin `fitViewport` frames a graph's bounds with. */
export const CANVAS_PADDING = 64

export const MAX_ZOOM_IN = 4
export const MAX_ZOOM_OUT = 2

/** The whole graph, framed. */
export function fitViewport(bounds: Bounds): Viewport {
  return {
    x: bounds.x - CANVAS_PADDING,
    y: bounds.y - CANVAS_PADDING,
    width: bounds.width + 2 * CANVAS_PADDING,
    height: bounds.height + 2 * CANVAS_PADDING,
  }
}

/**
 * The smallest a graph row may render before the picture stops being readable, in CSS pixels.
 *
 * Measured against the failure it exists to prevent: a codebase with 165 call sites lays out
 * several thousand graph units tall, and fitting that into a 576px canvas renders a 28-unit row
 * at about three pixels — a grey texture rather than a graph. Ten pixels is the floor at which a
 * row still reads as a row; below it a reader is zooming blind.
 */
export const MIN_LEGIBLE_ROW_PX = 10

/**
 * The view a large graph should *open* at: fitted when fitting is legible, and otherwise the
 * top-left corner at the scale where a row still reads.
 *
 * **Fit-to-everything is the wrong default past a certain size, and this is the arithmetic that
 * says where.** A picture that shows the whole codebase illegibly answers no question; one that
 * shows part of it legibly answers a question and says how much it is showing. The minimap and
 * the truncation notice carry the rest, which is why opening zoomed in is honest rather than
 * hiding anything.
 *
 * `rowHeight` is the layout's own row unit and `canvasHeightPx` the height the canvas actually
 * renders at, so the decision is made in the units a reader sees rather than in graph space.
 */
export function readableViewport(
  fit: Viewport,
  { rowHeight, canvasHeightPx }: { rowHeight: number; canvasHeightPx: number },
): Viewport {
  const fittedRowPx = (rowHeight / fit.height) * canvasHeightPx
  if (fittedRowPx >= MIN_LEGIBLE_ROW_PX) return fit

  const height = (rowHeight * canvasHeightPx) / MIN_LEGIBLE_ROW_PX
  const width = fit.width * (height / fit.height)
  // Anchored at the graph's own top-left rather than its centre: a file tree is read from the
  // top down, and opening in the middle of one drops a reader into an unlabelled interior.
  return { x: fit.x, y: fit.y, width, height }
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high)
}

/** How large a row may render before zooming in further only wastes the canvas. */
export const MAX_LEGIBLE_ROW_PX = 72

/**
 * Zoom about the view's own centre, bounded in the units a reader sees.
 *
 * **The limits used to be multiples of the fitted view, and that is the defect this replaces.**
 * `fit / 4` is plenty of zoom on a graph with three nodes and nowhere near enough on one with
 * three hundred: the cap scaled with the problem, so a large codebase could never be zoomed to
 * a legible scale at all — measured by the owner on a tree whose rows fitted at about three
 * pixels. Expressed in pixels per row instead, "as far in as is useful" and "no further out
 * than the whole graph" mean the same thing on every codebase.
 *
 * `scale` carries the row unit and the canvas height; omitted, the old relative bounds apply,
 * which keeps a caller that has no canvas measurement working rather than unbounded.
 */
export function zoomViewport(
  view: Viewport,
  factor: number,
  fit: Viewport,
  scale?: { rowHeight: number; canvasHeightPx: number },
): Viewport {
  let low = fit.width / MAX_ZOOM_IN
  let high = fit.width * MAX_ZOOM_OUT
  if (scale !== undefined) {
    const aspect = view.width / view.height
    // A view this tall renders one row at MAX_LEGIBLE_ROW_PX; anything narrower is more zoom
    // than the picture can use.
    low = ((scale.rowHeight * scale.canvasHeightPx) / MAX_LEGIBLE_ROW_PX) * aspect
    // Out to the whole graph and no further: past the fit there is nothing left to reveal.
    high = Math.max(fit.width, low)
  }
  const width = clamp(view.width / factor, low, high)
  const height = view.height * (width / view.width)
  const centreX = view.x + view.width / 2
  const centreY = view.y + view.height / 2
  return { x: centreX - width / 2, y: centreY - height / 2, width, height }
}

/** Pan by a delta already converted into graph units, with the view's centre held inside the graph. */
export function panViewport(view: Viewport, dx: number, dy: number, fit: Viewport): Viewport {
  const centreX = clamp(view.x + view.width / 2 + dx, fit.x, fit.x + fit.width)
  const centreY = clamp(view.y + view.height / 2 + dy, fit.y, fit.y + fit.height)
  return { x: centreX - view.width / 2, y: centreY - view.height / 2, width: view.width, height: view.height }
}
