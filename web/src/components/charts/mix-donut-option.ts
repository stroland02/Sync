/**
 * A mix over a closed vocabulary, as a donut. The owner's form ruling of 2026-08-19.
 *
 * **What a donut may show here, and what it may not.** A donut asserts share-of-whole, so it is
 * permitted only where the parts genuinely sum to the whole and the whole is a real total the
 * page can name: severity across a finding set, rung across a binding set. It is never used for
 * a ranking — `ranked-bars.tsx` owns those, because a donut makes small members unreadable and
 * two similar arcs impossible to compare. It is never used where the parts overlap, and never
 * where members can be absent-versus-zero, because an arc cannot draw the difference.
 *
 * **The centre carries the total, and the total is the sum of the arcs.** Not a second query, not
 * a figure from another payload — a donut whose centre disagrees with its parts is the composite
 * this console refuses, wearing a shape that hides it. `buildMixDonutOption` sums what it is
 * given, so the two cannot drift.
 *
 * **Colour is slot order, never meaning.** `DESIGN.md` owns the eight series slots and they are
 * assigned by sorted key so one severity is the same colour on every screen that draws it. No
 * slot is red-for-bad: colour here separates members, and the label says which is which. A
 * status colour would be the traffic light `CLAUDE.md` refuses.
 *
 * **A ninth member folds into one arc rather than reaching for a ninth colour**, which is the
 * same rule `lib/palette.ts` applies to every scale — and the folded arc is labelled with its
 * member count so a reader is never told a set is smaller than it is.
 */

import type { EChartsOption } from "echarts"

import type { ChartTokens } from "@/components/charts/echart"
import { escapeHtml } from "@/components/charts/chart-text"

export interface MixSlice {
  readonly key: string
  readonly value: number
}

/** Beyond this, members fold into one arc — the palette declares eight slots and no more. */
const MAX_ARCS = 8

export interface MixDonutInput {
  /** Already-counted members. Order is irrelevant; this sorts by key for stable colour. */
  readonly slices: readonly MixSlice[]
  /** What one unit is, for the centre label — "findings", "call sites". */
  readonly unit: string
}

export function buildMixDonutOption(input: MixDonutInput, tokens: ChartTokens): EChartsOption {
  // Sorted by key, not by value: colour must not move when a count changes, or a reader who
  // learned "this arc is breaking" relearns it every time the data shifts. `ranked-bars` sorts
  // by value because a ranking's whole claim is the order; a mix's is not.
  const sorted = [...input.slices].sort((a, b) => a.key.localeCompare(b.key))
  const kept = sorted.slice(0, MAX_ARCS - 1)
  const folded = sorted.slice(MAX_ARCS - 1)
  const arcs =
    folded.length > 1
      ? [
          ...kept,
          {
            key: `${folded.length} others`,
            value: folded.reduce((sum, slice) => sum + slice.value, 0),
          },
        ]
      : sorted

  const total = arcs.reduce((sum, arc) => sum + arc.value, 0)

  return {
    textStyle: { color: tokens.inkSecondary },
    tooltip: {
      trigger: "item",
      // Percent alongside the count, never instead of it. A share with no denominator is the
      // figure a reader cannot check. `escapeHtml` because a formatter returns markup and every
      // member name here was written by the graph rather than by this console.
      formatter: (params: unknown) => {
        const p = params as { name: string; value: number }
        const share = total === 0 ? 0 : Math.round((p.value / total) * 100)
        return `${escapeHtml(p.name)}<br/>${p.value.toLocaleString()} ${escapeHtml(input.unit)} · ${share}% of ${total.toLocaleString()}`
      },
    },
    legend: {
      orient: "vertical",
      right: 0,
      top: "middle",
      textStyle: { color: tokens.inkSecondary },
      // The count travels with the name, so the legend is readable without hovering every arc.
      formatter: (name: string) => {
        const arc = arcs.find((a) => a.key === name)
        return arc === undefined ? name : `${name}  ${arc.value.toLocaleString()}`
      },
    },
    series: [
      {
        type: "pie",
        // A true donut rather than a pie: the hole is where the total goes, and the total is
        // what stops the arcs being read as a share of something unstated.
        radius: ["58%", "82%"],
        center: ["34%", "50%"],
        avoidLabelOverlap: true,
        itemStyle: {
          borderColor: tokens.surface,
          borderWidth: 2,
        },
        // No label on the arc itself. At eight members the labels collide, and a chart that
        // drops the ones that collide is silently incomplete -- the legend carries every one.
        label: { show: false },
        labelLine: { show: false },
        emphasis: {
          // Scale only. No shadow and no colour change: emphasis says "this one", and a
          // recoloured arc on hover says something about the value instead.
          scale: true,
          scaleSize: 4,
        },
        data: arcs.map((arc, index) => ({
          name: arc.key,
          value: arc.value,
          itemStyle: { color: tokens.series[index % tokens.series.length] },
        })),
      },
    ],
    graphic: [
      {
        type: "text",
        left: "34%",
        top: "middle",
        style: {
          text: `${total.toLocaleString()}\n${input.unit}`,
          align: "center",
          fill: tokens.ink,
          fontSize: 22,
          lineHeight: 24,
        },
      },
    ],
  }
}
