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

/**
 * Zoom about the view's own centre, bounded at both ends.
 *
 * The limits are relative to the fitted view rather than absolute, so they mean the same thing on
 * a graph with three nodes and on one with three hundred.
 */
export function zoomViewport(view: Viewport, factor: number, fit: Viewport): Viewport {
  const width = clamp(view.width / factor, fit.width / MAX_ZOOM_IN, fit.width * MAX_ZOOM_OUT)
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
