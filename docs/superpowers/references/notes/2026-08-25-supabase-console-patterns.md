# What Supabase's console teaches, mined 2026-08-25

270 raw observations from 356 screens of Supabase's production dashboard, deduplicated and
ranked. Read under the Mobbin carve-out (`CI-W630`): patterns and the problems they solve, never
a picture to copy. Stitch remains the primary visual authority; this fills gaps Stitch does not
draw. The capture itself is gitignored -- `docs/supabase-reference/`, local only.

## Adopt (25)

### 1. Absence is written as a named sentence in the value slot — "No runtime telemetry yet", "No changelog entry parsed", "No adapter bound" — held at the same type size and position a real value would take, one step down in ink. Never a dash, never an em-dash, never a zero. A configured-to-nothing value states its effective behaviour in parentheses ("Unset (50 MB)"); a permissive one is the word "Any"; a genuine zero is a plain full-contrast numeral.

**The problem it solves.** A glyph collapses three different facts — not measured, configured to nothing, genuinely zero — onto one mark, and a reader cannot tell any of them from a failed fetch. Sync already refuses to conflate these in its types (TriageChecks counted/unanswered) but renders the answer as ABSENT = "—" with the reason as an optional trailing child. The sentence in the value slot is the rendering that matches the type, and holding the value slot's exact size keeps a fact grid from visually collapsing where data is missing.

*area: state · value: 5/5 · effort: medium · screens: Every screen — lib/format ABSENT, components/status.tsx Absent, components/fact-tile.tsx and every table cell that renders it, Call sites (bindings), Vendor changes, Findings, Runs*

### 2. Every column header carries the value's type, unit and derivation inline: the name in medium weight, then a muted monospace annotation in the same cell — `observed_at timestamptz`, `call_sites int4`, `DIGEST [SHA256]`, `ROWS (ESTIMATED)`. One parenthetical covers every value in the column, so no cell needs an asterisk, tooltip or footnote. When the cell narrows the annotation truncates first; the identifying name is never clipped. A structural role (the row's canonical identity) is marked by a leading glyph in its own header cell rather than by spending a column.

**The problem it solves.** Sync's tables are full of values whose meaning is ambiguous without a unit — call counts, p95 latencies, drift dates, semver strings, confidence-free integers — and its telemetry columns are sampled rather than counted, so a bare number is read as exact. Annotating the header states the unit and the derivation once per column at zero row cost, and the truncation order guarantees the half that identifies the column survives at any width.

*area: table · value: 5/5 · effort: medium · screens: Call sites (bindings), Vendor changes, Findings, Runs*

### 3. One toolbar band above the grid with a fixed left-to-right order that matches the funnel an operator walks: scope selector, then filter, then search — the search placeholder naming the actual columns of this table — then right-aligned secondaries (refresh, columns, export), then exactly one filled primary at the far right. An unset filter or sort control is drawn with a dashed border and becomes solid when it holds a value. The toolbar band, the column header row and the footer band are all pinned; only the row body scrolls.

**The problem it solves.** Filters that sit in the page header read as page navigation; filters on the table read as belonging to the rows beneath them. "Is a filter active" is answered without opening it and without relying on colour. And on a call-sites table thousands of rows deep, a filter that scrolls away costs a scroll back up to change scope while headers that scroll away leave a bare integer with no unit.

*area: composition · value: 5/5 · effort: medium · screens: Call sites (bindings), Vendor changes, Findings, Runs*

### 4. The applied narrowing is a standing chip that names its own state — "Sorted by 1 rule", "Sorted by last seen", a removable `vendor ×` chip — sitting in the toolbar row itself with a permanent muted "Add more filters…" beside it. Multi-clause filters and sorts are composed as a stack of removable rules inside a popover (each rule a row with its parameters inline and an X, WHERE/AND rails down the left edge, the operator's literal symbol right-aligned in a mono chip) and committed with an explicit Apply, so nothing re-queries mid-edit.

**The problem it solves.** A filtered table looks like a short table. The chip is the standing proof that the view is not the whole set — which is how someone otherwise concludes a vendor has three call sites when it has three hundred. Composing before applying lets an operator build a multi-key ordering over a large call-site graph in one round trip instead of thrashing the query, and printing the operator symbol beside its plain-language name teaches the grammar Sync's graph filters actually speak.

*area: table · value: 5/5 · effort: medium · screens: Call sites (bindings), Findings, Vendor changes, Runs*

### 5. A record's header block is fixed and the tabs swap only the body beneath it: breadcrumb, large title, an identity sub-line carrying the canonical address in full with a copy button and a relative time underlined to signal hover-for-exact, then a right-aligned action cluster, then a text-only underlined tab strip. Everything above the strip is pixel-identical across the record's tabs. The record owns its telemetry, its raw payload, its source and its configuration as tabs on itself rather than as four global sections that must be re-filtered to it.

**The problem it solves.** An investigation that starts at one entity should never leave it, and an operator moving between a finding's evidence, its history and its configuration should never re-read which record they are in or have the actions relocate under them. The identifier you would paste elsewhere and the record's freshness are both readable without opening a metadata table.

*area: composition · value: 5/5 · effort: medium · screens: Finding detail, Call-site detail, Run detail, Vendor detail*

### 6. Selecting rows swaps the toolbar's contents in place rather than pushing a second bar in: the filter input is replaced by the count ("3 selected"), then only the actions valid for that selection with the count inside the verb ("Dismiss 3 findings"), the destructive one in the far-right slot in destructive treatment, then an X to clear. Selected rows take a faint tint and a filled checkbox; the header cell becomes "Select all 40". The grid never shifts vertically.

**The problem it solves.** A bulk bar that appears on top shoves every row down by 48px the moment a checkbox is ticked, and rapid multi-select then misses its target. Bulk operations on findings are the highest-consequence thing in the console, so putting the count inside the verb means the operator reads what will happen rather than counting checkboxes.

*area: table · value: 5/5 · effort: medium · screens: Findings, Call sites (bindings), Runs*

### 7. Rows are partitioned into per-entity cards instead of one flat table: each card's header carries the parent's identity in monospace, a state or provenance chip for the whole group, and that group's own create action; the column header row and the rows live inside the card. A group with nothing in it still renders, with one quiet muted line in its body ("No call sites") rather than being filtered out.

**The problem it solves.** A flat table of children across many parents needs a redundant parent column and gives per-parent actions nowhere to live. More importantly for Sync, rows have sharply different provenance — statically extracted, telemetry-confirmed, vendor-declared, operator-entered — and that provenance governs what an operator may do to them; the card header states it once for many rows. Keeping empty groups rendered is what stops a vendor with zero call sites from vanishing, so "nothing found" stays distinguishable from "not scanned".

*area: composition · value: 5/5 · effort: medium · screens: Call sites (bindings) grouped by vendor, Findings grouped by vendor change, Vendor changes*

### 8. Errors from a subsystem are rendered verbatim in the output pane where the successful result would have appeared — full upstream text, vendor code preserved, monospace, left-aligned, no icon, no paraphrase, no toast, no modal. A remediation affordance sits on the same line at the far right as a split button with a caret for alternatives.

**The problem it solves.** An operator debugging an upstream failure needs the exact string they will paste into a search or an issue. Paraphrasing it into friendly copy destroys the only useful part, and a toast puts it somewhere they cannot copy from later. This is the surface for vendor API error bodies, `tsc` output and the customer's own CI failure text — the three things Sync's verification promise rests on.

*area: state · value: 5/5 · effort: small · screens: Runs, Finding detail, Workflows*

### 9. A relative time-range control shows the absolute window it resolved to as plain text immediately beside it: the "Last 24 hours" chip, then "31 May 23:56 → 01 Jun 23:56". The range belongs to the section that uses it, stated on that section's heading line, not to the page. Sparse series label the x-axis only at its two endpoints, in monospace, with no gridlines or intermediate ticks.

**The problem it solves.** "Last 24 hours" is unreproducible the moment it is screenshotted, pasted into an issue, or read by a second person an hour later — and for Sync a finding's supporting telemetry window ends up in a pull request body, where it has to be citable. Section-scoped ranges also let "new since last run" and "open" answer different questions on one screen, and make it obvious which numbers a change of range actually moved.

*area: state · value: 5/5 · effort: small · screens: Runs, Telemetry, Call-site detail, Findings*

### 10. Before a consequential write, the surface states its blast radius: the exact count in a sentence ("A total of 20 call sites will be patched"), a sample of the actual rows in a small bordered table, an explicit truncation statement ("a preview of the first 20 rows"), a literal consequence list headed "Applying this fix will:" naming the branches, files and call sites it touches, and — where a selection pulled in more than was clicked — one sentence naming what was auto-included and why, with the resulting set drawn and the affected members outlined.

**The problem it solves.** A selection whose real blast radius is larger than what was clicked is the classic silent surprise, and stating the truncation limit is the part most tools skip — it is what stops an operator believing the preview is exhaustive. Opening a PR, applying a repair across call sites and re-running a scan over a repo are exactly the cases that need the count and the sample before the button.

*area: state · value: 5/5 · effort: medium · screens: Findings — bulk repair confirmation, Pull requests — PR preparation, Runs — re-run scope*

### 11. Long-running work reports twice from one operation: a persistent card in the top-right corner with a determinate bar, the aggregate ("Scanning 4 repositories… 62%"), one line naming what would break it, and a Cancel — plus an inline spinner on each affected row in the list. Under the toolbar, a live status line states liveness in words and a number: a glyph, the state as a word ("Scanning"), a dot separator, then a running count ("Found 5 call sites…").

**The problem it solves.** Aggregate progress alone hides which item is stuck; per-row spinners alone hide how much is left. Running both answers "how long" and "which one" without switching screens. And it is the honest alternative to the liveness pulse Sync refuses by name: the words and the count are recorded values, so an operator can tell a job that is alive from one whose last three attempts quietly failed.

*area: state · value: 5/5 · effort: medium · screens: Runs, Index graph — rescan, Workflows*

### 12. The toolbar's action slot mutates in place with the machine state rather than sitting beside its opposite: before a scope is chosen the primary reads "Start scan" and is greyed and inert; once running the same slot becomes "Cancel scan" with a stop glyph and a differentiated tint. One slot, verb derived from state.

**The problem it solves.** The current state and the only sensible next move are the same control, so there is never a pair of buttons where one of them is always wrong, and the inert-until-valid state removes the no-op click.

*area: state · value: 5/5 · effort: small · screens: Runs, Workflows*

### 13. The docked inspector's body is banded into full-bleed sections by hairlines that run edge to edge, each with its own heading and internal padding, in a fixed order that does not vary by item — so scrolling past a rule is a position cue. It carries its own tab strip (Overview / Evidence / Raw) with a raw-payload tab that shows the graph node's JSON, and where it commits, a commit pair pinned in a footer band at the bottom of the pane, secondary then primary, the keyboard shortcut printed inside the primary.

**The problem it solves.** A twenty-field inspector reads as a wall unless it is banded, and a long one becomes unnavigable as one continuous column of label-value pairs — full-width rules give the scroll a coarse structure without the click cost of tabs or accordions. A fixed section order means an operator learns one shape and then reads any finding at speed. The raw tab is the escape hatch for "what does the graph actually hold" without a separate screen, and the pinned footer keeps the commit reachable regardless of field count.

*area: detail · value: 5/5 · effort: medium · screens: Finding detail, Call-site detail, Run detail*

### 14. The canvas reserves its four corners for chrome and leaves the middle entirely to nodes: scope selector top-left, canvas-scoped actions top-right, minimap bottom-right showing the viewport rectangle, and a persistent legend bottom-centre defining every glyph as glyph-plus-word. The ground is a dotted grid inside a bounded rounded border, not an empty rectangle. A node is a miniature table — header row with type glyph, name and a ⋮ overflow, then uniform attribute rows with a right-aligned muted monospace annotation, and a hairline-divided footer band for volatile telemetry so a refresh visibly changes only that band. Zooming out scales type down but never collapses a node into an anonymous blob.

**The problem it solves.** A force-directed map has no fixed extent, so chrome that takes a horizontal band steals from the only dimension the graph needs, and a one-node graph in a plain rectangle looks broken. A dense symbol vocabulary is only learnable if the key is on screen while the symbols are being read — and glyph-plus-word is the compliant form: each mark is one categorical fact stated in a word, with no colour scale and nothing composited. Scanning a node then uses the same skill as scanning the tables, so the graph needs no second reading mode.

*area: composition · value: 5/5 · effort: large · screens: Index graph — integration map canvas, File tree canvas*

### 15. A hierarchy is browsed as fixed-width scrolling Miller columns side by side, separated by hairlines: selecting in column N populates column N+1, unfilled columns stay as empty ruled space rather than collapsing, and a wide preview region sits at the end. Search is scoped to the level in view and says so in its own placeholder — "Search in root directory…" becomes "Search in src/vendors…" as you descend.

**The problem it solves.** A single expanding tree loses the sibling context of every ancestor once you are deep, so the path taken stops being visible and lateral moves cost a collapse-and-reopen. An unlabelled search box in a hierarchical view is ambiguous between "this folder" and "everything", which is why operators stop trusting empty results; the placeholder names the scope at zero layout cost.

*area: composition · value: 5/5 · effort: large · screens: File tree canvas, Index graph*

### 16. Inside a picker list, each row carries a right-aligned "View definition" disclosure that expands a read-only, line-numbered, syntax-highlighted code block within the row itself — the list stays a list, the code arrives inline. Where the picker is a modal it is itself master-detail: full-height list left, and on the right a heading, a short explanation and the actual artefact the option would produce.

**The problem it solves.** Choosing a call site, a vendor endpoint or a suppression target is a decision that needs the source to make, and choosing from named options without seeing what each produces is guesswork. Inline expansion answers "is this the one" without a second pane or a route change, in the same read-only line-numbered form Sync already cites code in elsewhere.

*area: craft · value: 5/5 · effort: medium · screens: Call-site picker, Index graph node picker, File tree, Finding detail — remediation template*

### 17. A dismissible footer strip spans the content column beneath the table, holding the two things the rows cannot carry: provenance in a sentence with the named tool linked ("These findings were raised by oasdiff against openai's published spec") and the maintenance action that re-derives the data ("Re-run detectors"). It has its own X and is not part of the row flow.

**The problem it solves.** "Where did this list come from and how do I recompute it" is asked once per session, not once per row, so it does not belong in the header where the constantly-used actions live. But it must be answered on the same screen as the claim — for Sync that is load-bearing, since every finding has to be traceable to the graph edge that produced it, and the console already carries the per-row rung without carrying the list-level derivation or the way to redo it.

*area: composition · value: 5/5 · effort: small · screens: Findings, Vendor changes, Detectors*

### 18. Constraints are disclosed at the field, before the value is typed: an immutability note right-aligned on the label's own line ("Cannot be changed after creation"), validation rules as helper text under the input, and read-only fields drawn recessed and disabled with the reason as their placeholder ("Automatically generated") rather than hidden. A consequence callout — icon, bold one-line title, two sentences of mechanism, one outlined docs button — appears inside the form only while the control immediately above it is in the state that causes it.

**The problem it solves.** Irreversibility learned after the fact is the most expensive kind, and it costs one line at the moment of naming rather than a confirmation dialog later. Hiding a read-only field makes the operator wonder whether the system holds it at all. And the consequence of a setting is invisible until it bites — which is how Sync should explain the things that silently produce nothing: a detector enabled with no telemetry bound, a repo scanned with no adapter matched.

*area: craft · value: 4/5 · effort: medium · screens: Settings, Detectors — configuration, Repositories — connection, Vendors — adapter binding*

### 19. Save is scoped to the card it belongs to and lives in that card's own footer strip — a hairline above, reset or cancel at the left, one filled primary at the right, rendered dimmed-but-present until that card is dirty. One page carries several independent save scopes and nothing saves the page. Rows inside the card are label-left / control-right separated by full-bleed dividers, with helper text under the control rather than under the whole row.

**The problem it solves.** A page-level save on a page of unrelated concerns makes every edit feel like it risks the others. Card-local commit bounds the blast radius, draws exactly what a given save covers, and makes the disabled state a truthful "nothing pending here" — so no dirty banner is needed. Help text under the control also keeps the label column scannable top to bottom as explanations grow.

*area: craft · value: 4/5 · effort: medium · screens: Settings, Detectors — configuration, Vendors — adapter configuration*

### 20. Every row ends with the same two-part action zone: one named secondary button for the single most common drill-in, identical on every row so it forms a readable column, then a ⋮ overflow for the long tail. A row where the action is unavailable shows it dimmed rather than omitted, so the column stays aligned. The row's edge slot means exactly one thing per table — a chevron means this row opens, a ⋮ means this row has a menu, never both. The overflow menu is divided into three blocks in a fixed order: read/copy actions, act-on-the-object actions, then the single destructive action alone in its own final block.

**The problem it solves.** The frequent action is reachable in one click and discoverable without hovering, while the long tail costs no horizontal space, and conditional omission is what makes a right edge ragged. When a row is simultaneously a link and a target of commands, an operator otherwise learns by accident which click does which. Isolating the destructive item puts physical distance between copying a call-site path and dismissing a finding.

*area: table · value: 4/5 · effort: medium · screens: Call sites (bindings), Findings, Runs, Vendor changes*

### 21. A destructive confirmation names the target's identifier in the title ("Cancel run 153437?"), states the consequence as two short sentences with the affected count echoed back ("This cancels 3 in-flight verifications. This cannot be undone."), and draws the destructive button as a tinted outline rather than a solid slab, with the plain Cancel beside it. The primary stays inert while the current selection would be a no-op. Where the target is a persistent entity, a type-to-confirm field naming the exact required string.

**The problem it solves.** The dialog operates on a selection the operator can no longer see behind it, so echoing the count is what catches a mis-click that selected 30 rows instead of 3, and the identifier in the title proves which object it is about when three panes are open. A tinted-not-solid destructive button keeps the console's filled weight reserved for the affirmative path, and the inert no-op prevents the confirmation that changes nothing — the one that erodes trust in confirmations generally.

*area: craft · value: 4/5 · effort: small · screens: Findings — bulk dismiss, Runs — cancel, Pull requests — close, Settings — disconnect repository*

### 22. Typeface does the annotation: identifiers, timestamps, ids and enum tokens are set in monospace while prose stays proportional, and enumerated cell values render as monospace chips on a tinted ground. Timestamps in operator tables are absolute and fully specified, with relative age offered as the underlined hover-for-exact form rather than as the only rendering. Long opaque identifiers render a readable monospace prefix with the remainder masked and a copy button at the cell's right edge; where the value must stay readable, the copy control is attached after it rather than replacing it.

**The problem it solves.** In a table mixing identifiers, enum values and prose, the reader cannot tell which strings are literal tokens they could type or grep for — and monospaced digits align vertically, so four cards side by side can be confirmed at a glance to share one window and a column of times scans as a column rather than a ragged list. Correlating a run against an external log needs the real clock value, since "yesterday" cannot be joined to anything. Values that exist only inside a copy button cannot be read, compared or partially selected.

*area: table · value: 4/5 · effort: medium · screens: Runs, Vendor changes, Call sites (bindings), Findings*

### 23. Keyboard shortcuts are printed inside the control they trigger rather than collected in a help sheet: the primary reads "Run ⌘↵", global search shows "⌘K" in its placeholder, and a chord is taught in the button's own tooltip as separate keycaps joined by the word "then".

**The problem it solves.** An operator who runs the same triage loop fifty times a day learns the shortcut only if it is where their eye already is; a shortcuts modal is read once and forgotten. It costs no additional surface, and the keycap-plus-"then" form disambiguates a sequence from a simultaneous press.

*area: craft · value: 4/5 · effort: small · screens: Every screen with a primary action, Command palette*

### 24. A picker opens as a search-first popover anchored under the button that spawned it, with small-caps group labels and one row per option rendered as type-glyph + monospace token + a one-line plain-language definition. "Create new" with a leading + is the first row of results rather than a separate button elsewhere. The chosen value renders back in the closed field with the same glyph. An unset control shows a grey placeholder with a double up-down chevron; a set one shows dark value text with a single chevron.

**The problem it solves.** An enum list of bare identifiers forces the operator to already know the vocabulary, so Sync's own vocabularies — finding kinds, change classes, binding rungs, run outcomes — get taught at the point of choice instead of in a legend nobody opens. Pickers over unbounded sets should start typed rather than scrolled, and putting create-new inside the same list means nobody has to decide up front whether the thing they want already exists. Two distinct glyphs make "nothing chosen" unmistakable without an asterisk or a validation message.

*area: craft · value: 4/5 · effort: medium · screens: Detectors — kind selector, Vendors — adapter selection, Findings — status picker, Call sites (bindings) — add filter / add column*

### 25. A bounded quantity is stated as a literal ratio — "7/60 concurrent runs", "8/60 connections" — as an inline strip of name-value pairs separated by middots where several volatile scalars share a row, with a thin unlabelled two-tone track beneath only where a real published ceiling exists. No percentage, no fill gauge, no threshold recolour.

**The problem it solves.** A ratio carries the ceiling in the same glance as the reading, which a percentage or a filled bar throws away — and where the denominator is the operationally interesting number (rate limit, quota, budget, concurrency cap) the ceiling is the point. Four volatile numbers also do not each deserve a card.

*area: state · value: 4/5 · effort: small · screens: Vendor detail — rate-limit headroom, Runs — concurrency against the cap, Settings — budget*


## Conflicts with our rules (13) — the honest version

- **A rolled-up status word rendered as a peer fact — a STATUS tile in the fact grid reading "Healthy", or a section heading generalised from one detector's result to the whole surface.**
  - Collides with: No composite score or health figure. The fact-grid slot and the outcome-as-heading form are both worth taking; the aggregate in them is not.
  - Honest version: Keep the tile geometry and the typography, but the slot holds a fact Sync actually computed — "14 call sites", "Last indexed 4m ago", "3 breaking changes since 2026-08-01". Keep the heading-states-the-outcome form and scope it to one named detector ("oasdiff found no breaking changes"), which degrades honestly because it cannot be confused with "oasdiff has not run". A heading that aggregates across detectors ("Your APIs are healthy") is a composite score written in prose.
- **Colour carrying meaning on its own: a green/grey dot as the sole has-data signal beside a count, red/amber/green legend dots in a timeline histogram tooltip, a coloured icon tile sitting next to a status word, and a two-state row property drawn as an eye vs a struck-through eye with no word.**
  - Collides with: No traffic light or liveness pulse. components/status.tsx already fixes the contract: an icon, a word, and the mark — never the mark alone.
  - Honest version: Every one of these becomes icon-plus-word in the console's existing Status form, or the muted glyph-plus-word the same source uses elsewhere ("✕ Disabled", "INSTALLED"). Keep the histogram's count readout and its shared x-axis, and encode its categories by icon and word or by hues chosen for discriminability — the fix CI-W619 already forced on the traffic chart. Keep the fixed-slot shape change for two-state row properties, and keep the word beside it.
- **One amber doing three jobs: the PRODUCTION environment chip, the forcing-action button tint, and severity.**
  - Collides with: No traffic light — a hue that means both "which environment" and "this is dangerous" is the exact ambiguity the rule exists to prevent.
  - Honest version: The environment chip is outline-neutral and identity-only; it names the branch's role and never rates it, and it never shares a colour with finding severity. A forcing primary is differentiated by weight and by an explicit verb, not by borrowing a hue already spent on status or environment.
- **Exactly one saturated colour in the chrome for the primary action — while the chart series is drawn in that same saturated hue.**
  - Collides with: In a console where the data is the product, an affordance colour on a plotted series makes data look clickable.
  - Honest version: Keep the one-saturated-element rule and the primary pinned into the scope bar. Reserve the accent for that action alone and give series their own discriminable hues, which is what CI-W619 already established for the traffic chart.
- **A zero series keeps the full metric card — label, literal "0", a flat hairline where the baseline would be, both endpoint timestamps — with the plot area drawn rather than blanked.**
  - Collides with: Absence is not zero. The flat baseline is only honest when a measurement actually happened.
  - Honest version: A measured zero keeps the whole card exactly as observed: the card does not shrink and the row does not reflow, because a blank plot reads as a failed load. An unmeasured tile keeps the numeral slot but swaps the plot area for a dashed-border region with a muted glyph, "No data to show", and a second line naming the cause and the horizon — "no runtime telemetry is bound to this call site". A call site with no telemetry must never render as a call site with no traffic.
- **Loading placeholder rows carrying plausibly-shaped fake names (postgres_table_0 … postgres_table_3) at the correct row height, one of them in the selected state.**
  - Collides with: Real data only. Sync's identifiers look like real paths and versions, so a plausible placeholder is a screenshot away from being read as data.
  - Honest version: components/skeleton.tsx already holds the compliant form — a bar the width of the value it will become, no text, no pulse, aria-hidden. Take the no-layout-shift property the observation is really about and keep the bars; never a synthetic file path or version string.
- **A three-way pre-execution warning: Cancel, the risky path in an amber-tinted button, and the recommended path as the primary — the risky path stays available and is marked, not disabled.**
  - Collides with: Nothing reaches a pull request unverified. The three-way form is genuinely better than proceed-or-cancel, because a warning that only offers two teaches nothing about which is correct — but the third slot cannot be "proceed without verification".
  - Honest version: The risky slot must itself be gated: "apply to a branch without opening a PR" is a real third option that stays inside the invariant. If no such option exists for a given action, ship the two-button version rather than inventing one.
- **A capability matrix whose cells are inline toggles, writing configuration directly from a list row.**
  - Collides with: Nothing reaches a pull request unverified — an inline row toggle is the shape that invites bypassing the pipeline.
  - Honest version: Fine for console-local settings that touch nothing outside the console (column visibility, saved views, detector enablement in Settings). Anything acting on a customer repository goes through the verified pipeline and gets a drawer with a preview and a commit footer, never a switch in a row.
- **A consumption bar or quota gauge — a thin filled track with the numerator and denominator stated beneath it.**
  - Collides with: No composite score. The shape is legitimate only for a single measured quantity against a known hard cap.
  - Honest version: Draw it only where Sync holds both the observed value and a real published limit from the adapter. Keep the numbers authoritative in text with their units, let the track only echo them, never recolour at a threshold, and never draw it against an inferred ceiling or an aggregate of several signals — that is a health bar.
- **A filter placeholder that names the table's real columns and then ends "…or ask AI".**
  - Collides with: Real data only — a placeholder is a promise.
  - Honest version: Keep the half that works: name the actual columns this table's filter accepts, so the operator knows the language before typing. Advertise natural-language filtering only once it is wired.
- **A Data | Definition segmented toggle pinned to the far right of the table footer, swapping the pane between the rows and the thing that produced them.**
  - Collides with: Real data only. A toggle to an empty pane is worse than no toggle.
  - Honest version: Ship the second half only where Sync holds a printable definition for that view — the graph query or the edge that selected the rows. Where it does, this is the right place for it, because it keeps the toolbar's single-primary rule intact.
- **Banners and advisories that state an implication rather than an observation: "this table can be accessed by anyone", a predicted saving from enabling something, a NEW-pill caveat that reads as a confidence rating on the values below it.**
  - Collides with: No composite score; real data only. The banner form is right and the amber severity tint is not.
  - Honest version: The sentence restates something the graph actually holds — "no runtime telemetry is joined to these 12 call sites", "telemetry covers 3 of 11 endpoints", "this scan was partial". A coverage limitation, never a risk judgement, a predicted outcome, a projected saving, or a confidence rating on individual values. Take the banner geometry; leave the hue.
- **A lens or role chip standing in the toolbar that changes what the rows below it return, chosen from a popover of labelled cards and kept visible afterwards as a standing reminder.**
  - Collides with: No composite score; real data only.
  - Honest version: Adopt it only for a dimension Sync genuinely holds data for — a scan run, a vendor version, a graph snapshot — where an operator who forgets which run is loaded would misread a resolved finding as an open one. The chip must never carry a composite state word, and it must never present a filtered subset as though it were a different truth.


## Confirms what we already do (19) — do not redo as new work

- Empty tables keep their real column headers and state what was checked rather than merely that there is nothing — components/table-empty.tsx (decision 61), with the counted / unanswered and checked / unchecked distinctions held in the types in components/triage-tabs.tsx and the five kinds of nothing in components/states.tsx. The "solid border = ran and found nothing, dashed border = never configured" observation is a border encoding on a distinction Sync already refuses to conflate; do not re-litigate the distinction.
- Absence is one console-wide marker that says which kind of nothing it is, and a tile never renders an empty value — components/status.tsx (Absent), components/fact-tile.tsx. Only the rendering needs work (see adopt #1); the rule is in place and tested.
- Status is an icon, a word and the mark, never the mark alone, across four reserved hues — components/status.tsx. The provenance rung takes weight and spacing and never a hue — components/provenance.tsx (RungBadge).
- No liveness pulse, no dot, no Live badge; staleness is the last successful fetch stated in words with its age, ticking, and a stopped poll says why it stopped — components/fetched-at.tsx.
- Loading placeholders are width-matched bars with no text and no pulse — components/skeleton.tsx.
- One primary action per surface, type-enforced as a single slot, with scope and search on the left — layouts/control-bar.tsx.
- A footer band under the table carrying the record count and paging, with the count stating what a filter excluded rather than a bare range — layouts/footer-bar.tsx, components/page-controls.tsx, describeRange (decision 60).
- The applied ordering is stated in words whether or not anybody chose one, and both filtering and ordering are sent to the API rather than applied to the rows already fetched — components/ordering.tsx, components/filters.tsx. Facet counts are counted over the facet's own scope, never the page.
- The detail pane sits beside the list rather than over it, is not modal, has no focus trap, and Back closes it — components/detail-layout.tsx (the M15 Task 2 correction of the earlier modal Sheet, citing Supabase's own non-modal list-detail).
- A per-table column-visibility picker exists, with claim columns declared un-hideable (the provenance rung is never hideable) and stored choices filtered against the current column set — components/column-visibility.tsx.
- A persistent top bar carries the scope trail with a switcher per tier, derived from the address and holding no state of its own — layouts/scope-switchers.tsx; sibling screens are a chassis-owned tab strip in the identity band — layouts/screen-tabs.tsx.
- Fact tiles use a distinct label register above a value register, with no chart, delta, sparkline or colour, inside one strip with hairline dividers rather than a row of cards — components/fact-tile.tsx, components/kpi-strip.tsx.
- A figure is required to carry its unit, and a value sits above its own evidence — components/metric-panel.tsx.
- Triage tabs carry a count per bucket with counted-vs-unanswered in the type, so a view that never asked cannot render 0 — components/triage-tabs.tsx. This is the severity-bucket strip observation, already shipped.
- A panel-level scope chip states what a figure was counted over, monochrome, in words rather than a colour, with an ⓘ carrying why — components/scope-chip.tsx.
- Chart series are drawn in distinguishable hues — CI-W619 fixed exactly the near-identical-orange failure the histogram observations warn about.
- Every screen names itself, larger than its own sections — CI-W622; the persistent sidebar and its collapse — CI-W615, CI-W629 (two-bar chrome, sidebar moves only on its button).
- A command palette exists — layouts/command-palette.tsx.
- Per-row provenance and an envelope-level provenance strip already ship — components/provenance.tsx; what is missing is only the list-level derivation sentence and the re-derive action (adopt #17).
