/**
 * What the indexing canvas is looking at, decided once rather than at each render site.
 *
 * **This screen used to render one nothing for two facts, and its own empty state admitted it**:
 * "a repository the index never ran against shows the same nothing as one that calls no vendor".
 * That was true of the payload at the time. `indexed_at` (`CI-W403`) makes the two expressible,
 * and this is where the console stops conflating them.
 *
 * The two are different answers to a reader deciding whether to trust the picture. *Never
 * recorded* means the graph holds nothing about this repository and the canvas is not evidence
 * about the codebase at all. *Indexed and found none* means the index ran, wrote here, and drew
 * no vendor call — a measurement, and a claim about the code.
 *
 * **Off-path is its own axis, not a third kind.** A repository whose call sites were all
 * retracted still has observed traffic and unattributed findings, so evidence can exist with no
 * static binding to draw. `offPathTotal` travels with every state rather than only the drawn one,
 * because "nothing here" would otherwise drop what the graph is holding.
 */

import type { RepositoryGraphResponse } from "@/api/types"

export type IndexStateKind = "never-recorded" | "indexed-empty" | "drawn"

export interface IndexState {
  readonly kind: IndexStateKind
  /** When the index last wrote a call site here, or `null` when it never has. */
  readonly indexedAt: string | null
  /** Bindings the canvas cannot draw as edges. A measured count, never an absence. */
  readonly offPathTotal: number
}

export function classifyIndexState(graph: RepositoryGraphResponse): IndexState {
  const offPathTotal = graph.off_path.unresolved + graph.off_path.unattributed

  if (graph.indexed_at === null) {
    return { kind: "never-recorded", indexedAt: null, offPathTotal }
  }
  if (graph.bindings.length === 0) {
    return { kind: "indexed-empty", indexedAt: graph.indexed_at, offPathTotal }
  }
  return { kind: "drawn", indexedAt: graph.indexed_at, offPathTotal }
}
