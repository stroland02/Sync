# `npx shadcn add` replaces rather than merges, and it reached a file nobody named

**Measured 2026-08-18 while running the nineteen-component batch (`M0-W326`).** Recorded rather than
only fixed, because the failure is silent, no guard in this repository can see it, and twenty-two
components were already vendored before the batch began.

## What happened

```
npx shadcn@latest add switch form radio-group checkbox pagination toggle-group accordion alert collapsible --yes --overwrite
```

The CLI reported two things, and the second is the finding:

```
✔ Created 9 files:
  - src\components\ui\switch.tsx
  … eight more …
ℹ Updated 1 file:
  - src\components\ui\button.tsx
```

**`button.tsx` was not in the command.** It arrived as a transitive dependency of something that
was, and it was *replaced*, not merged.

## What the replacement destroyed

`git diff` before staging, which is the only reason this was caught:

- **A recorded design decision was deleted** — six lines of comment on the `destructive` variant:

  > *No focus-ring override. This variant used to recolour the ring to `critical-ink` at 20% and its
  > border at 40%, which composite to **1.40:1 and 2.03:1** against the button's own surface — a
  > focus signal below the **3:1 non-text floor** on the one variant whose job is to be hard to press
  > by accident.*

  That is an accessibility decision with its arithmetic, of exactly the kind `DESIGN.md` exists to
  hold. Deleting the comment would not restore the bad ring by itself — but it removes the reason,
  and a reason nobody can find is a decision that gets made again the other way.

- **Three token references changed silently:** `transition-colors` → `transition-all`,
  `focus-visible:ring-ring` → `focus-visible:ring-ring/50`, and the `default` variant's hover from a
  `color-mix(in oklch, …)` to `hover:bg-primary/80`. The middle one is a focus-ring opacity change
  on every button in the console.

## Why nothing would have caught it

This is the part that makes it worth a report rather than a commit message.

- **The colour guard cannot see it.** `tests/test_console_design_tokens.py` catches hex and
  colour-function *literals*. `ring-ring/50` is a token reference with an opacity modifier, so it is
  legal by construction.
- **No test asserts it.** `.claude/rules/console-dev-loop.md` forbids class-name assertions and
  snapshots, on good grounds — so the one mechanism that would have failed here is the one this
  repository has deliberately ruled out.
- **The build stays green.** It is valid Tailwind and valid TypeScript.
- **The CLI's own output half-hides it.** `Created` is a bulleted list under a tick; `Updated` is a
  single line under an `ℹ`, below it, naming a file the operator never mentioned.

So the failure mode is: a documented contrast decision is reverted, every gate passes, and the only
signal is one line of CLI output and a diff nobody was told to read.

## The procedure, which is now the owner's and is wider than "check the target"

The owner's instruction is to check whether the target already exists before each add, diff after,
and restore anything the CLI dropped. **One amendment from this incident, and it is the load-bearing
half: checking the targets is not sufficient.** `button.tsx` was not a target. The check has to be
against what the CLI actually wrote, not against what it was asked to write.

1. **Before the batch:** record which files already exist. Twenty-two were vendored under
   `web/src/vendor/supabase/ui/` and eight under `web/src/components/ui/` before this one.
2. **After every `add`:** `git status --short` and read the `M` lines, not the `??` lines. A created
   file is safe by definition; a *modified* file is the whole risk.
3. **For every `M`:** `git diff` it and restore any local amendment — a comment carrying a decision
   counts as an amendment, not as noise.
4. **In the commit:** say which files were already present and what was restored.

## What was restored here

`web/src/components/ui/button.tsx`, reverted with `git checkout --` and verified: the six-line
focus-ring decision is intact at `button.tsx:20-25` and the file is clean against `HEAD`. No other
pre-existing file was modified by the batch — checked with `git status` across all three `add`
invocations, which reported `button.tsx` once and nothing else.

## One related finding from the same batch

`npx shadcn@latest add form` reports `✔ Checking registry` and then creates nothing, twice, with no
error. `form` is the component Lane G's Settings work needs. It is not a permissions or network
failure — every other component in the same session installed — so it is either absent from the
`radix-nova` style declared in `web/components.json` or gated behind a dependency the CLI declines to
add. Recorded here because a silent no-op is the same class of defect as a silent overwrite: the
command reports success and the file is not there.
