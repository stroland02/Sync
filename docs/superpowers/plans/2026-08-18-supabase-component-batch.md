# The Supabase component batch: nineteen missing, one lane adds them, five consume

**Owner direction, 2026-08-18:** pull the front-end components properly from Supabase's
`packages/ui`, and note that `npx shadcn@latest add <url>` injects the source directly rather than
requiring a dig through GitHub.

## This is already authorised and already half-built — check before adding

`.claude/rules/interface-originality.md` carries **the Supabase carve-out, owner-authorised
2026-08-06**: their component code is adopted at code level, vendored under
`web/src/vendor/supabase/`, with attribution in `web/NOTICE`. For this one source, *"a component's
appearance"* and *"a component built by looking at a screenshot"* stop being refusals.

**Measured, not assumed:**

- **22 files already vendored**, including `sidebar.tsx`, `table.tsx`, `tabs.tsx`, `command.tsx`,
  `sheet.tsx`, `scroll-area.tsx`, `dialog.tsx`, `dropdown-menu.tsx`.
- **`web/NOTICE` already exists**, naming the upstream commit `6ac0316` and the Apache-2.0 licence,
  and listing every vendored file.
- **`shadcn` is already a devDependency** at `^4.16.1`, and `radix-ui` at `^1.6.7`. The owner's CLI
  route works here today.
- **`cn()` exists** at `web/src/lib/utils.ts`, with a customised `twMerge` that already knows about
  our `text-emphasis` and `text-critical-ink` tokens.

**So the task is not "set this up". It is "add the nineteen the new layouts need".**

## The nineteen, each with the surface that needs it

| Component | Needed by |
|---|---|
| `label`, `textarea`, `switch`, `form`, `radio-group` | Settings — every card control, the merge-policy choice, save-per-card |
| `checkbox`, `pagination` | The table format — row selection, footer with record count |
| `toggle-group`, `accordion`, `alert` | Triage headers with counts, show-more spans, empty and refusal states |
| `collapsible`, `navigation-menu`, `menubar` | Sidebar nested disclosure and the top row |
| `chart` | Overview per-vendor bar charts |
| `resizable` | Drawer and split panes |
| `avatar` | Vendor cards, agent turns |
| `hover-card` | Binding and rung detail |
| `progress` | Index progress |
| `sonner` | Transient notices |

## One lane adds them, in one commit, and here is why

`web/src/vendor/supabase/**` and `web/NOTICE` are on the fenced list — the three places a change
breaks every lane at once. **Five lanes adding components independently produces five-way conflicts
in `NOTICE` and duplicate files.** So it is a single batch by a single lane, and everyone else
consumes the result.

**Lane B owns it**, because it already owns the shared chrome.

## The adaptation rules, which are the owner's and are non-negotiable per file

1. **React, TypeScript, Tailwind, Radix primitives** where the original uses them.
2. **Strip monorepo imports.** Any `common/utils` or workspace-internal import is replaced with our
   `cn()` from `web/src/lib/utils.ts`.
3. **Strict typing. No `any`.** Every interface and prop type defined and exported.
4. **Preserve the visual design exactly** — tokens, animations, hover states, and the `dark:` class
   structure as Supabase authored them.
5. **Drop-in complete files.** No omitted imports, nothing left to resolve.

**And two of ours on top:**

6. **`web/NOTICE` is updated in the same commit**, with each new file listed and the upstream commit
   named. A vendored file absent from `NOTICE` is an attribution defect, not a paperwork one.
7. **No component may assert a claim our data cannot support.** Per the carve-out's own section 6: a
   slot for a confidence score renders the rung instead. `chart` is the one to watch — a bar chart
   over real counts is fine; a gauge or a health ring is not.
