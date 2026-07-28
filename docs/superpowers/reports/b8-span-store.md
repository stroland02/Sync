# B8 — the span store

The first half of M1: somewhere for client spans to land, and the correlation that makes them
mean something. No detector. `observed_call` has real rows in it, produced from a captured OTLP
payload by the same code path an endpoint would use.

## The grain, and the argument for it

```
Grain: one row per (repo_id, vendor_id, operation_id, server_address, http_method, trace_id)
       -- one unit of work's use of one operation against one host.
```

**A row is not a span and not a call.** Three calls to one operation inside one request are one
row whose `call_count` is three.

The decision that mattered was whether the trace belongs in the key. It does, and the reason is
that three of the four efficiency findings the design document names are the same question
wearing different clothes:

| Finding | The question it asks |
|---|---|
| Vendor call inside a loop | How many times did **one unit of work** call this? |
| Default page size against a large result set | How many times did **one unit of work** call this? |
| Repeated identical call with no caching | How many times did **one unit of work** call this, to the same place? |
| Retry storm | What was the worst `resend_count`? |

A time-bucketed rollup — one row per operation per hour — answers "how many calls this hour". It
cannot distinguish one request making two hundred calls from two hundred requests making one.
Those are the same call volume, and the difference between them *is* the finding. Bucketing
throws away the only signal three of the four detectors read.

The other half of the argument is directional. A windowed rollup is derivable from per-trace
rows by a `GROUP BY`. Per-trace facts are not recoverable from a rollup at any price. This table
cannot be backfilled — the same sentence appears twice already in `schema.sql`, about
`migration_outcome` and `observed_shape`, both times as a lesson — so the resolution is kept now
and aggregated later, never the reverse.

**The honest cost.** For traffic where most requests make one vendor call, this compresses
barely at all: 3M spans becomes ~2M rows rather than something dramatically smaller. Compression
happens exactly in the pathological case, which is the case worth compressing but not the common
one. A high-volume tenant will want a windowed rollup on top of this. That is a view to add, not
a grain to have chosen — and I would rather explain a large table than explain why the loop
detector cannot be written.

`server_address` is in the key because one operation reached through two hosts is two
integrations — a live key and a sandbox — and merging them averages a test workload into a
production bill. `http_method` is in it because `operation_id` is empty for uncorrelated calls,
and without the method every uncorrelated request to one host in one trace would collapse into a
single row.

## Idempotence: there is no counter, so no counter can drift

`spans` is a JSONB map keyed by span id. Every aggregate — `call_count`, `distinct_targets`,
`max_resend_count`, `error_count` — is a derived property over that map, not a stored column.

The conflict clause is `spans = observed_call.spans || EXCLUDED.spans`. JSONB concatenation is
last-write-wins per key, so folding a span already present is a no-op.

I went looking for a batch-level dedup first and it is wrong. OTLP redelivery is at-least-once,
and a collector that misses an acknowledgement re-sends **whatever is still in its buffer** —
an overlapping subset repacked with newer spans, not the batch it sent before. A content digest
of the batch would treat that as new and double-count the overlap. The span id is the only
handle at the granularity redelivery actually happens at. `test_a_partial_redelivery_of_
overlapping_spans_converges` is that case specifically.

This is where `observed_call` deliberately diverges from `observed_shape`, whose `sample_count`
is a `+=` counter and is *not* idempotent under redelivery. That is correct for a table whose
sources do not redeliver, and would be a silent inflation bug here.

## Attributes read, and what a missing one does

Stable HTTP client conventions, 1.23.0 or later.

| Attribute | Missing |
|---|---|
| `http.request.method` | **Span skipped.** No request to correlate. Not a partial row — not a row. |
| `url.full` | **Span skipped.** An empty URL correlates to whichever operation sits on the empty path, which is a fabricated binding. |
| `server.address` | Falls back to the URL's host. That recovers a real value rather than substituting a placeholder. |
| `http.response.status_code` | Stays `None`. A request that got no response is a real outcome and is neither a success nor a 4xx. |
| `http.request.resend_count` | Reads as `0`. The convention omits it on a first attempt rather than writing zero, so absence *states* a value here. This is the only default that is a reading rather than a guess. |

Pre-1.23 spellings (`http.method`, `http.url`, `net.peer.name`) are deliberately rejected. An
exporter old enough to emit them predates `http.request.resend_count` entirely, so a payload
written that way cannot answer the retry question — half-reading it would produce a baseline
that looks complete and is not.

Two encoding traps, both covered: OTLP/JSON writes 64-bit fields as **strings** (`"intValue":
"200"`), and enums as **either** their number or their name, differing by exporter. A reader
that handles one `kind` spelling silently discards most of a real batch, and the discard looks
like low traffic rather than like a bug.

**Client spans only.** A server span carries identical HTTP attributes and is separated from a
client span by `kind` and nothing else. That direction is the product thesis, so it is filtered
where spans are read and never re-litigated downstream.

## Ingest shape: a library function

`ingest_payload(payload, store, repo_id, correlator, salt)`. Not a server, and **not a CLI
subcommand either**.

The design document says "endpoint". An endpoint needs a port, a supervisor, an authentication
story telling one collector from another, and a deployment this project does not have — none of
which makes a span mean more once it lands. Becoming the endpoint is a wrapper, not a rewrite:
`POST /v1/traces` with an OTLP/JSON body *is* `ingest_payload(json.loads(body), ...)`, with the
handler taking `repo_id` from the authenticated tenant and supplying the salt.

I did not add a CLI subcommand, for two reasons. `src/sync/cli.py` is being edited by another
worker right now — a webhook module appeared in this worktree mid-run — and more importantly a
runnable command has to decide where the salt comes from, which is a real open question (below).
A command that got that wrong would be worse than no command.

## No OTLP dependency was added

Nothing matching `opentelemetry`, `otlp` or `protobuf` is in `uv.lock` or `pyproject.toml`. I
hand-rolled the parser.

`opentelemetry-proto` exists to give you generated protobuf message classes, which costs a
`protobuf` runtime — a pinned C extension and the most common source of unresolvable version
conflicts in a Python dependency tree — to decode a wire format we are not reading. What arrives
here is OTLP/**JSON**, whose encoding is fixed by protobuf's canonical JSON mapping, and Sync
reads five attributes on one message type. A generated decoder would not make that traversal
more correct. `sync.core` is the plugin SDK: a dependency added to save forty lines is one every
third-party adapter author inherits.

The deferred half is real and stated in the module: **protobuf-encoded OTLP is not read**, and
most collectors default to it. An endpoint accepting only JSON would reject the common
configuration.

## Correlation stayed in the adapter

`sync.telemetry` never names a vendor — asserted against the modules' own source, since the
import-boundary contract covers `sync.core` and would not catch it.

The inverse of `operation_for_symbol` is `StripeAdapter.operation_for_request(method, path)`,
reached through a new `sync.core.protocols.RequestCorrelator`. That is a **separate** protocol
rather than a method on `VendorAdapter`: folding it in would make three existing adapters fail a
`runtime_checkable` test to gain a capability none of them was asked for.

The inverse index is built from the **symbol map**, not from the specification. That sounds like
a limitation and is the opposite. An operation absent from the symbol map has no SDK method, so
no call site is ever bound to it, so a span correlated to it would describe traffic no indexed
code produced — a finding with nothing to remediate and nothing to attribute it to. The inverse
map covers exactly what the forward map covers, by construction.

**The ceiling this creates, which the brief asked about.** `build_symbol_map`'s pattern is
`^/v1/([a-z_]+)(/\{[^}]+\})?/?$` — at most one placeholder segment. So nested paths like
`/v1/accounts/{account}/bank_accounts/{id}` correlate to nothing, today, permanently, for as
long as the forward map has that shape. The fixture contains one such span and
`test_a_path_the_symbol_map_never_covered_correlates_to_nothing` pins it. This is not a blocker
for the detector, but whoever writes it should know the unresolved fraction is structural rather
than a bug, and that widening it means widening `build_symbol_map` first.

## Lineage and the privacy line

`binding_rung` is a column: `observed` for a span-derived binding, `unresolved` where nothing
matched. An uncorrelated span is **kept**, not dropped — dropping it makes the unresolved
fraction invisible, and the unresolved fraction is the only measure of how good the correlation
is.

The request URL never reaches a column. A correlated row keeps the **vendor's published
template** (`/v1/charges/{charge}`), which is public data. Every row keeps a **salted digest** of
the full URL, whose only job is to say whether two calls went to the same place — that is what
makes `distinct_targets` able to tell "fetched three charges" from "fetched one charge three
times" while holding nothing that says which charge.

This is where I traded one rule against another and should say so. "Keep the raw record"
(`VendorChange.raw`) and "free-form values are discarded at the observation boundary" point in
opposite directions here. I let the threat model win, because `VendorChange.raw` is *public
vendor data* while a request path with `ch_3MtwBw…` in it is a customer's. **The cost is
concrete: an uncorrelated row keeps no path at all, so improving the adapter cannot reinterpret
history — it requires re-ingesting.** That is the exact re-derivation `b29795a` was able to do
and this table will not be able to do.

The query string *is* in the digest (parameters sorted first, so two spellings of one request do
not look like two calls). `?limit=10` versus `?limit=100` is the entire page-size finding.

## The open question the detector should not be written on top of

**`salt` has no provenance.** It is a plain argument, which is right for a library function and a
trap for anything runnable. The same URL under two salts digests to two values, so a rotated or
per-run salt makes repeat calls look distinct and **silently deletes the cache finding**. Nothing
in the schema can detect that having happened.

I asserted the hazard rather than a guarantee —
`test_a_rotated_salt_silently_breaks_the_repeat_signal` — so whoever writes the CLI or the
endpoint finds out before shipping. One stable salt per deployment, stored, is a decision that
has to be made before this table is trusted across batches.

## Verification

Every mutation below was applied, the suite run, and the mutation reverted.

| Mutation | Result |
|---|---|
| Accept `kind: 2` (server spans) | 3 failed |
| Drop `"SPAN_KIND_CLIENT"`, keep numeric only | 3 failed |
| `int(value)` → `None` for string ints | 8 failed |
| Absent status defaults to 200 | 1 failed |
| Drop `trace_id` from the natural key | **passed — hollow test, see below** |
| Key the span map by object identity, not span id | 2 failed |
| Store the request URL as `url_template` | 2 failed |
| `first_seen = EXCLUDED.first_seen` (last-write-wins) | **passed first time — see below** |
| `last_seen = EXCLUDED.last_seen` | 1 failed |
| Drop uncorrelated spans | 3 failed |
| Unsalted target digest | 1 failed |
| `sync.core` imports `sync.telemetry` | contract **BROKEN**, correctly |

**Two tests could not fail and were fixed.**

Dropping `trace_id` from the key passed, because the fixture had no operation appearing in two
traces — so collapsing the grain merged nothing. I added a second `GET /v1/charges` in the second
trace and rewrote the assertion to require two rows of one call rather than `len(rows) == 1`.
The mutation now fails it. This was the single most important test in the task and it was
worthless as first written.

Last-write-wins on `first_seen` passed, because the window test only ingested newest-then-oldest.
Added the mirror test in the other arrival order, matching the pair `observed_shape` already has.
Both orders now fail their respective mutation.

**Gates, all run unredirected, after the final edit:**

```
uv run pytest                                          1001 passed
uv run lint-imports                                    Contracts: 1 kept, 0 broken
uv run python scripts/lint_encoding.py src scripts tests   exit 0
```

`tests/test_merge_webhook.py` errors on collection — it imports `sync.forge.webhook`, is another
worker's in-flight file that appeared in this worktree mid-run, and is not mine, not staged, and
not touched.
