/**
 * The vendor's own record, as one pane holding one table at a time.
 *
 * Two records answer different questions about the same integration — what it published, and what
 * came out of that here — and they are the two widest tables on the screen. Stacking them would put
 * one of them below the fold of a locked column; mounting both to show one is the cost
 * `page-tabs.tsx` documents. So the pane's head carries the vocabulary and only the pressed record
 * mounts.
 *
 * **The record is a query parameter, not component state**: a shared address opens on the record
 * the sender was reading.
 *
 * **The chips carry no counts.** Both figures are already on the chassis strip, at figure weight,
 * with their scopes attached — a count on a chip would be the same fact a third time and would
 * need the record's query mounted to produce it, which is the thing this pane exists to avoid.
 */

import { Table2 } from "lucide-react"

import { ChipTabs } from "@/components/chip-tabs"
import { InfoHint } from "@/components/info-hint"
import { PanelPane } from "@/components/pane"
import { VendorChangesRecord } from "@/features/vendors/vendor-changes-record"
import { VendorFindingsRecord } from "@/features/vendors/vendor-findings-record"
import { RECORDS, type RecordId } from "@/features/vendors/vendor-record"

export function VendorRecordPane({
  vendorId,
  repoId,
  record,
  onRecord,
}: {
  vendorId: string
  repoId: string
  record: RecordId
  onRecord: (next: RecordId) => void
}) {
  return (
    <PanelPane
      scroll={false}
      label="The vendor's own record"
      icon={Table2}
      hint={
        <InfoHint label="About the two records">
          <p>
            <strong>Changes published</strong> is what {vendorId} shipped, whether or not this
            codebase is affected — evidence about the vendor, read out of a feed rather than out of
            your source, which is why no rung applies to it.
          </p>
          <p>
            <strong>Open findings</strong> is what a detector made of that here: a change meeting a
            call this codebase makes, at the call sites listed against it. Its three narrowings sit
            in its own head and reach only it; the changes record takes none of them, because what a
            vendor published has no severity in your codebase and no path in it either.
          </p>
        </InfoHint>
      }
      actions={
        <ChipTabs
          label="Which record"
          options={RECORDS.map((entry) => ({ id: entry.id, label: entry.label }))}
          activeId={record}
          onSelect={(id) => onRecord(id as RecordId)}
        />
      }
    >
      {record === "changes" ? (
        <VendorChangesRecord vendorId={vendorId} repoId={repoId} />
      ) : (
        <VendorFindingsRecord vendorId={vendorId} repoId={repoId} />
      )}
    </PanelPane>
  )
}
