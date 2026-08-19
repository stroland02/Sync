/**
 * Settings → Pages: how each screen works, in its long form.
 *
 * Owner direction, 2026-08-18: the screens themselves keep the data and the load-bearing
 * qualifications, field descriptions move behind ⓘ hints, and the fuller how-it-works account
 * lives here — one place to read about a page instead of a paragraph in front of every table.
 *
 * This panel explains; it never replaces. The protected honesty sentences stay on the screens
 * they qualify, so nothing here is the only copy of a claim — everything below is exposition a
 * reader can skip without being misled by what remains.
 */

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"

interface PageGuide {
  readonly id: string
  readonly title: string
  readonly body: readonly string[]
}

const PAGE_GUIDES: readonly PageGuide[] = [
  {
    id: "overview",
    title: "Overview",
    body: [
      "The selected codebase, and the root of everything beneath it. Three answers sit side by side, and none of them confirms another: what is currently wrong here (open findings), how much of this codebase Sync has read (index coverage), and what traffic Sync saw (observed telemetry). They are kept as three cards because a single figure over them would collapse three different kinds of not-knowing onto one axis.",
      "Every figure on this screen and every screen below it is scoped to the selected codebase. Picking a different one changes every number, not some of them.",
    ],
  },
  {
    id: "findings",
    title: "Metrics",
    body: [
      "Every open finding in the workspace — the call sites an open finding touches, and what each one is bound to. The tabs across the top divide the set by change kind, counted over the whole scope rather than the page in view, so a tab's count says what selecting it would return.",
      "The rung column on each row says how the system knows the site is bound to the operation — static (read from the code), resolved, or observed (seen in traffic). It is not hideable, because a false positive that cannot be attributed to a rung cannot be fixed.",
      "An empty tab names the detectors that stood behind the zero. An unindexed workspace says so instead — those are different facts, and the screen keeps them apart.",
    ],
  },
  {
    id: "runs",
    title: "Logs",
    body: [
      "What the remediation pipeline attempted, what it abandoned, and which change kinds it does not handle mechanically. One row is one attempt: a finding retried three times is three rows here and one finding everywhere else.",
      "The rail on the left narrows by disposition, counted across every run the deployment holds. The record count under the table describes the narrowed set — two figures, two questions, each stating its scope.",
      "Abandonment is data rather than failure: the reason codes are how routing learns which changes are not mechanically safe to attempt.",
    ],
  },
  {
    id: "signals",
    title: "Signals",
    body: [
      "A catalogue of what is attached to the repository's graph, grouped by the role it plays: the vendor role (which API services the code calls), the signal-source role (what traffic showed up and how it behaved), and the human-surface role (where remediation output is delivered).",
      "One card per integration — and a card is not evidence that an integration stands behind it. Each role group states whether anything is attached, because a role that was never asked is a different fact from one that was asked and had nothing to report.",
    ],
  },
  {
    id: "vendors",
    title: "Integrations and connections",
    body: [
      "One page per vendor, scoped to the selected codebase: the operations this codebase calls, the findings open against them, and what the vendor published beside where it was read from. Exposure leads and the vendor's history follows, because the history is the reason the findings appeared.",
      "What a vendor published is a fact about the vendor, never about one codebase — the changes table says so on screen, because it is the one figure on the page that is not scoped.",
    ],
  },
  {
    id: "binding-surface",
    title: "Binding surface",
    body: [
      "One vendor operation joined against every call site bound to it — the place to check whether a binding is right. The call-site table is scoped to the repository; the vendor-change table is not, and each says which.",
      "Every binding carries the rung it was established at, and filtering by rung is how a false positive is traced to the mechanism that produced it.",
    ],
  },
  {
    id: "workflow",
    title: "Solution workflow",
    body: [
      "What Sync actually did about one finding, node by node, read from the checkpointer. Activity is the turn-by-turn narrative with each node's evidence attached where it happened; Findings is the settled output — summary, root cause, the diff, the evidence.",
      "The fact rail holds the run's identity still while the transcript scrolls. The reply box is where a human turn re-enters a run once the write path exists; until then it says exactly why it cannot send.",
      "There is no per-node elapsed time and no liveness signal, because the checkpointer holds neither — the screen says what it reads rather than inventing what it does not.",
    ],
  },
  {
    id: "pull-request",
    title: "Pull request",
    body: [
      "The diff a run wrote and the branch it went to, in one answer — a diff served alone reads as a change that already landed, and the branch is what says otherwise. The verification chain under it is the evidence trail: what compiled, what CI said, and where.",
    ],
  },
  {
    id: "settings",
    title: "Settings",
    body: [
      "Codebases holds the repository scope and the project context read from .sync/context.md — shown and linked, never edited here, because that file belongs to the repository it describes and versions with it.",
      "Pull requests holds the merge policy. The 'immediately' option is refused on the record: a tool that merges before its own evidence arrives is the black box Sync was built against.",
      "Adapters is the inventory of vendor adapters and signal feeds; Connection is the forge authentication this deployment runs with; About explains the platform's own vocabulary — rungs, tiers, gates.",
    ],
  },
]

export function PagesGuidePanel() {
  return (
    <div className="flex flex-col gap-section">
      <div className="flex flex-col gap-field border-b border-line pb-field">
        <h2 className="text-emphasis font-medium text-ink">Pages</h2>
        <p className="max-w-prose text-body text-ink-muted">
          How each screen works, in full. The screens keep their data and their qualifications;
          the explanation lives here and behind each panel&rsquo;s ⓘ.
        </p>
      </div>
      <Accordion type="multiple" className="w-full">
        {PAGE_GUIDES.map((guide) => (
          <AccordionItem key={guide.id} value={guide.id}>
            <AccordionTrigger className="text-body font-medium text-ink">
              {guide.title}
            </AccordionTrigger>
            <AccordionContent className="flex max-w-prose flex-col gap-field text-body text-ink-muted">
              {guide.body.map((paragraph) => (
                <p key={paragraph.slice(0, 32)}>{paragraph}</p>
              ))}
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </div>
  )
}
