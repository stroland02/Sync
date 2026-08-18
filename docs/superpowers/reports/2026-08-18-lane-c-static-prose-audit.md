# M0-W329 applied to Lane C's three screens, without cutting anything

**2026-08-18, `CI-W376`.** The ruling is that static description moves to Settings, with the test
*would this text change if the data changed?* The instruction attached to it is to run
`prose-audit.mjs` first, because some prose is protected and the ratio does not license deletion.

**`prose-audit.mjs` could not be run, and the reason is a blocker rather than a choice.** It drives a
*built* console over CDP, and `npm run build` exits 2 on `main` — six `tsc` errors in
`web/src/features/settings/`, escalated separately and not this lane's. So this audit is static: it
reads the source rather than the rendered screen, and it proposes rather than cuts.

## What is protected here, established before anything was counted

`docs/superpowers/plans/2026-08-05-sync-console-architecture.md` reproduces the twenty-four
sentences with file and line. Two of them are in this lane:

- `features/bindings/binding-surface-page.tsx:116`, `:117` and `:157-160` — the *two-meanings*
  sentence, that a missing row cannot be told from a retracted one.

Those may be restyled and never shortened, and nothing below touches them.

## The count

Long string literals — sixty characters or more, which is the length at which a label has become a
sentence:

| directory | literals | characters |
|---|---|---|
| `features/findings/` | 4 | 652 |
| `features/bindings/` | 9 | 1,605 |
| `features/pullrequests/` | 14 | 2,009 |

## The one block the test clearly catches

**`BUNDLE_STAGES[].blurb` in `features/pullrequests/evidence-bundle.tsx`: five blurbs, 757
characters, and not one of them changes when the data changes.** They describe what each node of the
remediation graph *is* — what the compiler checks, what replay does, why the customer's CI is the
long pole. That description is identical for a run that passed, a run that abandoned, and a run that
never started, which is precisely the ruling's test failing.

It is also 38% of this lane's static prose in one constant, so it is the whole of the finding rather
than the first of many.

**Not moved here, for two reasons.** Settings is another lane's directory and is currently the
broken one; and the ruling says static description *moves* to Settings rather than being deleted, so
moving it requires a destination that exists and someone who owns it. **The proposal is that these
five sentences go to Settings verbatim and the five stage titles stay** — a reviewer scanning this
bundle for the node that did not run reads five titles and five verdicts, and needs the essay once,
somewhere else.

## What the audit does not support

- **No cut on the other eighteen literals.** Several are the four-kinds-of-nothing sentences in
  `EmptyStage` and `Framing`, which *do* change with the data — they are selected by `standing` and
  by `outcome`, and each says something different about what happened. They pass the test.
- **No tile row on the binding surface.** The side-by-side names signals, observe and remediation as
  the three screens behind on composition and says explicitly "three screens, not nine". This lane's
  surface measured *ahead* — `regionsBeside` 5 against the mock's 1, and 36 cells where the mock has
  none. Adding a `FactTile` row would reverse `B115`'s measurement — about a hundred vertical pixels
  on the console's densest screen, where the scarce resource is rows above the fold on a 2,500-row
  table — and it would add static caption prose at the moment the ruling is to remove it.
