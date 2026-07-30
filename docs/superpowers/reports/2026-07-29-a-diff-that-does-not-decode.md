# A diff that does not decode

M3-W101, 2026-07-29. `scripts/subprocess_encoding_baseline.txt` carried one entry with a
measurement behind it rather than a suspicion: `git diff HEAD` in
`sync.remediate.agent_patch._git_diff`. This is the reproduction, the route taken, the route
refused and why, and what turned out to be true of the call beside it.

## The reproduction

A git repository holding one tracked `.ts` file, committed as ASCII and then rewritten in
cp1252 — `export const caf\xe9 = "montr\xe9al";`, written with `write_bytes` so nothing
repairs it. `git diff HEAD` copies file content onto the pipe verbatim, so the child emits
those bytes unchanged:

    git diff HEAD, read as bytes
      returncode: 0
      stdout (188 bytes): b'diff --git a/src/billing.ts b/src/billing.ts\nindex 7e15a4a..acf4e0e
                            100644\n--- a/src/billing.ts\n+++ b/src/billing.ts\n@@ -1 +1 @@\n
                            -export const legacy = 1;\n+export const caf\xe9 = "montr\xe9al";\n'
      decode('utf-8'): UnicodeDecodeError: invalid continuation byte, position 172

Read the way `_git_diff` read it — `text=True, encoding="utf-8", check=True`:

    _git_diff(...) -> returned None
    threading.excepthook captured:
      on thread 'Thread-9 (_readerthread)': UnicodeDecodeError: 'utf-8' codec can't decode
      byte 0xe9 in position 172: invalid continuation byte

Exit code 0. No exception at the call site. `stdout` is `None`. `threading.excepthook` is
what establishes *where* the failure happened rather than only that output went missing,
which is the same instrument `tests/test_subprocess_encoding.py` uses and the reason this is
a defect and not a preference: it fails on a thread no caller can reach.

### One correction to the baseline entry's account

The entry says the `None` travels on and "the `TypeError` arrives somewhere that does not
name this call". Measured, it does not get that far. `Patch.diff` is typed `str` and pydantic
rejects the `None` one line later:

    pydantic_core._pydantic_core.ValidationError: 1 validation error for Patch
    diff
      Input should be a valid string [type=string_type, input_value=None, input_type=NoneType]

The `TypeError` and the `AttributeError` are both real and both reachable — `nodes.py:68`
joins `patch.diff` into the patch agent's CI-retry prompt and `nodes.py:248` calls
`.strip()` on it — but pydantic gets there first, so neither is what an operator sees.

This makes the defect quieter rather than louder, which is worth recording. `make_patch`
catches `Exception` around `propose` and turns it into `_describe(exc)`, which becomes both
the abandon record's `diagnostics` and the next attempt's `feedback`. So the patch agent was
being handed a pydantic message about `NoneType` as its instruction for what to fix, burning
its remaining attempts on it before the run abandoned. Nothing crashed and nothing named the
customer file that caused it.

## The route taken

`_git_diff` stops decoding at the subprocess boundary and decodes in the parent, where the
failure can raise:

    result = subprocess.run(
        ["git", "diff", "HEAD"], cwd=repo_path, capture_output=True, check=True,
    )
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(...)

The refusal names the file and the call, which is the whole of what the defect cost:

    `git diff HEAD` produced bytes that are not UTF-8: src/billing.ts holds byte 0xe9 at
    offset 172 of the diff. A patch is data and is refused rather than decoded leniently;
    re-encode that file as UTF-8 [finding=f-42 repo=acme-billing]

and `threading.excepthook` now captures nothing at all, which is the other half of the
measurement inverted.

This is both of the shapes the baseline named rather than a choice between them. Reading
bytes is what removes the reader-thread decode, so the failure becomes catchable; refusing is
what happens once it is caught. The precedent for the second half is
`sync.cli._literal_call_sites`, which skips a customer source file it cannot decode and
prints the path.

Two properties come free and are held by tests rather than asserted. The call now satisfies
`tests/test_subprocess_encoding.py` by route 1 — it does not decode — so it needs neither an
exemption nor an `errors=`. And a diff of ordinary ASCII is compared byte-for-byte against
what the child emitted, not for a substring, because the diff *is* the data.

### Naming the file

`UnicodeDecodeError` carries a byte offset into the diff, not a path. `_undecodable_path`
maps one to the other by scanning the diff's own headers: a byte that is not UTF-8 can only
be file content, because headers, hunk ranges, index lines and mode lines are ASCII by
construction, so the byte always sits inside a hunk and the last destination header before it
owns the file.

A `+++` line counts as a header only where a `---` line precedes it. Inside a hunk an added
line whose content is `++ b/elsewhere.ts` renders as `+++ b/elsewhere.ts`, and a customer
repository that keeps patch files under version control has them; read naively that names a
file which is not in the diff at all. A deletion has `+++ /dev/null`, so the path comes off
the `---` side instead.

The path itself is decoded with `errors="replace"`. It is diagnostic rather than data at that
point, and `core.quotepath` has usually already reduced it to ASCII escapes.

## The route refused, and why

**`errors="replace"` corrupts the patch.** Both non-ASCII characters in the measurement come
back as the same replacement character, so a diff read that way applies bytes the customer
did not write. `tests/test_decode_handlers.py::_drive_literal_call_sites` records this
shipping once already: `_literal_call_sites` read customer sources leniently until B57, where
a mangled `operation_id` became a call site joined against a model nothing retires.
`test_a_diff_carrying_legitimate_non_ascii_utf_8_comes_through_intact` is the assertion that
rules it out here.

**An exemption asserts something false.** An exemption says the child cannot emit non-UTF-8.
This one demonstrably can, and the measurement above is what it emitted.

**Reading bytes end to end is a much larger change than it looks, and it was not taken.**
The brief asked for every consumer of `Patch.diff` to be established before choosing it. They
are:

| consumer | what it does with `diff` | survives `bytes`? |
|---|---|---|
| `sync/core/conformance.py:306` | `if not isinstance(diff, str)` — fails a third-party remediator that returns anything else | no, and it is a published contract |
| `sync/core/conformance.py:311,318,323` | `diff.strip()`, three times | works on bytes, means a different thing to an author reading the kit |
| `sync/remediate/serde.py:21` | `Patch` is in `CHECKPOINTED_TYPES`, serialised into the graph's Postgres checkpoints | no, needs a codec |
| `sync/mcp/tools.py:242` | `"diff": patch.diff` inside a JSON envelope | no, bytes is not JSON-serialisable |
| `sync/remediate/nodes.py:68` | `"\n".join([..., patch.diff])` into the patch agent's CI-retry prompt | no, `TypeError` |
| `sync/remediate/nodes.py:248` | `proposed.diff.strip()` routing an empty diff | works, silently |
| `sync/remediate/literal_swap.py:110` | constructs `Patch(diff=<str>)` | no |
| `sync/remediate/parameters.py:106` | constructs `Patch(diff=<str>)` | no |
| `sync/remediate/property_omit.py:128` | constructs `Patch(diff=<str>)` | no |
| `sync/remediate/corpus.py:295` | constructs `Patch(diff="")` | no |
| `sync/core/conformance.py:341` | `_NO_PATCH = Patch(diff="", ...)` | no |

That reaches the graph's checkpoint serialisation, a pull-request-adjacent prompt body, the
MCP tool surface, and the conformance kit a third party writes an adapter against — three of
them in modules this task was forbidden to edit (`sync/mcp/`, `sync/remediate/nodes.py`). The
brief's instruction was to stop and report at exactly that point, so `Patch.diff` is
unchanged and `src/sync/core/models.py` was not touched.

The cost of not taking it is real and worth stating: a customer repository with a file in a
legacy encoding gets no patch for a call site in that file until somebody re-encodes it.
Lenient decoding recovered a patch there, and recovered it wrong. `route_after_patch` already
handles a refusal — the message goes into the abandon record and back to the next attempt —
and `abandon_reason` staying queryable is how routing learns which repositories this hits.

## `_unstaged_additions` was a different question, and got a different answer

It takes a measured exemption rather than a fix, and it keeps `text=True, encoding="utf-8"`
exactly as it was.

The audit had measured `git ls-files -z` and found `b'caf\xc3\xa9.ts'`. This call passes no
`-z`, and `-z` is precisely what disables `core.quotepath`, so the earlier measurement did not
transfer and both settings had to be checked. Against a clone holding an untracked
`src/café.ts`:

| `core.quotepath` | `git ls-files --others --exclude-standard` | ASCII? | decodes as UTF-8? |
|---|---|---|---|
| `true` (git's default) | `b'"src/caf\\303\\251.ts"\n'` | yes | yes |
| `false` | `b'src/caf\xc3\xa9.ts\n'` | no | yes |
| `true`, with `-z` | `b'src/caf\xc3\xa9.ts\x00'` | no | yes |
| `false`, with `-z` | `b'src/caf\xc3\xa9.ts\x00'` | no | yes |

So the exemption is honest at both settings, and for two independent reasons rather than one:
with quoting on, git escapes the path to pure ASCII; with it off, the path arrives as the
UTF-8 git stores internally, converted from NTFS's UTF-16. This child reports paths, and git
owns their encoding either way. `git diff HEAD` is different in kind because it copies
content, and content is the customer's.

`tests/test_agent_patch.py::test_git_cannot_hand_this_call_a_path_that_is_not_utf_8` is
parametrised over both settings and is what establishes this rather than restating it.

**M3-W82's guard decides exactly what it decided.** The bytes reaching it are identical —
nothing about the call changed — and the six tests covering it are unchanged and green,
including the two that assert a refusal names the path. One test was added for a non-ASCII
path: at `core.quotepath`'s default the guard names `src/caf\303\251.ts`, the escaped
spelling git handed it, and still refuses.

### One thing left, deliberately

`_unstaged_additions` ends in `result.stdout.split()`, which splits on any whitespace. With
quoting on, a path containing a space arrives quoted as `"a b.ts"` and splits into two
entries. The guard's decision is unaffected — a non-empty list refuses either way — so
changing it would change what M3-W82's guard reports, which this task was told not to do. It
is a message-quality defect, not a correctness one, and it belongs to whoever revisits that
guard.

## Non-vacuity

Every assertion below failed before the change and passed after, on the reproduction rather
than on a stub. The seven that failed first were: the refusal naming the file, the refusal
arriving at the caller rather than a reader thread, the ASCII diff being byte-identical, the
UTF-8 diff surviving intact, the correct file being named among several changed, and the two
`_undecodable_path` cases.

`tests/test_decode_handlers.py` is the other gate this change had to answer, and it is worth
recording that it fired unprompted. A new `except UnicodeDecodeError` in `src/` is a decode
handler with no driver, and the suite failed by name:

    no test has ever entered these decode handlers, so nothing is known about what they do
    with undecodable bytes:
      sync/remediate/agent_patch.py:240

`_drive_git_diff` is the driver, and because that file attributes by exception type through
`sys.monitoring`'s `EXCEPTION_HANDLED` event, it establishes the handler was entered by a
real `UnicodeDecodeError` and not merely that the line was executed.

### Mutation

Fifteen mutations. Thirteen behavioural, all killed; two demonstrating harness failure modes
deliberately. The harness distinguishes four outcomes because all four have produced false
verdicts on this project: it passes `--color=no`, `compile()`s each mutant before writing it,
puts `PYTHONIOENCODING=utf-8` in every child environment and reads that output with
`errors="replace"`, runs `-n0` so a mutation that breaks import is not a worker crash, reads
pytest's exit code explicitly rather than only scanning for `FAILED`, and measures the clean
tree before and after — refusing to score anything if the count moves.

| mutation | verdict | killed by |
|---|---|---|
| `_git_diff` back to the old `text=True` form | killed | the reproduction, the ASCII byte-identity test, and the UTF-8 intactness test |
| `_git_diff` decodes with `errors="replace"` | killed | the reproduction, and both decode-handler gates |
| the refusal stops naming the file | killed | the reproduction, and both decode-handler gates |
| the refusal stops naming the call | killed | the reproduction |
| the refusal drops the finding identity | killed | the reproduction |
| the refusal returns an empty diff instead of raising | killed | the reproduction, and both decode-handler gates |
| `_undecodable_path` names the first header, not the last | killed | the multi-file test, and the header test |
| `_undecodable_path` drops the `--- `-above guard | killed | the `+++`-inside-a-hunk test |
| `_undecodable_path` drops the `/dev/null` side-swap | killed | the deleted-file test |
| `_undecodable_path` leaves the `b/` prefix on | killed | three header tests |
| `_unstaged_additions` loses its exemption marker | killed | `test_every_decoding_subprocess_call_in_src_states_a_defence` |
| `_unstaged_additions` exemption gives no reason | killed | the same, by the marker-with-no-reason arm |
| the two retired baseline entries are put back | killed | `test_no_baseline_entry_has_stopped_describing_a_violation` |
| an unclosed paren in `_undecodable_path` | did-not-compile | reported, not scored |
| `SystemExit` at module import | unreadable | exit 3 with zero `FAILED` lines, reported, not scored |

All four false-verdict modes were demonstrated rather than guarded against on faith:

- **colourised summary.** With `--color=yes` and two genuinely failing tests,
  `startswith("FAILED ")` matched **0** lines — the line is
  `'\x1b[31mFAILED\x1b[0m tests/test_agent_patch.py::\x1b[1mtest_...'`. The same run with
  `--color=no` matched 2. A real kill reads as a survival.
- **did-not-compile.** The unclosed paren above raised `SyntaxError: '(' was never closed` at
  `compile()`, before anything was written to disk.
- **unreadable.** `SystemExit` at import returned exit 3 with zero `FAILED` lines. Scanning
  only for `FAILED` scores that as a survival; reading the exit code does not. Exit 5 —
  nothing collected — was checked the same way and is also not a kill.
- **baseline-drifted.** Removing the exemption marker before starting the run made the clean
  tree fail; the harness reported `baseline-drifted: exit 1` and scored nothing at all.

**The first pass had one survivor, and it was the test's fault rather than the mutation's or
the code's.** Dropping the `--- `-above guard survived. The fixture meant to exercise it
contained `++ b/elsewhere.ts` where the collision needs three `+` characters — git's marker
for an added line, then the content's own two — so the line never matched `+++ ` at all and
the guard was never reached. The docstring described a case the bytes did not contain. Fixed
by composing the line as `b"+" + content` and asserting on the fixture itself, so a test that
stops describing the collision fails instead of passing vacuously. That is the fifth time on
this project the survivor has been outside the production code.

## The baseline shrank

Both entries deleted, in the commit that defends them:

    sync/remediate/agent_patch.py:_git_diff
    sync/remediate/agent_patch.py:_unstaged_additions

with the comment block above them, since it described only those two. Three entries remain,
in `sync/cli.py` and `sync/index/typescript.py`, each still naming the task that retires it.

## What this leaves for somebody else

- **`sync/cli.py` needs no change for the refusal.** It was read as the precedent and not
  edited. `_literal_call_sites` already skips and names an undecodable file; nothing about
  this change asks anything more of it.
- **`.split()` in `_unstaged_additions`**, above.
- **The other two baseline entries**, M3-W98/a and M3-W98/b, unchanged and still owned.
