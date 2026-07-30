# Fifteen subprocess calls against the rule written today

M3-W98, 2026-07-29. `CLAUDE.md` gained a paragraph today saying that `encoding="utf-8"` on a
`subprocess.run` does not choose the child's encoding. Nothing in the repository had been checked
against it. This is the inventory, what measuring each call site established, and the check that
now holds the answer.

## The rule, reproduced

The paragraph came from a measurement, and it reproduces here exactly. A Python child with no
`PYTHONIOENCODING` in its environment writes the locale codepage:

    child emitted: b'caf\xe9 \x97\r\n'      # cp1252, for the string `café —`

Read the way fourteen of the fifteen calls in `src/` read their children, that comes back as:

    subprocess.run([...], capture_output=True, text=True, encoding="utf-8")
    -> returncode 0, stdout None
       UnicodeDecodeError raised on Thread-3 (_readerthread)

Exit code zero. No exception at the call site. `stdout` is `None`, so the next line that
concatenates it raises `TypeError` somewhere that does not name the subprocess. Both remedies
behave as the paragraph says: `PYTHONIOENCODING=utf-8` in the child's environment returns
`'café —'` faithfully, and `errors="replace"` returns `'caf� �\n'` — no crash, but the
accent and the dash have collapsed into the same character.

`tests/test_subprocess_encoding.py` holds all four of those as tests. The one that matters most is
`test_the_old_form_loses_stdout_on_a_child_that_chooses_its_own_encoding`, which installs a
`threading.excepthook` and asserts on both halves: that `stdout` is `None`, and that the
`UnicodeDecodeError` was raised on a thread. The second half is the claim that makes this a defect
rather than a preference — the failure happens where no caller can catch it.

## The inventory

Fifteen calls, eleven modules. Twelve failed the check on its first run. Three already satisfied
it. **Not one of the fifteen spawns a Python process**, which is the single most consequential
finding for how the check had to be written.

| call site | child | Python? | can the rule bite it | disposition |
|---|---|---|---|---|
| `cli.py:247` `_clone` | `git clone` | no | no — reads bytes, never decodes | already satisfied |
| `cli.py:248` `_clone#1` | `git rev-parse` | no | no — a hex SHA | baseline, M3-W98/a |
| `cli.py:256` `_git` | `git`, argv from caller | no | not established — callers not enumerated | baseline, M3-W98/a |
| `forge/github.py:124` `GitHubForge._run` | `git`/`gh`, argv from caller | no | measured UTF-8, but the child is not fixed | fixed: `errors="replace"` |
| `index/dependency_edits.py:125` | `git ls-files -z` | no | no — git emits UTF-8 paths | exempt, measured |
| `index/deps.py:89` | `npm`/`pnpm`/`yarn` shim | no | measured UTF-8 | fixed: `errors="replace"` |
| `index/shipped_tree.py:90` | `git status -z` | no | no — git emits UTF-8 paths | exempt, measured |
| `index/tsc.py:155` | `tsc` or `npx` | no | measured UTF-8 | fixed: `errors="replace"` |
| `index/typescript.py:578` | `git diff --name-only` | no | no — quoted path list | baseline, M3-W98/b |
| `remediate/agent_patch.py:196` | `git diff HEAD` | no | **yes, reproduced** | baseline, M3-W98/c |
| `remediate/agent_patch.py:210` | `git ls-files --others` | no | no — quoted path list | baseline, M3-W98/c |
| `signals/oasdiff.py:64` | `oasdiff breaking` | no | no — Go via `encoding/json` | exempt, measured |
| `signals/oasdiff.py:88` | `oasdiff checks` | no | no — Go via `encoding/json` | exempt, measured |
| `signals/stripe/adapter.py:55` | `gh api` | no | no — reads bytes, never decodes | already satisfied |
| `verify/replay.py:337` | `node` | no | no — already passes `errors="replace"` | already satisfied |

Two corrections to the brief's framing, both from counting by AST rather than by grep. Thirteen
calls decode, not fourteen: `cli.py:247` and `signals/stripe/adapter.py:55` both read bytes on
purpose. And `signals/oasdiff.py:88`, the call the new paragraph quotes verbatim, is the shape of
the rule without being an instance of it — oasdiff is a Go binary answering through
`encoding/json`, which replaces invalid byte sequences before they reach the pipe. Measured against
the pinned binary, its output is UTF-8. The brief was right to make that a question.

### The one call whose defect is reproduced

`git diff` copies file content onto the pipe verbatim. Against a repository holding one cp1252
source file:

    git diff HEAD -> rc=0, NOT utf-8: can't decode byte 0xe9 in position 130
    read the old way -> stdout is None

That is `remediate/agent_patch.py:196` `_git_diff`, whose `return result.stdout` then hands `None`
onward as the patch's diff. It is the only one of the fifteen with a measurement rather than a
suspicion behind it, and it is in a module this task could not edit. It is the follow-up to
dispatch first.

Neither cheap route fixes it. A diff is data, so `errors="replace"` would corrupt the patch, and
there is nothing to exempt because the child genuinely does emit non-UTF-8. Reading the diff as
bytes, or refusing the file the way `sync.cli._literal_call_sites` refuses one it cannot decode, is
the shape of the answer.

### What was measured, per child

- **`git`, path-output commands.** UTF-8. Windows stores NTFS names as UTF-16 and git converts
  them; an accented filename came back as `b'caf\xc3\xa9.ts'`. The commands without `-z`
  (`ls-files --others`, `diff --name-only`) are safer still, because git's `core.quotepath`
  octal-escapes non-ASCII into pure ASCII.
- **`git`, content-output commands.** Not UTF-8. `git diff HEAD` is the only one in `src/`.
- **`git commit -m`.** Echoes the message back as UTF-8, `b'... receipt_email \xe2\x80\x94 ...'`,
  which matters because `forge/github.py` builds that message from `patch.rationale` — model-written
  prose that routinely carries an em dash.
- **`oasdiff`.** UTF-8. Go, through `encoding/json`.
- **`npm`, `pnpm`, `npx`.** UTF-8, including their failure output. These resolve to `.CMD` shims
  over cmd.exe, and the console codepage here is 437, so the shim layer was the thing worth
  checking rather than assumed.
- **`node`.** UTF-8.

## What the check requires, and why not one literal spelling

`PYTHONIOENCODING=utf-8` is the remedy the paragraph names, and a check demanding that literal
would have been wrong in the expensive direction. No child in `src/` is a Python process, so none
of them reads that variable. The check would have fired on all thirteen decoding calls, and every
one would have been silenced by setting an environment variable the child ignores — a green gate
over an unchanged defect, which is worse than no gate.

Requiring `errors="replace"` everywhere is wrong in the other direction, because it is lossy.
Both characters in the measurement above came back as the same replacement character. Where the
output is data that is a silent corruption, and this repository has shipped it once already:
`tests/test_decode_handlers.py::_drive_literal_call_sites` records `_literal_call_sites` reading
customer sources that way until B57, where a mangled `operation_id` became a call site joined
against a model nothing retires. `CLAUDE.md` scopes `errors="replace"` to output that is
"diagnostic rather than data" for exactly that reason.

So the check requires that a choice has been made, and accepts four routes:

1. **The call does not decode** — no `text=`, `encoding=`, `errors=` or `universal_newlines=`.
2. **`errors=` is passed** — the decode cannot raise. Cost: mojibake.
3. **`env=` is passed and the expression names `PYTHONIOENCODING`** — the only route that keeps the
   output faithful, and the only one available when the output is data and the child is Python.
4. **An exemption marker carrying a reason** — `# subprocess-encoding: allow - <why>` on any line
   the call spans. A marker with nothing after `allow` is itself reported, copying
   `scripts/lint_dead_links.py`: an opt-out that says nothing is how a check decays into
   decoration.

Route 4 is what keeps the check satisfiable when the honest answer is "this child cannot emit
non-UTF-8, and here is how I know". Route 2 is what keeps it satisfiable for everything else. The
combination fires on no correct code and can always be answered.

### `errors="replace"`: in the guidance, not in the check

The brief asked whether it belongs in the check. It does not, and the reason is that the check
cannot tell data from diagnostics — which is the distinction the rule turns on. What went in
instead is the requirement to choose, and the choice is recorded at each of the seven call sites
this task owns:

- **Diagnostic, so `errors="replace"`.** `index/tsc.py` (a typecheck diagnostic string;
  `parse_diagnostics` matches `file(line,column): error TSxxxx:`, which is ASCII, so a replacement
  character can only land inside a message a human reads), `index/deps.py` (read only by the
  `RuntimeError` it raises), `forge/github.py` (stderr into a `RuntimeError`; the load-bearing
  stdout values are hex SHAs, branch names, and gh's JSON numbers and URLs, all ASCII by
  construction).
- **Data, so a measured exemption.** `index/shipped_tree.py` and `index/dependency_edits.py` hand
  back paths — a replacement character there silently moves a file between shipped and unshipped,
  or hides an edit inside `node_modules`. `signals/oasdiff.py` hands back `kind`, `operation_id`
  and the whole of `raw`.

`forge/github.py` is the one where the two arguments met. Its child measures as UTF-8, which would
support an exemption, but `_run` takes its argv from the caller and nothing in the function
constrains what the child is. An exemption there would be a claim about callers not yet written, so
it took `errors="replace"` instead.

## Baseline rather than fifteen fixes

Five entries in `scripts/subprocess_encoding_baseline.txt`, all in modules a live task holds. It
may only shrink: an entry that stops describing a violation fails the gate until it is deleted, in
the commit that fixed it. The seven this task owned were opened in the same run and closed again,
which is the mechanism demonstrated on real code rather than only compiled.

The key is `<path>:<enclosing qualname>`, not `<path>:<line>`.
`tests/test_decode_handlers.py` pays a real price for a positional key — it re-anchored seven keys
in one afternoon over added comment blocks — and says in its own docstring that there is no stable
identity to key on instead. For a `subprocess.run` there is one: the function that holds it. An
edit above the call does not move the key, and
`test_a_key_does_not_move_when_a_line_is_added_above_the_call` holds that. Two calls in one
function are disambiguated by `#<n>` in line order, which is positional again but only within a
single function body.

The follow-ups, in dispatch order:

- **M3-W98/c**, `src/sync/remediate/` — `_git_diff` and `_unstaged_additions`. The reproduced one.
- **M3-W98/a**, `src/sync/cli.py` — `_clone#1` and `_git`. `_git` takes caller argv; enumerate them.
- **M3-W98/b**, `src/sync/index/typescript.py` — `_baseline`. Likely the same measured exemption
  `shipped_tree.py` now carries.

`test_every_baseline_entry_names_the_task_that_retires_it` enforces that each entry has an owner in
the comment block above it, because debt with no owner is a permanent exemption wearing a different
hat.

## Non-vacuity

**A violation constructed in real source.** A seventeenth `subprocess.run` was appended to
`src/sync/signals/oasdiff.py`, decoding with no defence. The check reported it by key and line:

    sync/signals/oasdiff.py:229 (sync/signals/oasdiff.py:_constructed_violation) decodes the
    child's output with no defence against the child choosing its own encoding

Giving that same call `errors="replace"` returned the suite to green, and the call was then removed.
The baseline did not absorb it, which is the property that matters: a new violation is not covered
by an existing entry.

**The shrink-only property.** Re-adding `sync/index/tsc.py:run_tsc` to the baseline after it was
fixed failed `test_no_baseline_entry_has_stopped_describing_a_violation` by name.

**Mutation.** Twenty-one mutations, all killed; no survivors, nothing that failed to compile, and
the tree verified green before and after the run. The first pass had **six survivors**, and every
one was a missing test rather than a mutation artefact or a fault in `src/` — the fourth time on
this project the fault has been outside the production code. Three of the six shared one cause, and
it is the failure the brief warned about: `test_every_decoding_subprocess_call_states_a_defence`,
`test_no_baseline_entry_has_stopped_describing_a_violation` and
`test_every_baseline_entry_names_the_task_that_retires_it` each asserted only that `src/` as it
stands is clean. A test whose sole input is the repository in its current state can fail only when
the repository is dirty, so deleting the decision it tests leaves it green — `new = []` survived.
The fix was to extract the three decisions into `unbaselined`, `stale_entries` and
`entries_without_a_retiring_task` and drive them with synthetic input as well as the real tree.
The other three survivors were untested branches the docstring had claimed: a computed `text=`
flag, a marker on a line other than the call's first, and an `env=` that does not name
`PYTHONIOENCODING`.

The harness distinguishes four outcomes rather than two, because this task's own subject is a
harness reading a false verdict. All four were demonstrated rather than asserted: a mutant with an
unclosed paren reported `did-not-compile`; one raising `SystemExit` at import reported `unreadable`
rather than counting as a kill or a survival; removing `errors=` from `tsc.py` before the run
reported `baseline-drifted` and refused to score anything. Every child the harness spawns gets
`PYTHONIOENCODING=utf-8` and is read with `errors="replace"`, and pytest is given `--color=no`, so
the harness cannot suffer the defect it is measuring.
