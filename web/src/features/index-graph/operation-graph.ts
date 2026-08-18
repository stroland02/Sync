/**
 * The indexing canvas's three levels: file -> operation -> vendor.
 *
 * **Why three and not two.** The canvas drew file -> vendor and hung the rung on that edge. But
 * that hop spans two bindings — the static index binding a call site to an operation, and the
 * operation belonging to a vendor — so a rung on it named neither precisely. With the operation
 * on screen, every edge carries the rung it was actually established at, which is the sentence
 * this screen exists to make true.
 *
 * **Why file-first and not vendor-first.** The dispatch asked for vendor -> operation -> call
 * site, which is the shape owner decision 8 names and rejects: "the file tree with edges out to
 * vendors... framed as *your codebase*, not as Sync's model of it... this is a different build
 * from the schema-visualiser shape". The ruling was to reconcile rather than revert — keep the
 * reader's own codebase as the entry point and insert the level the dispatch was really after.
 * `src/api/billing.ts -> PostCharges -> stripe` reads as the reader's code reaching outward,
 * which vendor-first does not.
 *
 * **An operation is identified by its vendor as well as its id.** Two vendors may both publish
 * `Charge`, and merging them would draw one node for two unrelated operations and route a
 * repository's exposure to the wrong company.
 *
 * **A binding naming no operation is unroutable, not absent.** There is no node to draw it to and
 * inventing one would put a name on screen that no payload carries. It leaves by `unroutable` so
 * the canvas can say the graph holds it, which is the same rule `off_path` follows one level up.
 *
 * No layout here. Where a node lands is the renderer's problem, the separation `file-tree-graph.ts`
 * already draws between deriving and placing.
 */

import { BINDING_SOURCES, type BindingSource } from "@/api/types"

/** One indexed or observed binding, flattened to the four fields this graph needs. */
export interface CallBindingRow {
  file: string
  vendorId: string
  operationId: string
  rung: BindingSource
}

export interface OperationNode {
  operationId: string
  vendorId: string
}

export interface VendorNode {
  vendorId: string
}

/** A call site reaching an operation. The rung is the binding the static index or a correlator made. */
export interface FileOperationEdge {
  file: string
  operationId: string
  vendorId: string
  rungs: BindingSource[]
}

/** An operation belonging to a vendor, carrying the rungs the bindings beneath it were made at. */
export interface OperationVendorEdge {
  operationId: string
  vendorId: string
  rungs: BindingSource[]
}

/** A binding the canvas cannot route, because it names no operation to route through. */
export interface UnroutableBinding {
  file: string
  vendorId: string
  rungs: BindingSource[]
}

export interface OperationGraph {
  vendors: VendorNode[]
  operations: OperationNode[]
  fileEdges: FileOperationEdge[]
  vendorEdges: OperationVendorEdge[]
  unroutable: UnroutableBinding[]
}

function rungOrder(rung: BindingSource): number {
  const index = BINDING_SOURCES.indexOf(rung)
  return index === -1 ? BINDING_SOURCES.length : index
}

function sortRungs(rungs: Set<BindingSource>): BindingSource[] {
  return [...rungs].sort((a, b) => rungOrder(a) - rungOrder(b))
}

/**
 * Nested maps rather than joined string keys throughout: a file path, an operation id and a
 * vendor id may each legally contain whatever separator this module might pick, and a key
 * collision between two distinct triples would silently merge their rungs — which is the one
 * error this graph must not make, since a merged rung is a claim about evidence.
 */
export function buildOperationGraph(
  rows: CallBindingRow[],
  knownVendorIds: string[] = [],
): OperationGraph {
  const vendorIds = new Set<string>(knownVendorIds)
  const operations = new Map<string, Set<string>>()
  const fileRungs = new Map<string, Map<string, Map<string, Set<BindingSource>>>>()
  const vendorRungs = new Map<string, Map<string, Set<BindingSource>>>()
  const unroutableRungs = new Map<string, Map<string, Set<BindingSource>>>()

  for (const binding of rows) {
    vendorIds.add(binding.vendorId)

    if (binding.operationId === "") {
      const byVendor = unroutableRungs.get(binding.file) ?? new Map<string, Set<BindingSource>>()
      unroutableRungs.set(binding.file, byVendor)
      const rungs = byVendor.get(binding.vendorId) ?? new Set<BindingSource>()
      rungs.add(binding.rung)
      byVendor.set(binding.vendorId, rungs)
      continue
    }

    const vendorOperations = operations.get(binding.vendorId) ?? new Set<string>()
    vendorOperations.add(binding.operationId)
    operations.set(binding.vendorId, vendorOperations)

    const byVendor = fileRungs.get(binding.file) ?? new Map<string, Map<string, Set<BindingSource>>>()
    fileRungs.set(binding.file, byVendor)
    const byOperation = byVendor.get(binding.vendorId) ?? new Map<string, Set<BindingSource>>()
    byVendor.set(binding.vendorId, byOperation)
    const rungs = byOperation.get(binding.operationId) ?? new Set<BindingSource>()
    rungs.add(binding.rung)
    byOperation.set(binding.operationId, rungs)

    const vendorByOperation = vendorRungs.get(binding.vendorId) ?? new Map<string, Set<BindingSource>>()
    vendorRungs.set(binding.vendorId, vendorByOperation)
    const upward = vendorByOperation.get(binding.operationId) ?? new Set<BindingSource>()
    upward.add(binding.rung)
    vendorByOperation.set(binding.operationId, upward)
  }

  const operationNodes = [...operations.entries()]
    .flatMap(([vendorId, ids]) => [...ids].map((operationId) => ({ operationId, vendorId })))
    .sort((a, b) => a.operationId.localeCompare(b.operationId) || a.vendorId.localeCompare(b.vendorId))

  const fileEdges = [...fileRungs.entries()]
    .flatMap(([file, byVendor]) =>
      [...byVendor.entries()].flatMap(([vendorId, byOperation]) =>
        [...byOperation.entries()].map(([operationId, rungs]) => ({
          file,
          operationId,
          vendorId,
          rungs: sortRungs(rungs),
        })),
      ),
    )
    .sort(
      (a, b) =>
        a.file.localeCompare(b.file) ||
        a.operationId.localeCompare(b.operationId) ||
        a.vendorId.localeCompare(b.vendorId),
    )

  const vendorEdges = [...vendorRungs.entries()]
    .flatMap(([vendorId, byOperation]) =>
      [...byOperation.entries()].map(([operationId, rungs]) => ({
        operationId,
        vendorId,
        rungs: sortRungs(rungs),
      })),
    )
    .sort((a, b) => a.vendorId.localeCompare(b.vendorId) || a.operationId.localeCompare(b.operationId))

  const unroutable = [...unroutableRungs.entries()]
    .flatMap(([file, byVendor]) =>
      [...byVendor.entries()].map(([vendorId, rungs]) => ({
        file,
        vendorId,
        rungs: sortRungs(rungs),
      })),
    )
    .sort((a, b) => a.file.localeCompare(b.file) || a.vendorId.localeCompare(b.vendorId))

  return {
    vendors: [...vendorIds].sort().map((vendorId) => ({ vendorId })),
    operations: operationNodes,
    fileEdges,
    vendorEdges,
    unroutable,
  }
}
