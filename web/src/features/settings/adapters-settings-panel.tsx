import { useAdapters } from "@/api/queries"
import { ErrorState, LoadingState } from "@/components/states"
import { AdapterTable } from "@/features/settings/adapter-table"

export function AdaptersSettingsPanel() {
  const query = useAdapters()

  return (
    <div className="flex flex-col gap-section">
      <div className="flex flex-col gap-1 pb-field border-b border-line">
        <h2 className="text-emphasis font-medium text-ink">Registered Adapters & Vendor Feeds</h2>
        <p className="text-body text-ink-muted">
          Every adapter this deployment registers, beside what the graph has received from it.
          An adapter with nothing received has never delivered, which is not the same as having
          delivered nothing — a vendor Sync watched and found unchanged reports a count.
        </p>
      </div>

      {query.isPending && <LoadingState what="the adapter inventory" />}
      {query.isError && (
        <ErrorState
          error={query.error}
          what="the adapter inventory"
          onRetry={() => void query.refetch()}
        />
      )}
      {query.isSuccess && <AdapterTable adapters={query.data.adapters} />}
    </div>
  )
}
