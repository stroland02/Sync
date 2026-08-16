/**
 * The console's one echarts wrapper. Every colour, ink and gridline value is read
 * from `getComputedStyle(document.documentElement)` rather than passed in as a
 * literal, so a chart built anywhere in the console repaints from the same tokens
 * `index.css` declares — a chart carrying its own hardcoded palette would be a
 * second design system.
 *
 * `getComputedStyle` on a custom property returns the declared text verbatim (the
 * ramp in `index.css` is written as `oklch(...)`, and that comment there is why),
 * and zrender's colour parser does not read that syntax. Each value is round-tripped
 * through a canvas 2D context instead: `CanvasRenderingContext2D.fillStyle`'s getter
 * is spec-required to normalise any legal CSS colour to hex or `rgba()`, which
 * zrender does read.
 */
import { useEffect, useMemo, useState } from "react"
import type { CSSProperties } from "react"
import ReactECharts from "echarts-for-react"
import type { EChartsOption } from "echarts-for-react"

export interface ChartTokens {
  ink: string
  inkSecondary: string
  inkMuted: string
  surface: string
  grid: string
  axis: string
  labelOnLight: string
  /** Fixed slot order, index 0 is series-1. Never reassigned by value or reversed. */
  series: string[]
}

const TOKEN_PROPERTIES = {
  ink: "--color-ink",
  inkSecondary: "--color-ink-secondary",
  inkMuted: "--color-ink-muted",
  surface: "--color-surface",
  grid: "--color-chart-grid",
  axis: "--color-chart-axis",
  labelOnLight: "--color-chart-label-on-light",
} as const

const SERIES_PROPERTIES = Array.from({ length: 8 }, (_, i) => `--color-series-${i + 1}`)

let resolveCtx: CanvasRenderingContext2D | null = null

function resolveColor(raw: string): string {
  if (!raw) return raw
  if (!resolveCtx) {
    resolveCtx = document.createElement("canvas").getContext("2d")
  }
  if (!resolveCtx) return raw
  resolveCtx.fillStyle = raw
  return resolveCtx.fillStyle
}

function readTokens(): ChartTokens {
  const computed = getComputedStyle(document.documentElement)
  const read = (property: string) => resolveColor(computed.getPropertyValue(property).trim())
  return {
    ink: read(TOKEN_PROPERTIES.ink),
    inkSecondary: read(TOKEN_PROPERTIES.inkSecondary),
    inkMuted: read(TOKEN_PROPERTIES.inkMuted),
    surface: read(TOKEN_PROPERTIES.surface),
    grid: read(TOKEN_PROPERTIES.grid),
    axis: read(TOKEN_PROPERTIES.axis),
    labelOnLight: read(TOKEN_PROPERTIES.labelOnLight),
    series: SERIES_PROPERTIES.map(read),
  }
}

export interface EChartProps {
  /** Builds the option from the current theme tokens. Called again on every repaint. */
  buildOption: (tokens: ChartTokens) => EChartsOption
  ariaLabel: string
  style?: CSSProperties
  className?: string
}

/**
 * Watches `class` on `<html>` rather than `prefers-color-scheme`: the theme switch
 * this console ships writes `.dark` there directly, and following the OS setting
 * instead would leave the chart out of step with an operator who overrode it.
 */
export function EChart({ buildOption, ariaLabel, style, className }: EChartProps) {
  const [tokens, setTokens] = useState<ChartTokens>(() => readTokens())

  useEffect(() => {
    const observer = new MutationObserver(() => setTokens(readTokens()))
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    })
    return () => observer.disconnect()
  }, [])

  const option = useMemo(() => buildOption(tokens), [buildOption, tokens])

  return (
    <ReactECharts
      option={option}
      notMerge
      autoResize
      style={style}
      className={className}
      role="img"
      aria-label={ariaLabel}
    />
  )
}
