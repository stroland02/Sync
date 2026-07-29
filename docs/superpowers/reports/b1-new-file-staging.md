# B1 — a patch that needs a new file can now ship one

Commit `aeecde4` on `stroland02/m1-forge`, rebased onto `origin/main` at `9b13cce`.

Files changed: `src/sync/remediate/agent_patch.py`, `src/sync/forge/github.py`,
`tests/test_agent_patch.py`, `tests/test_github_forge.py`. Nothing under `src/sync/index/`
was touched.

## Did the staging-as-assertion line hold up

Yes, and more cheaply than the brief expected. Three of the four places it had to hold
already held, which I measured rather than assumed:

| Question | Answer | How it was measured |
|---|---|---|
| What does `git status --porcelain --ignored` report for a staged new file? | `A ` | Scratch repository: `git add added.ts`, then status. |
| Does `shipped_tree` hold it aside? | No. `_UNSHIPPED` is exactly `{"??", "!!"}`, and `A ` is in neither. | Read plus the status code above. |
| Does `git add -u` drop it? | No. A staged path has an index entry, and `git add -u` updates the index where it already has one, so the file stays staged and is committed. | Scratch repository: stage a new file, modify a tracked one, `git add -u`, `git status` still reports `A `. |
| Does `git checkout -B <branch>` drop it? | No. The index survives the branch creation. | Same scratch repository, status re-read after `checkout -B`. |

So `push_branch` did not have to change to stop undoing the staging — it was never undoing
it. The one place that was actually broken is in `sync.remediate.agent_patch`.

### What `shipped_tree` does with a staged new path — the answer the brief asked for

It leaves it in the tree, and the gate therefore compiles it. `unshipped_paths` selects on
`code in _UNSHIPPED` where `_UNSHIPPED = frozenset({"??", "!!"})`, and git reports a
staged-but-new file as `A `, not `??`. There is no code path that could move it aside.

That is the correct behaviour and it is correct by accident of how the set was written, not
because anything states the intent. **`_UNSHIPPED` being exactly `{"??", "!!"}` is now
load-bearing for the new-file path, and its own comment does not say so.** A future change
that added `"A "` to that set would read as tightening — "surely a file that is not in a
commit yet is unshipped" — and would silently break every patch that needs a new module: the
gate would compile a tree without the file and report an unresolved import, which is exactly
the failure this task removed.

One further measurement, since it decides whether the gate and the push can ever disagree: a
file that is gitignored and force-added with `git add -f` also reports `A `. So it is kept by
`shipped_tree`, measured by the gate, and committed by the push — consistent in all three.
There is no state in which the gate measures a tree the push would not carry.

## The defect that was actually blocking

`agent_patch._git_diff` ran `git diff`, which compares the working tree to the index and so
cannot see a staged addition at all.

- A patch that adds a module *and* edits a tracked call site produced a diff naming only the
  call site. That diff is what the corpus records and what a CI retry is shown as "the diff
  CI rejected", so both described half a patch.
- A patch whose whole content is the new module produced an **empty** diff, which
  `route_after_patch` treats as a remediator that changed nothing — retry, retry, abandon.

It is `["git", "diff", "HEAD"]` now. That reads the index as well as the working tree, and it
is still blind to untracked paths for the same reason `git add -u` is: neither reads the
working tree for a path the index does not know. Widening to `HEAD` is not the loose option
and the docstring says so, because it reads like one.

## The agent's scope instructions — yes, they had to change

Two rules in `_SCOPE_RULES`. One new, one amended.

**New rule, inserted before the typecheck rule:**

> - If the edit genuinely needs a file that does not exist yet, create it and then stage it
>   with `git add <path>`. Only what git already tracks and what you have staged is
>   typechecked and pushed; a new file left unstaged is in neither, and the branch would
>   carry an import of a module that is not there. Stage the files you added for this change
>   by path and nothing else -- never `git add -A` or `git add .`, which would sweep in
>   whatever your commands happened to leave in this clone. Staging a file is you asserting
>   the patch needs it, and it is the only thing that distinguishes a file the fix requires
>   from a build artifact or a log.

**Amended typecheck rule** — the clause `-- after staging anything you added, so that it
measures the same tree the branch will carry --` was inserted after "once you have made the
edit". The rest of that rule is unchanged, including everything
`test_the_prompt_says_a_clean_typecheck_does_not_mean_the_edit_was_unnecessary` pins.

This is the instruction problem `prepare`'s docstring names. The agent is told to run its own
`npx tsc --noEmit`; unqualified, that command measures the working tree while the gate
measures the tree the push would carry, so an agent that created a file and left it unstaged
would get a clean run from its own command and a failure from the gate over the same edit.
Naming the staging makes the two agree.

## Honesty of the abandon path

Half closed, and the remaining half needs a file I do not own.

**Closed:** an agent that creates files and stages none of them leaves an empty diff, which
previously reported "the remediator produced no change" — the wrong cause entirely, sending
an operator after a model that did nothing when it had done the work and failed to assert it.
`propose` now raises naming the files and the remedy. That message is not only the abandon
reason: `make_patch` catches it and hands it to the next attempt as feedback, so it is also
how the run corrects itself. A remediator that genuinely found nothing to change still
returns an empty diff and still reaches `route_after_patch` — the raise is conditional on
there being unstaged files, and there is a test holding that counterweight.

**Not closed:** the mixed case. An agent that edits the tracked call site *and* creates a new
module it does not stage produces a non-empty diff, so the run proceeds and the gate fails on
`TS2307: Cannot find module './x'`. That is a downstream compile error standing in for the
real cause. It is self-correcting on retry — `_SCOPE_RULES` is in the retry prompt too, so
the agent sees the unresolved import beside the rule that explains it — but if both attempts
fail, the operator-facing `abandon_reason` is still the compile error.

Closing it properly means a disclosure in the diagnostics `static_verify` returns, along the
lines of "these paths exist in the clone but are not staged, so neither the typecheck nor the
branch includes them". That is a statement of fact rather than a classification, so it does
not reintroduce the heuristic the brief rules out — but it belongs in
`src/sync/index/typescript.py`, which B3 holds. Flagging rather than doing.

## Tests, and the exact mutation run against each

Six new tests. Four failed before the implementation existed and are recorded from that run;
the other two pass on the pre-change code by construction — they are the guards that would
silently pass if the thing they guard were dropped — so each was mutated deliberately and
watched go red, then the mutation reverted.

### `tests/test_agent_patch.py`

| Test | Mutation | Result |
|---|---|---|
| `test_the_patch_carries_a_new_file_the_agent_staged` | None needed — failed on the pre-change `git diff`. | `assert 'src/money.ts' in patch.diff` failed; the diff named only `src/billing.ts`. |
| `test_a_patch_that_is_only_a_new_file_is_not_read_as_a_remediator_that_changed_nothing` | None needed — failed on the pre-change `git diff`. | `assert patch.diff.strip()` failed on `''`. |
| `test_the_patch_omits_a_file_the_agent_left_unstaged` | Inserted `subprocess.run(["git", "add", "-A"], ...)` at the top of `_git_diff`. | Red: the diff carried `build/bundle.js`. |
| `test_an_agent_that_created_files_and_staged_none_is_told_that_rather_than_reported_as_no_change` | None needed — `DID NOT RAISE RuntimeError` before the implementation. | — |
| `test_an_agent_that_changed_nothing_at_all_is_still_reported_as_changing_nothing` | Changed `if unstaged:` to `if True:` in `propose`. | Red: `RuntimeError: the agent created  and staged none of them`. |
| Three prompt tests (`..._how_to_make_a_new_file_part_of_the_patch`, `..._does_not_let_the_agent_stage_everything`, `..._names_the_tree_the_verification_gate_measures`) | None needed — failed against the old `_SCOPE_RULES`. | — |

### `tests/test_github_forge.py`

Both use the existing `remote` fixture — a real bare repository and a real shallow clone, not
a stub — because what the clone holds and what the push delivered are the two things they
exist to tell apart. Each asserts on `git ls-tree -r --name-only <branch>` read from the bare
repository.

| Test | Mutation | Result |
|---|---|---|
| `test_push_branch_carries_a_new_file_the_patch_needed` | Inserted `self._run(["git", "reset"], path)` before the `git add -u` — the "push undoes the staging" failure the brief names. | Red: `assert 'money.ts' in ['file.txt']`. |
| `test_push_branch_leaves_behind_a_file_the_agent_never_staged` | Replaced `git add -u` with `git add -A`. | Red: `assert 'build/bundle.js' not in ['build/bundle.js', 'file.txt', 'npm-debug.log']`. |

The debris test uses `build/bundle.js` and `npm-debug.log`, neither gitignored, deliberately.
Ignored paths are excluded by git itself, so a debris assertion resting on them would hold
even with the staging widened to `-A` and would prove nothing.

Both new push tests also assert `file.txt` still reads `patched` on the remote, so an empty
commit cannot satisfy them for the wrong reason.

**The ordinary single-file modification is still pinned exactly as before.**
`test_push_branch_issues_the_expected_git_sequence_for_a_new_branch` asserts the full argv
list including `["git", "add", "-u"]`, and it is untouched and green — the staging command
did not change, so that test is the proof rather than a casualty.

## Documentation drift I could not fix, since B3 holds `src/sync/index/`

Three paragraphs now describe an instruction that has changed. All are prose; none affects
behaviour.

**1. `src/sync/index/shipped_tree.py`, module docstring, first paragraph.** It reads:

> `push_branch` commits `git add -u` -- the index, plus tracked modifications -- so every
> untracked and every ignored path in the clone is content the branch will not have. The
> patch agent holds `Bash` and `Write` and is told to run `npx tsc --noEmit` until it is
> clean, which it can do by creating exactly such a file.

The first sentence is still exactly right and was already written the correct way round —
"the index, plus tracked modifications" is precisely what makes staging-as-assertion work.
What is missing is that this is now *relied on*: a staged new file is kept in the tree on
purpose, and `_UNSHIPPED` being exactly `{"??", "!!"}` is what keeps it. The second sentence
also describes an instruction that no longer exists in that form — the agent is no longer
told to run tsc "until it is clean" (that was removed in an earlier task) and is now told to
stage anything it adds before running it.

Suggested addition, after the first paragraph:

> A file the agent staged is not held aside. Git reports it as `A `, and `_UNSHIPPED` is
> exactly `{"??", "!!"}`, so it stays in the tree and the gate compiles it — which is the
> whole mechanism by which a patch that needs a new module can be verified and shipped.
> Adding `"A "` to that set would read as tightening and would break that path silently.

**2. `src/sync/index/typescript.py`, `prepare`'s docstring, first paragraph.** "The patch
agent runs with `Bash` in hand and is instructed to run its own `npx tsc --noEmit` until it
is clean" — the instruction says neither "until it is clean" nor anything about staging any
more. It now reads, in `_SCOPE_RULES`: run it once the edit is made, after staging anything
added, so that it measures the same tree the branch will carry.

**3. `src/sync/index/typescript.py`, `static_verify`'s docstring, the two-subtractions
paragraph.** "The agent's untracked and ignored files are held out of the way for the
compile, because `push_branch` will not carry them" is still true as written, but it is now
half the rule. The other half is that a file the agent *staged* is neither untracked nor held
aside, and is measured for the same reason: because `push_branch` will carry it.

This is the paragraph the coordinator flagged as most likely to be rewritten by B3, which is
why none of the three were touched.

## Anything the brief did not mention

- **`CLAUDE.md` has a sentence that is now understated.** Under "Nothing reaches a pull
  request unverified": "`git add -u` never stages a new file, so a patch that needs one fails
  verification rather than pushing a branch without it." That gap is closed for a file the
  agent stages. The honest replacement is that a new file reaches a branch only when the
  agent stages it, and that a file it leaves unstaged still fails verification. Not edited —
  `CLAUDE.md` is shared and B3 may be revising the same section.
- **A test in my own file was git-initialising a repository with no commit.**
  `test_a_patch_carries_its_findings_rationale_verbatim` called `git init` and nothing else,
  which `git diff` tolerated and `git diff HEAD` does not — an unborn HEAD names nothing. It
  now seeds a commit, with a comment saying that a repository with no commit is a shape of
  that fixture and not of anything the pipeline sees. No fallback was added to `_git_diff`
  for it: every clone Sync works in has a commit.
- **The `sync_b1` database did not exist** and 53 tests errored at setup on it. Created with
  `CREATE DATABASE sync_b1;` against the container on 5433. Worth knowing if another worker
  is handed the same DSN line.
- **`_ci_feedback` in `nodes.py` is still accurate.** It says `push_branch` has already
  committed the patch so `git diff` in the clone is empty. That holds for `git diff HEAD`
  too, since the commit is HEAD.

## Gates

Run from a clean tree on `aeecde4`, unredirected:

- `uv run pytest` — 767 passed, 1 deselected (the e2e test, left to the coordinator).
- `uv run lint-imports` — `sync.core depends on nothing KEPT`. Contracts: 1 kept, 0 broken.
- `uv run python scripts/lint_encoding.py src tests` — no output.

Every `subprocess.run` added here passes `encoding="utf-8"` explicitly.
