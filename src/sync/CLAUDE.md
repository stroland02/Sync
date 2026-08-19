# The pipeline

Loads when you are editing Python. The root `CLAUDE.md` still applies.

## Encoding — the bug no test here can catch

**Always pass `encoding="utf-8"`** to `read_text`, `write_text`, `open`, **and
`subprocess.run(..., text=True)`**. On Windows all four default to cp1252, so any non-ASCII byte
corrupts or raises — and **every fixture in this repository is ASCII, so no test will ever catch
it.** It fails first against real vendor data or a real customer repository.

`subprocess` fails worst: a decode error is raised on the reader thread and never propagates.
`stdout` comes back `None` and the next line raises `TypeError` somewhere unrelated. **Also set
`PYTHONIOENCODING=utf-8` in the child's environment** — `encoding=` says how to decode the bytes,
not which bytes arrive, and a Python child on this machine emits cp1252 regardless. Pass
`errors="replace"` where the output is diagnostic rather than data.

For bytes that are not text, use `read_bytes`/`write_bytes` and do not decode.

Enforced by `scripts/lint_encoding.py`, and by a PostToolUse hook on every Python edit.

## Pipeline discipline

`specs/2026-07-27-sync-pipeline-discipline.md` carries the argument.

- **Declare a table's grain in `schema.sql` before adding a column.** One `migration_outcome` row is
  one *attempt*, not one finding. A query counting findings by counting rows is wrong, and quietly.
- **Every stage is idempotent.** Re-running INDEX, SIGNAL or DETECT on one input converges. Every
  table gets a natural key and an explicit conflict clause; `efcc19d` was this bug. **One exemption:**
  oasdiff-derived `vendor_change` rows do not converge — treat that source as at-least-once and never
  read a row count from it as a measurement.
- **Every binding carries its rung** (`static` / `resolved` / `observed`), and so does everything
  derived from it. Enforced: the rung is a column, and `insert_finding` refuses an unattributed finding.
- **Abandoned runs are data.** `abandon_reason` stays queryable — abandoned attempts are where routing
  learns which change kinds are not mechanically safe.

**Latency is a design constraint** (`specs/2026-07-25-sync-latency-architecture.md`): every agent must
shorten the critical path or improve a result. One consequence fails silently — **any state key written
by parallel branches must declare a reducer**, or concurrent writes are dropped with no error.

**Never detect a write by comparing against a live mtime.** Filesystems record mtimes far more coarsely
than the clock: 184 of 200 identical-byte rewrites left `st_mtime_ns` untouched. Backdate the baseline,
or make the content differ.

## Model configuration

Always `claude-opus-5`, adaptive thinking, `xhigh`. **The two surfaces spell it differently.**

```python
# Messages API — nested, takes a ceiling
model="claude-opus-5", thinking={"type": "adaptive"},
output_config={"effort": "xhigh"}, max_tokens=64000

# Agent SDK — flat, no output_config, no max_tokens
ClaudeAgentOptions(model="claude-opus-5", thinking={"type": "adaptive"}, effort="xhigh", ...)
```

Three containment facts, checked against the installed package (`0.2.128`, 45 fields):

- **`disallowed_tools` is a real block. Omitting from `allowed_tools` is not.**
- **A `can_use_tool` callback is shadowed by a whole-tool `allowed_tools` entry** — the SDK's own
  `_get_can_use_tool_shadowed_warning` says so. Use a `PreToolUse` hook instead. `hooks` works with a
  one-shot prompt; `can_use_tool` requires streaming mode.
- **The hang is a property of the default permission mode**, not headless mode. `PermissionMode`
  includes `dontAsk`.

`sandbox` accepts network `deniedDomains` and is **macOS/Linux only**, which is why B97's gate shipped
as a `PreToolUse` hook. `temperature`, `top_p` and `budget_tokens` return HTTP 400 on this model.

## Tests

`uv run pytest tests/ -q -n0`. Fixtures are committed — **no vendor API, no model API.** The one
end-to-end test is `@pytest.mark.e2e` and deselected by default.

**Never open an admin connection by hand.** `CREATE`/`DROP DATABASE` go through
`conftest.admin_connection` and `conftest.drop_database` — a bare `psycopg.connect(admin_dsn)` has no
`statement_timeout` and no `lock_timeout`, and B132 was a serial gate killed after 70 minutes blocked
in exactly that statement.
