# B23 — the fifth conformance check, and the boundary it guards

Commit `5260021` on `coordinator/solo-a`, from `2b144c2`. Not pushed.

Files changed: `src/sync/core/conformance.py`, `tests/test_adapter_conformance.py`,
`tests/test_span_correlation.py`. Nothing under `src/sync/cli.py`,
`src/sync/signals/generated/`, `src/sync/graph/store.py`, or `generated-vendors.yaml`.

## Gates

Run from the worktree root against the committed tree, quoted verbatim:

```
uv run pytest -q
1799 passed in 77.54s (0:01:17)

uv run lint-imports
sync.core depends on nothing KEPT
Contracts: 1 kept, 0 broken.

uv run python scripts/lint_encoding.py src scripts tests
(no output, exit 0)

uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
(no output, exit 0)
```

One note on the dead-links gate, because a new public symbol in a scanned tree passing it
silently is exactly the shape that should be checked rather than assumed. I added a deliberately
unreachable `sync_b23_probe_symbol` to `conformance.py` and re-ran the lint: it still exited 0.
The reason is `_in_public_package` in `scripts/lint_dead_links.py:342` — `sync.core` is the
published SDK package and every definition in it is exempt by design, which is why the four
existing checks are not reported either. The gate is not blind; it is deliberately not looking
here. The probe was removed.

## What `runtime_checkable` actually verifies, measured

The brief states that an attribute is what `runtime_checkable` does not verify. That is half
right on Python 3.12.10, and the half that is wrong changes how the rule is worded. Measured
directly against `RequestCorrelator`:

| Object | `isinstance(x, RequestCorrelator)` |
|---|---|
| no `vendor_id` at all | **False** |
| `vendor_id = 42` | **True** |
| `vendor_id = ""` | **True** |

So presence *is* checked; type and emptiness are not. The rule is therefore narrower than the
equivalent one on `VendorAdapter` and is worth having for the half that remains, and
`_check_correlator_vendor_id`'s docstring says so rather than repeating the stronger claim.

## The rule set, and the argument for each

Seven rules and two preconditions. `check_request_correlator(correlator, *, known_request,
identifier)` — the author supplies an `(http_method, path)` pair the correlator resolves and the
substring of that path which is a live identifier. The identifier cannot be derived: which
segment is an id and which is a resource name is vendor knowledge.

**1. The identifier does not survive the call.** The reason the check exists. Every string field
on the returned `OperationRef` is examined, not `path` alone — a correlator that substitutes the
template correctly and appends the id to the operation id has moved the leak rather than closed
it, and a rule reading one field would certify that as conformant. Both halves are proved below.

**2. An unresolvable request is answered, not raised on.** One correlator is handed every client
span in a batch and most of them address other hosts, so declining is the ordinary case. Probed
with three inputs: an unrecognised path, `/`, and the empty string. The empty string is not
decoration — `sync/cli.py:931` passes `urlsplit(url).path`, which is `""` for a URL carrying no
path, so a correlator that raises there stops the ingest over a real span.

**3. An unresolvable request returns `None` rather than a guess.**
`sync/signals/stripe/adapter.py:189` states the contract and the check quotes its reasoning back.
The additional argument the docstring makes: an observed binding carries the `observed` rung,
which the graph surface reports as the most trustworthy of the three, so a guess here is
laundered into the rung an agent weighs a patch by.

**4. The operation returned is under the method that was asked about.** Stated as a property of
the answer rather than as a probe for a defect, because the property is the simpler statement: if
the correlator says a request addressed an operation declared under `post`, a `GET` did not
address it. Also probed across `GET`/`POST`/`PUT`/`PATCH`/`DELETE` on the author's own path,
because a correlator that ignores the method answers the known request correctly by luck whenever
the author's verb happens to be the one it always returns — and that is exactly how the violator
below survives rule 1.

**HEAD is deliberately not probed**, and this is the one place I chose a carve-out. Reading a
HEAD request as addressing the GET operation is a defensible reading of RFC 9110; probing it
would make the kit reject a correlator over a judgement the protocol never made. The rule still
applies if an author hands in HEAD as their own case, and the docstring names that as the single
place a conforming correlator could disagree, so it is argued rather than discovered as a
failure.

**5. The return is an `OperationRef` or `None`.** `sync/telemetry/ingest.py:97` reads
`.operation_id` and `.path` off whatever arrives, several stages away.

**6. `vendor_id` is a non-empty string.** See the measurement above.

**7. Two correlations of one request give the same answer.** OTLP delivery is at-least-once and a
collector re-sends whatever is still buffered, so the same span really does arrive twice;
`observed_call` is keyed partly on the operation, so a moving answer writes the second delivery to
a different row instead of folding into the first.

**Two preconditions, checked and named.** The kit's own docstring already says a precondition
failing is not the same as a rule passing. An identifier the path does not contain makes rule 1
vacuous — a correlator returning the raw path sails through it — and a known request that
resolves to nothing leaves no template for rules 1, 4 and 7 to read. Both fail naming the case
rather than the correlator.

### What I considered and did not add

**A fake verb such as `BREW`.** It catches a correlator that ignores the method, but rule 4
subsumes it with a better message, and probing a verb no specification declares tests parsing
rather than semantics.

**Requiring the author to supply an unresolvable path.** `_check_operation_for_symbol` already
sets the precedent of synthesising its own negative case (`"this.symbol.does.not.exist"`), and an
author who supplied the negative could supply one their correlator happens to resolve. The kit
states the negative.

**Asserting the returned path differs from the request path.** Wrong: for a collection path such
as `/v1/charges` the template *is* the request path, legitimately. Keying on the identifier is the
correct formulation.

## Every rule proved able to fail

Each is a deliberately non-conforming correlator in `tests/test_adapter_conformance.py`. Observed
output, run against the committed implementation:

**Rule 1 — returns the request path verbatim**

```
the operation returned carried the request's own identifier.
  `path` came back as '/v1/charges/ch_3PjkLm2eZvKYlo2C1cQrSt' for the request
  '/v1/charges/ch_3PjkLm2eZvKYlo2C1cQrSt'. What comes back must address the operation with the
  vendor's published template, which is public data; the request path is a customer's. This value
  is written to `observed_call`, joined into findings, and rendered into the body of a pull
  request on a repository we do not own, and nothing downstream removes it.
```

**Rule 1 — leaks the identifier into `operation_id` instead**

```
the operation returned carried the request's own identifier.
  `operation_id` came back as 'GetChargesCharge:ch_3PjkLm2eZvKYlo2C1cQrSt' for the request
  '/v1/charges/ch_3PjkLm2eZvKYlo2C1cQrSt'. ...
```

**Rule 2 — raises on a request it cannot resolve**

```
operation_for_request must answer for a request it cannot resolve, not raise.
  One correlator is asked about every client span in a batch, and most of them address something
  else. An exception abandons the batch over a request this correlator was never expected to
  recognise. Asked 'GET' '/sync-conformance/no-such-resource/2f8b1c' and it raised
  KeyError('/sync-conformance/no-such-resource/2f8b1c').
```

**Rule 2 — raises on the empty path `sync.cli` can hand it**

```
operation_for_request must answer for a request it cannot resolve, not raise.
  ... Asked 'GET' '' and it raised ValueError('empty path').
```

**Rule 3 — guesses**

```
operation_for_request must return None for an unrecognised request, not a guess.
  Asked 'GET' '/sync-conformance/no-such-resource/2f8b1c' and got
  OperationRef(operation_id='GetCharges', http_method='get', path='/v1/charges'). A missing
  binding is visibly unresolved and can be counted; a wrong one attributes real traffic to an
  operation nobody called, and it arrives carrying the `observed` rung, which is the one an agent
  trusts most.
```

**Rule 4 — ignores the http method**

```
the operation returned must be the method it was asked about.
  Asked 'POST' '/v1/charges/ch_3PjkLm2eZvKYlo2C1cQrSt' and got an operation declared under 'get'.
  The method is not being consulted, so every span for this path folds into one operation
  whichever verb produced it.
```

**Rule 5 — returns a dict**

```
operation_for_request must return an OperationRef or None.
  Got dict. `sync.telemetry.ingest` reads `.operation_id` and `.path` off what arrives, several
  stages away, so another shape fails there as an attribute error about a field rather than here
  as a statement about the correlator.
```

**Rule 6 — empty and non-string `vendor_id`**

```
vendor_id must be a non-empty string.
  Every observed call this correlator resolves is filed under it, and it is what joins a span to
  the call sites indexed for the same vendor. `isinstance` verifies that the attribute exists and
  nothing about its value. Got ''.
  ... Got 42.
```

**Rule 7 — answers differently the second time**

```
two correlations of one request must give the same answer.
  Got OperationRef(operation_id='GetChargesCharge4', ...) then
  OperationRef(operation_id='GetChargesCharge9', ...). OTLP delivery is at-least-once, so the same
  span arrives more than once by design; a correlator whose answer depends on how many times it
  has been asked makes `observed_call` a record of ingest ordering.
```

**Precondition — identifier absent from the path**

```
the identifier must appear in the request path the kit was handed.
  'ch_not_in_this_path' is not in '/v1/charges/ch_3PjkLm2eZvKYlo2C1cQrSt', so the rule that it
  does not survive the call is vacuous: every correlator passes it, including one that returns the
  path unchanged. Fix the case handed to the kit, not the correlator.
```

**Precondition — the supplied request resolves to nothing**

```
the request handed to the kit must resolve to an operation.
  'GET' '/v1/nothing_here/ch_3PjkLm2eZvKYlo2C1cQrSt' correlates to nothing, so there is no
  template to inspect and every rule below this one is vacuous. Either the case is wrong or the
  correlator resolves nothing at all -- the kit cannot tell which.
```

Every one of these failed first for the right reason: the tests were written before the check
existed and the first run was `ImportError: cannot import name 'check_request_correlator' from
'sync.core.conformance'`.

## The mutation pass, and the two things it found

The violator tests prove each rule fires on a real violation. The converse — that no violator test
is green for some other rule's reason, which is how a deleted rule stays passing — needs a
mutation. Each rule call in `check_request_correlator` was replaced with `pass` in turn and the
correlator tests re-run:

| Rule removed | Tests that went red |
|---|---|
| `_check_correlator_vendor_id` | `..._without_a_vendor_id_fails`, `..._whose_vendor_id_is_not_a_string_fails` |
| `_check_unrecognised_requests_answer_none` | `..._guesses_at_an_unrecognised_path_fails`, `..._raises_on_an_empty_path_fails` |
| `_check_the_identifier_does_not_survive` | `..._returns_the_request_path_fails`, `..._leaks_the_identifier_into_the_operation_id_fails` |
| `_check_the_method_is_the_one_asked_about` | `..._ignores_the_http_method_fails` |
| `_check_correlation_is_deterministic` | `..._answers_differently_the_second_time_fails` |

Every rule is load-bearing. Two honest observations from it:

- `test_a_correlator_that_raises_on_an_unrecognised_path_fails` stayed green when rule 2 was
  removed. It is caught instead by rule 4's probe, which also asks about a method the path does
  not serve and reaches the same `_correlate` guard. Same rule, second call site — not a test
  passing for a wrong reason, but worth recording so nobody reads the table as saying rule 2 is
  the only thing standing between that violator and a pass.
- `test_a_correlator_that_returns_the_wrong_type_fails` is caught by
  `_check_known_request_resolves`, which was not mutated because it is the precondition every
  later rule reads; removing it makes the rest raise `AttributeError` rather than pass.

## The real Stripe adapter passes unchanged

`StripeAdapter` was not modified. The assertion lives in `tests/test_span_correlation.py` —
the correlator's own test file — rather than in the kit's, matching the kit's stated position
that adapters ship their own tests.

That is a change in kind worth flagging: **before this, no real implementation was asserted
against the conformance kit anywhere in the suite.** `grep -rn "check_vendor_adapter\|
check_detector\|check_language_adapter\|check_remediator" tests/` outside
`test_adapter_conformance.py` returns nothing. The four existing checks have only ever been run
against the kit's own examples, and the module docstring's account of probing them against the
five detectors describes a manual session rather than anything CI repeats. Worth a follow-up task,
not mine to open.

## Recommendation on the two `sync.cli` guards — with a correction

The guards are at **`src/sync/cli.py:1032`** (`sync shapes`) and **`src/sync/cli.py:1102`**
(`sync ingest`), not 1023 and 1093 as the brief has them; the file has moved since.

**They should not call `check_request_correlator`, and I recommend against it.** Three reasons:

1. **The check needs a case the CLI does not have.** It requires a request the correlator resolves
   and the identifier inside it. Nothing at the `sync ingest` entry point knows a resolving path
   for an arbitrary vendor, and the kit cannot synthesise one — that is vendor knowledge, which is
   the whole reason `known_request` is an argument.
2. **It is a development-time kit, not a runtime gate.** Running seven rules including a
   determinism probe on every ingest invocation puts a conformance suite on an operational path,
   and the rules would be re-establishing per run what a test establishes once.
3. **What the guards do is dispatch, and `isinstance` is the right tool for it.** They answer
   "does this vendor correlate at all", which is exactly the presence question `runtime_checkable`
   answers correctly. The comment at `cli.py:1103` already says so.

The gap the brief is pointing at is real, and the repair is the one this commit makes in the other
direction: **every registered correlator asserts conformance in its own test file.** Stripe now
does. When a second correlator lands, its test file gains the same three lines, and CI holds the
boundary for every adapter rather than the CLI re-checking one at run time.

If you want a runtime guard anyway, the shape would be for `sync.signals.registry` to carry a
per-vendor conformance case alongside the builder, so the CLI has a `known_request` to hand the
kit. That is a registry change, it is a real design decision rather than a wiring one, and I would
argue against it for reason 2 above.

## One process note

Midway through, I ran `git checkout -- src/sync/core/conformance.py` to revert a one-line
sensitivity probe, on a file that also held the uncommitted implementation. It discarded both. The
work was recoverable because the implementation had been written to a scratchpad file first and
was re-applied verbatim, and the full suite and all four gates were re-run against the restored
tree — the numbers quoted above are from that run, not from before it. Recorded because the near
miss is instructive: `git checkout --` is not an undo for one edit, and a probe on a dirty file
wants a targeted reversal or no probe at all.
