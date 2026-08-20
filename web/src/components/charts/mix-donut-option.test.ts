/**
 * The donut's derivation rules. Scope is `.claude/rules/console-dev-loop.md`'s: classification,
 * derivation and structural invariants — never class names, never a snapshot.
 *
 * Four properties, and each one is a claim the chart makes about the data rather than a styling
 * choice: the centre total is the sum of the arcs, colour is fixed by sorted key rather than by
 * rank, a ninth member folds into a labelled arc rather than silently vanishing, and a fold of
 * exactly one member is not a fold.
 */

import { describe, expect, it } from "vitest"

import { buildMixDonutOption } from "@/components/charts/mix-donut-option"
import type { ChartTokens } from "@/components/charts/echart"

const TOKENS: ChartTokens = {
  ink: "#fff",
  inkSecondary: "#ccc",
  inkMuted: "#999",
  surface: "#111",
  grid: "#222",
  axis: "#333",
  labelOnLight: "#000",
  goodInk: "#3ecf8e",
  warningInk: "#ffb224",
  seriousInk: "#f76b15",
  series: ["s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7"],
}

interface Arc {
  name: string
  value: number
  itemStyle: { color: string }
}

function arcs(option: ReturnType<typeof buildMixDonutOption>): Arc[] {
  const series = (option.series as { data: Arc[] }[])[0]
  return series.data
}

function centreText(option: ReturnType<typeof buildMixDonutOption>) {
  const graphic = option.graphic as { style: { text: string } }[]
  return graphic[0].style.text
}

describe("the mix donut", () => {
  it("puts the sum of its own arcs in the centre, so the two cannot disagree", () => {
    const option = buildMixDonutOption(
      { slices: [{ key: "breaking", value: 7 }, { key: "behavioural", value: 3 }], unit: "findings" },
      TOKENS,
    )

    // The composite this console refuses is a centre figure from a second source. Summing the
    // arcs is what makes the total checkable against the thing drawn around it.
    expect(centreText(option)).toContain("10")
    expect(centreText(option)).toContain("findings")
  })

  it("assigns colour by sorted key, not by rank, so an arc keeps its colour when counts move", () => {
    const first = buildMixDonutOption(
      { slices: [{ key: "a", value: 1 }, { key: "b", value: 99 }], unit: "x" },
      TOKENS,
    )
    const second = buildMixDonutOption(
      { slices: [{ key: "a", value: 99 }, { key: "b", value: 1 }], unit: "x" },
      TOKENS,
    )

    // A reader who learned "aqua is breaking" must not have to relearn it when the counts swap.
    const colourOf = (o: typeof first, name: string) => arcs(o).find((d) => d.name === name)!.itemStyle.color
    expect(colourOf(first, "a")).toBe(colourOf(second, "a"))
    expect(colourOf(first, "b")).toBe(colourOf(second, "b"))
  })

  it("folds past the eighth member into one arc that says how many it holds", () => {
    const slices = Array.from({ length: 11 }, (_, i) => ({ key: `k${i}`, value: i + 1 }))

    const option = buildMixDonutOption({ slices, unit: "rows" }, TOKENS)

    // Eight arcs at most, and the last names its member count -- a reader is never told the
    // set is smaller than it is.
    expect(arcs(option)).toHaveLength(8)
    expect(arcs(option)[7].name).toBe("4 others")
    // And the fold is still counted: the centre total covers every member, folded or not.
    expect(centreText(option)).toContain(String(slices.reduce((s, x) => s + x.value, 0)))
  })

  it("does not fold a single overflow member into an 'others' arc naming one thing", () => {
    const slices = Array.from({ length: 8 }, (_, i) => ({ key: `k${i}`, value: 1 }))

    const option = buildMixDonutOption({ slices, unit: "rows" }, TOKENS)

    // Exactly eight fits. "1 others" would be a worse label than the member's own name, and
    // hiding a named member behind a count loses information for nothing.
    expect(arcs(option)).toHaveLength(8)
    expect(arcs(option).map((d) => d.name)).not.toContain("1 others")
  })
})
