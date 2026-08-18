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
