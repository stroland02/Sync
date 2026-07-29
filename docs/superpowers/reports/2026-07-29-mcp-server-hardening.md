# Hardening `sync.mcp.server`: what the seventeen unexecuted statements were doing

**Date:** 2026-07-29
**Task:** M3-W83
**Scope:** `src/sync/mcp/server.py` — the four frozen tools and the `sync://feed/{vendor}`
resource are reached through this module and nothing else, and it was the least-covered file in
the tree.

## The measurement

Both figures come from the same command, against a database no other task was using:

```
uv run pytest -q --cov=sync.mcp.server --cov-report=term-missing
```

| | Statements | Missed | Covered | Missing lines | Tests |
|---|---:|---:|---:|---|---:|
| Before | 96 | 17 | 82% | `88, 200-201, 275-295, 299` | 2028 passed, 1 skipped |
| After | 106 | 0 | 100% | — | 2036 passed, 1 skipped |

The statement count rises by ten because the defect described below was fixed, not because the
denominator was massaged: eight of the ten are the two guards and their error frames, and two
are the constants for the JSON-RPC codes they return.

`docs/superpowers/specs/2026-07-29-sync-coverage-baseline-2.md` reported this module at 82% and
qualified the number in a way this task confirms: eleven of the seventeen were `main()`, which
`tests/test_mcp_entry_point.py` already drove through a real subprocess, and coverage could not
see it because it measures the process it runs in. That qualification was right about the
mechanism and wrong about the conclusion it invites. Three separate claims `main()`'s docstring
makes had no assertion anywhere, in this process or a child one, and two of them are silent
when broken.

## What each newly covered statement does

**Line 88 — the `continue` on a blank line.** A blank line is not JSON, so without the skip it
draws a `-32700` parse error the client never asked for. An unrequested frame is worse than a
missing one: a client matching responses to requests in order is desynchronised for the rest of
the session. Blank lines are ordinary rather than exotic — a client writing CRLF endings emits
one wherever a frame boundary is written twice.

**Lines 200-201 — the broad `except Exception`.** The comment beside it says *"a tool fault must
not take the session down"*, and nothing established that it held. It has two ways to be wrong
and both are silent from the client's side: the exception escapes `serve` and the process dies
with the request unanswered, or it is caught and flattened into a message that says nothing
about what broke. The test now asserts the frame is a *result* carrying `isError` rather than a
protocol error, that it names the tool and the exception type and message, and that the request
after it is still answered.

**Lines 275-295 — `main()`.** Four separate contracts, each proven by a mutation below:

- A missing `SYNC_DSN` is an exit status and a line on stderr, decided *before* either stream is
  touched. A stdio server that reads stdin before deciding it cannot serve is indistinguishable
  to its client from one doing slow work — the client waits, the launcher waits, and nothing
  says why.
- `protocol = sys.stdout` is taken before `sys.stdout` is pointed at stderr, so frames land on
  the stream the client is reading and a stray `print` lands where a launcher shows it.
- `sys.stdin.reconfigure(encoding="utf-8")` is the one whose absence is invisible. Python decodes
  stdin with the machine's codepage — cp1252 here — and every MCP client sends UTF-8, so a
  request naming a non-ASCII path or symbol is mangled before the server sees it, and
  `json.dumps` escapes the mangling on the way out. The server answers confidently about a string
  nobody sent.
- `protocol.reconfigure(encoding="utf-8")` needed a UTF-16 stream to demonstrate at all, and that
  is worth stating rather than hiding. Because `json.dumps` escapes non-ASCII, every frame this
  server writes is ASCII, and cp1252 encodes ASCII identically to UTF-8 — so the realistic
  mutation is unobservable. UTF-16 is not, which is what makes the outbound reconfigure testable.

**Line 299 — `raise SystemExit(main())`.** `sync-mcp` is one way in and
`python -m sync.mcp.server` is the other. A launcher taking the second learns whether the server
started only from the exit status, and a module guard that swallowed it would report every
misconfiguration as a clean shutdown.

## The defect: a frame that parses can still end the session

`serve` handled a line that was not JSON and did not handle a line that was JSON and was not a
request. Six shapes, all reachable from any client, were measured against the transport before
anything was written:

| Frame | Before |
|---|---|
| `42` | `AttributeError: 'int' object has no attribute 'get'` |
| `null` | `AttributeError: 'NoneType' object has no attribute 'get'` |
| `"hello"` | `AttributeError: 'str' object has no attribute 'get'` |
| `[1, 2]` | `AttributeError: 'list' object has no attribute 'get'` |
| `tools/call` with `params` as an array | `AttributeError: 'list' object has no attribute 'get'` |
| `resources/read` with `params` as an array | `AttributeError: 'list' object has no attribute 'get'` |

In every case the exception escaped `_handle`, escaped `serve`, and ended the process — having
written nothing. The client is not told; it waits on a response until the pipe closes under it.

Two of these are not client bugs. **A JSON-RPC 2.0 batch is an array**, and a server that does
not implement batching owes it `-32600 Invalid Request` rather than a dereference. **Positional
parameters are legal JSON-RPC**, and a server that takes none owes them `-32602 Invalid Params`.
A conforming client can end this server's session by conforming.

This is a system boundary in the sense `CLAUDE.md` uses the term — the bytes come from a client
nobody here controls — so validating the shape is the rule rather than an exception to it. The
fix is two guards: `serve` refuses a frame that is not an object, and `_handle` refuses `params`
that is present and not an object. The params guard sits in `_handle` once rather than at each
method that reads `params`, because `tools/call` and `resources/read` both index into it and a
method added later would have to remember to.

Both tests were written first and both failed with the `AttributeError` above, out of `serve`,
before the guards existed.

## The mutation table

These tests pin behaviour that already worked, so none of them could be red before its code was
written. Each was proven non-vacuous instead: the branch broken, the test watched to fail, the
source restored. `src/sync/mcp/server.py` was `sha256:cfa3506…` before the campaign and
`sha256:cfa3506…` after it — the harness asserted that itself and printed `RESTORED IDENTICAL`.

| # | Mutation | Test that caught it |
|---|---|---|
| 1 | `if not line.strip()` becomes `if False` — blank lines are parsed | `test_a_blank_line_between_frames_is_skipped_rather_than_answered` |
| 2 | `except Exception` narrowed to `except ValueError` | `test_a_tool_that_raises_is_answered_as_a_tool_error_and_the_session_survives` |
| 3 | The tool-fault message loses the exception type and text | `test_a_tool_that_raises_is_answered_as_a_tool_error_and_the_session_survives` |
| 4 | The request-object guard is disabled | `test_valid_json_that_is_not_a_request_object_is_refused_without_ending_the_session` |
| 5 | The params-object guard is disabled | `test_positional_parameters_are_refused_rather_than_dereferenced` |
| 6 | A missing `SYNC_DSN` returns `0` rather than `2` | `test_no_dsn_is_an_exit_status_rather_than_a_server_that_waits_on_a_stream` |
| 7 | The `SYNC_DSN` complaint is written to stdout | `test_no_dsn_is_an_exit_status_rather_than_a_server_that_waits_on_a_stream` |
| 8 | `sys.stdin` is left on the locale codepage | `test_the_entry_point_reads_its_stream_as_utf_8_whatever_the_locale_declares` |
| 9 | The protocol stream is left on the locale codepage | `test_the_entry_point_serves_the_stream_it_captured_and_hands_stdout_to_stderr` |
| 10 | `sys.stdout` is not handed to stderr | `test_the_entry_point_serves_the_stream_it_captured_and_hands_stdout_to_stderr` |
| 11 | Frames are written to stderr rather than the captured stream | `test_the_entry_point_serves_the_stream_it_captured_and_hands_stdout_to_stderr` |
| 12 | The module guard exits `0` rather than with `main`'s status | `test_running_the_module_as_a_script_exits_with_the_status_main_returned` |

Twelve mutations, twelve killed, none survived.

Mutation 8 is worth recording for a reason beyond the branch it covers. Breaking the stdin
reconfigure made pytest print cp1252 bytes, and the mutation harness — which had
`encoding="utf-8"` on its `subprocess.run` and no `errors=` — died with
`UnicodeDecodeError` **on the reader thread**, returned `stdout=None`, and surfaced as an
`AttributeError` four lines later on `None.splitlines()`. That is the failure `CLAUDE.md`
describes verbatim, reproduced by accident while testing the code that prevents it.

## What was not done, and why

**`tests/golden/tool_schemas.json` did not move.** `git hash-object` reports
`ac2cc141de7906790083729b23ace9b47302c300` before and after, and `git status` does not list it.
Nothing in this change touches a schema; both guards are transport-level and neither adds,
removes or renames a tool. `test_the_advertised_schemas_are_the_frozen_ones` already asserts the
four schemas against that file twice — once over the subprocess transport and once against
`schemas_as_data()` — so no test was added for it. A second copy of an assertion that already
exists is not coverage.

**One test was written and then deleted.** It drove `resources/read sync://feed/stripe` through
`main()` and asserted `-32002` with `reason: "not_fetched"`. It covered no statement the other
`main()` tests did not, and it could not do the job it was written for: `sync.mcp.resources.read`
returns `not_fetched` identically whether the cache is empty or absent, so the test cannot tell
that `main()` builds a `FeedCache` at all. Nothing observable distinguishes those two without a
stored snapshot, and no snapshot can be put into the cache `main()` builds from outside it. That
claim is therefore still unasserted, and saying so is better than a test that appears to cover it.

**A narrowness in `_call`'s error translation was found and left alone.** `dispatch` raises
`KeyError` for an unknown tool and `TypeError` for an unknown argument, and `_call` translates
both by type. A tool that raised either of those *internally* would be reported as "unknown
tool" or "bad arguments" — the first of which tells an agent a working tool does not exist. It
is not reachable today: no argument an agent can send makes any of the four handlers raise
`KeyError`, `GraphSurface._site_for` and `_change_for` already absorb the lookup errors the
graph produces, and a `TypeError` from a wrong argument *type* genuinely is a bad argument. So
there is nothing to fix that would not be error handling for a condition that cannot occur.
Recorded here because the reachability, not the shape, is what makes it safe — a fifth tool that
indexes a dictionary would change that answer.

## Gates

| Gate | Result |
|---|---|
| `uv run pytest -q` | 2036 passed, 1 skipped, exit 0 |
| `uv run python scripts/lint_encoding.py src scripts tests` | exit 0 |
| `PYTHONIOENCODING=utf-8 uv run lint-imports` | 1 contract kept, 0 broken, exit 0 |
| `uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` | exit 0 |
