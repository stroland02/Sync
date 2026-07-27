---
paths:
  - "src/sync/signals/**"
---

# Signal stage rules

You are editing a vendor adapter — the code that turns a vendor's artifacts into
`VendorChange` rows.

## `path_ptr` holds a URL path, not a JSON Pointer

`oasdiff.py` sets `path_ptr=record.get("path", "")`. That is oasdiff's **URL path** —
`/v1/charges` — not a pointer into a response body. Do not write code that treats it as a
JSON Pointer, and do not "fix" a caller by pointing it at `path_ptr` when it wants a field.

The field a change refers to lives in the free-text `text` message, as the first backticked
token, and `changed_field()` is the only supported way to get it. `b29795a fix: resolve the
patch prompt's affected field from oasdiff text, not the URL path` is this exact mistake,
already made and already fixed.

## `kind` is an oasdiff rule ID

`VendorChange.kind` is `record["id"]` — one of oasdiff's checker rule identifiers, of which
there are over two hundred. The authoritative list is whatever `oasdiff checks` emits for the
pinned binary version, not a hand-maintained copy. Any code that switches on `kind` needs a
default branch, and any table of kinds needs a test asserting it still covers what oasdiff
actually emits.

## Keep `raw`

`VendorChange.raw` retains the original record. Never drop it to save space, and never
normalise it on the way in. It is what lets a better extractor re-derive against stored
history instead of re-fetching every spec pair — which is precisely how `b29795a` was
applied retroactively.

## Vendor knowledge stops here

Stripe's URL conventions, its `operationId` scheme, its SDK naming — all of it belongs in
`sync.signals.<vendor>`. The moment `sync.core` knows a vendor's name, the plugin story is
dead. `tests/test_import_boundary.py` enforces the import direction; this rule is about the
knowledge, which no linter can catch.

## Validate at the boundary

Vendor responses and feed payloads are untrusted input. Parse strictly and fail loudly. For
the public feed specifically: verify the signature *first*, then parse — a signature proves
origin, and a well-signed malformed payload must still be rejected before any row is built
from it.

## `oasdiff` exit codes

Without `--fail-on`, a clean run exits 0 and reports "nothing found" as the JSON literal `[]`,
never as empty output. A non-zero exit is therefore a real failure and must raise — never be
read as a clean report.
