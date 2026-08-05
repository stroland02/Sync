/**
 * Where an operator jumps into the binding surface from.
 *
 * Nothing in the graph enumerates "every operation a vendor has", and the frozen
 * `GraphSurface` offers no such list either — so this is a lookup rather than a picker. A
 * vendor id and an operation id are strings an operator already has in hand from a finding, a
 * vendor's changelog, or the vendor page's own tables; this form turns them into the URL that
 * answers "what depends on this, and how does Sync know?"
 */

import { type FormEvent, useState } from "react"
import { useNavigate } from "react-router"

import { Button } from "@/components/ui/button"

const FIELD_CLASS =
  "rounded-control border border-input bg-transparent px-row py-1 font-mono text-body outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder: string
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-meta tracking-wide text-muted-foreground uppercase">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className={FIELD_CLASS}
      />
    </label>
  )
}

export function BindingLookupForm() {
  const navigate = useNavigate()
  const [vendorId, setVendorId] = useState("")
  const [operationId, setOperationId] = useState("")
  const [repoId, setRepoId] = useState("")

  const canSubmit = vendorId.trim() !== "" && operationId.trim() !== ""

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!canSubmit) return
    const path = `/bindings/vendors/${encodeURIComponent(vendorId.trim())}/operations/${encodeURIComponent(operationId.trim())}`
    const query = repoId.trim() ? `?repo_id=${encodeURIComponent(repoId.trim())}` : ""
    navigate(`${path}${query}`)
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
      <Field label="Vendor id" value={vendorId} onChange={setVendorId} placeholder="stripe" />
      <Field
        label="Operation id"
        value={operationId}
        onChange={setOperationId}
        placeholder="PostCharges"
      />
      <Field
        label="Repository (optional)"
        value={repoId}
        onChange={setRepoId}
        placeholder="every repository"
      />
      <Button type="submit" disabled={!canSubmit}>
        Show bindings
      </Button>
    </form>
  )
}
