/**
 * The schema-driven staging editor (B195): one renderer for every vendor's staging fields.
 *
 * The adapter declares what it needs as typed fields — a title, a description, a shape — and
 * this component draws whatever arrives. The closing evidence for B195 is that Twilio's
 * product list is edited here with no Twilio-specific component: a second vendor declaring a
 * field costs its schema entry and nothing in `web/src`.
 *
 * A vendor with an empty schema renders one sentence rather than nothing: "nothing to
 * configure" is an answer, and a silent absence would read as a screen that failed to load.
 */

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { InfoHint } from "@/components/info-hint"
import { ErrorState, LoadingState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  ApiStatusError,
  MalformedResponseError,
  UnreachableApiError,
} from "@/api/errors"

interface StagingColumn {
  key: string
  title: string
  example?: string
}

interface StagingField {
  key: string
  title: string
  description: string
  type: "string" | "table"
  writable: boolean
  columns?: StagingColumn[]
}

interface StagingResponse {
  vendor_id: string
  schema: StagingField[]
  values: Record<string, unknown>
  stale_symbols?: string | null
}

async function fetchStaging(vendorId: string, signal?: AbortSignal): Promise<StagingResponse> {
  const path = `/api/adapters/${encodeURIComponent(vendorId)}/staging`
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (!response.ok) throw new ApiStatusError(response.status, path)
  try {
    return (await response.json()) as StagingResponse
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}

async function updateStaging(
  vendorId: string,
  payload: Record<string, unknown>,
): Promise<StagingResponse> {
  const path = `/api/adapters/${encodeURIComponent(vendorId)}/staging`
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    let detail = `the staging write answered ${response.status}`
    try {
      const body = (await response.json()) as { error?: string }
      if (body.error) detail = body.error
    } catch {
      // the status is the message
    }
    throw new Error(detail)
  }
  return (await response.json()) as StagingResponse
}

type TableRows = Record<string, string>[]

function TableField({
  vendorId,
  field,
  rows,
}: {
  vendorId: string
  field: StagingField
  rows: TableRows
}) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<TableRows | null>(null)
  const [staleNote, setStaleNote] = useState<string | null>(null)
  const shown = draft ?? rows
  const columns = field.columns ?? []

  const mutation = useMutation({
    mutationFn: (next: TableRows) => updateStaging(vendorId, { [field.key]: next }),
    onSuccess: (data) => {
      setDraft(null)
      setStaleNote(data.stale_symbols ?? null)
      queryClient.setQueryData(["adapter-staging", vendorId], data)
    },
  })

  function setCell(rowIndex: number, key: string, value: string) {
    const next = shown.map((row, index) => (index === rowIndex ? { ...row, [key]: value } : row))
    setDraft(next)
  }

  return (
    <div className="flex flex-col gap-row">
      <div className="flex items-center gap-row">
        <h3 className="furniture text-meta text-ink">{field.title}</h3>
        <InfoHint label={`About ${field.title.toLowerCase()}`}>{field.description}</InfoHint>
      </div>
      <div className="flex flex-col gap-field rounded-surface border border-line bg-surface p-section">
        <div
          className="grid gap-row"
          style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(0, 1fr)) auto` }}
        >
          {columns.map((column) => (
            <span key={column.key} className="furniture text-meta text-ink-muted">
              {column.title}
            </span>
          ))}
          <span aria-hidden="true" />
          {shown.map((row, rowIndex) => (
            <TableRowCells
              key={rowIndex}
              columns={columns}
              row={row}
              onCell={(key, value) => setCell(rowIndex, key, value)}
              onRemove={() => setDraft(shown.filter((_, index) => index !== rowIndex))}
              disabled={!field.writable || mutation.isPending}
            />
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-row">
          <Button
            size="sm"
            variant="outline"
            disabled={!field.writable || mutation.isPending}
            onClick={() =>
              setDraft([
                ...shown,
                Object.fromEntries(columns.map((column) => [column.key, ""])),
              ])
            }
          >
            Add row
          </Button>
          <Button
            size="sm"
            disabled={draft === null || mutation.isPending}
            onClick={() => mutation.mutate(shown)}
          >
            {mutation.isPending ? "Saving…" : "Save"}
          </Button>
          {draft !== null && (
            <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
              Discard
            </Button>
          )}
        </div>
        {mutation.isError && (
          <p className="max-w-prose text-meta text-ink-muted">
            {mutation.error instanceof Error ? mutation.error.message : "The save did not go through."}
          </p>
        )}
        {staleNote !== null && (
          <p className="max-w-prose text-meta text-ink-muted">{staleNote}</p>
        )}
      </div>
    </div>
  )
}

function TableRowCells({
  columns,
  row,
  onCell,
  onRemove,
  disabled,
}: {
  columns: StagingColumn[]
  row: Record<string, string>
  onCell: (key: string, value: string) => void
  onRemove: () => void
  disabled: boolean
}) {
  return (
    <>
      {columns.map((column) => (
        <Input
          key={column.key}
          value={row[column.key] ?? ""}
          placeholder={column.example}
          disabled={disabled}
          onChange={(event) => onCell(column.key, event.target.value)}
          className="bg-surface font-mono text-meta border-line"
        />
      ))}
      <Button size="sm" variant="ghost" disabled={disabled} onClick={onRemove}>
        Remove
      </Button>
    </>
  )
}

export function StagingEditor({ vendorId }: { vendorId: string }) {
  const query = useQuery({
    queryKey: ["adapter-staging", vendorId],
    queryFn: ({ signal }) => fetchStaging(vendorId, signal),
  })

  if (query.isPending) return <LoadingState what={`staging for ${vendorId}`} />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what={`staging for ${vendorId}`}
        onRetry={() => void query.refetch()}
      />
    )
  }

  if (query.data.schema.length === 0) {
    return (
      <p className="max-w-prose text-meta text-ink-muted">
        <span className="font-mono">{vendorId}</span> declares nothing to configure — its
        staging is fully baked.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-section">
      {query.data.schema.map((field) =>
        field.type === "table" ? (
          <TableField
            key={field.key}
            vendorId={vendorId}
            field={field}
            rows={(query.data.values[field.key] as TableRows | undefined) ?? []}
          />
        ) : null,
      )}
    </div>
  )
}
