/**
 * What a vendor operation's response has actually been seen to contain.
 *
 * Not scoped to this repository in the underlying table — a shape is a fact about what the
 * vendor sends, not about who calls it. `graph_views.observed_telemetry` joins this list in
 * through the `(vendor_id, operation_id)` pairs this repository's own observed calls name, so
 * an operation this repository has never correlated a call to has no row here even if the
 * vendor's other customers see traffic against it.
 */

import type { ObservedShapeRow } from "@/api/types"
import { Absent, Formatted } from "@/components/status"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatTimestamp, orAbsent } from "@/lib/format"

export function ObservedShapesTable({ shapes }: { shapes: ObservedShapeRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Operation</TableHead>
          <TableHead>Field</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Nullable seen</TableHead>
          <TableHead>Enum values</TableHead>
          <TableHead>Source</TableHead>
          <TableHead>Samples</TableHead>
          <TableHead>Observed</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {shapes.map((shape, index) => (
          <TableRow key={`${shape.vendor_id}-${shape.operation_id}-${shape.field_path}-${index}`}>
            <TableCell className="font-mono">
              {shape.vendor_id} · {shape.operation_id}
            </TableCell>
            <TableCell className="font-mono">{shape.field_path}</TableCell>
            <TableCell className="font-mono">{shape.json_type}</TableCell>
            <TableCell>{shape.nullable_seen ? "yes" : "no"}</TableCell>
            <TableCell className="font-mono">
              {shape.spec_enum_values.length === 0 ? (
                <Absent />
              ) : (
                shape.spec_enum_values.join(", ")
              )}
            </TableCell>
            <TableCell>
              <Formatted value={orAbsent(shape.source)} />
            </TableCell>
            <TableCell className="font-mono">{shape.sample_count.toLocaleString()}</TableCell>
            <TableCell className="font-mono text-meta">
              <Formatted value={formatTimestamp(shape.first_seen)} /> →{" "}
              <Formatted value={formatTimestamp(shape.last_seen)} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
