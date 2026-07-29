# M3 task archive

Every task this coordinator dispatched during the multi-agent build, with the brief it was given
and the status it reached. The companion `2026-07-29-orchestration-archive.md` holds the message
stream; this holds the task definitions, which the message stream does not carry.

A brief is worth keeping for the same reason a worker report is: it records the constraint a task
was held to, so a later reader can tell a deliberate refusal from an oversight. Several tasks came
back having refused something the brief demanded, and those refusals were right — the brief is
half of that record.

Exported 2026-07-29. 48 tasks.

---

## M3-W15: build observed_shape, the second dataset that cannot be backfilled.

`task_d7df9f81a65a` · created `2026-07-28 16:54:40` · status **failed**

### Result

{"reason":"duplicate: an earlier task-create call succeeded silently, so this row is a second copy of the same spec. The live copies are task_e173f21b0051 (W15) and task_edca24e45f09 (W16). Not dispatched."}

<details><summary>Brief</summary>

M3-W15: build observed_shape, the second dataset that cannot be backfilled.

Own ONLY src/sync/core/models.py (one new model), src/sync/graph/schema.sql, src/sync/graph/store.py, and tests/test_observed_shape.py. Do not edit src/sync/remediate/, src/sync/mcp/, src/sync/route/ or docs/ -- other workers own those right now.

Read CLAUDE.md first; it is binding. Read .claude/rules/graph-grain.md, which applies to every file you touch here. Test-first: prove each test RED before implementing, and actually run every command you claim to have run.

Set up: export SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_w15 and create that database. Rebase onto origin/main before starting. Three gates before committing: uv run pytest, uv run lint-imports (run it unredirected -- redirecting it crashes rich's Windows console renderer and looks exactly like a contract failure), and uv run python scripts/lint_encoding.py src tests.

The specification is docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md, which declares the table and calls the schema binding. It does not exist in code. Read that spec before writing anything.

Your precedent is the migration_outcome table, added in commit bf675b6: src/sync/core/models.py (MigrationOutcome), src/sync/core/corpus.py, the tail of src/sync/graph/schema.sql, and tests/test_migration_corpus.py. Match its shape, its testing style, and its docstring style. In particular it declares the table's grain as a SQL comment above the table before any column, and its natural key carries ON CONFLICT DO NOTHING so a re-run converges rather than inflating the table.

What to build. The observed_shape table per the spec's DDL, an ObservedShape model beside MigrationOutcome, a store method to record a shape, and a store method to read shapes back for a vendor and operation. The grain is one row per (vendor_id, operation_id, field_path, json_type, source) tuple, which is why sample_count is a counter column rather than a row multiplier -- recording the same shape twice must increment the count and the last_seen timestamp, not append a row. That behaviour is the most important test in this task.

The privacy rule is the point of the table and must be tested, not commented. Record field paths, JSON types, nullability and presence counts. Record an enum value ONLY when that value appears in the vendor's published specification. Free-form values -- amounts, names, tokens, identifiers -- must never reach a column. Write a test that feeds a payload containing obviously sensitive values and asserts against the serialised row that none of them survive, the way tests/test_migration_corpus.py::test_no_source_text_reaches_the_row does.

Do NOT build the detector, the replay tier, or any shape extraction from live traffic. This task is the table, the model, and the store methods only. The spec sequences the detector at M2 and it is not yours.

Report what you built, the grain you declared and why, the exact mutation you ran to prove each test could fail, and anything the spec does not mention that you had to decide.

</details>

---

## M3-W16: record migration outcomes from the remediation graph, so the corpus a...

`task_98a7cbb0b3e7` · created `2026-07-28 16:54:41` · status **failed**

### Result

{"reason":"duplicate: an earlier task-create call succeeded silently, so this row is a second copy of the same spec. The live copies are task_e173f21b0051 (W15) and task_edca24e45f09 (W16). Not dispatched."}

<details><summary>Brief</summary>

M3-W16: record migration outcomes from the remediation graph, so the corpus actually fills.

Own ONLY src/sync/remediate/ and tests for it. Do not edit src/sync/graph/, src/sync/core/, src/sync/mcp/, src/sync/route/ or docs/ -- other workers own those right now.

Read CLAUDE.md first; it is binding. Read .claude/rules/remediate-stage.md, which applies to every file you touch. Test-first: prove each test RED before implementing, and actually run every command you claim to have run.

Set up: export SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_w16 and create that database. Rebase onto origin/main before starting. Three gates before committing: uv run pytest, uv run lint-imports (unredirected -- redirecting it crashes rich's Windows renderer and looks like a contract failure), and uv run python scripts/lint_encoding.py src tests.

The state you are walking into. Commit bf675b6 added the migration_outcome table, the MigrationOutcome model with a from_attempt constructor that performs the whole privacy reduction, and three store methods: record_migration_outcome, migration_outcomes, and set_merge_outcome. Read src/sync/core/models.py and tests/test_migration_corpus.py before writing anything. Nothing anywhere in src/ calls record_migration_outcome. The table exists and stays empty, which is the same failure as not having built it.

What to build. Wire the recording into the remediation graph so every attempt writes exactly one row. The grain is one row per attempt, not per finding: a finding that takes three tries writes three rows, and attempt_index distinguishes them. src/sync/remediate/state.py already carries static_attempts and ci_attempts; use whichever genuinely counts attempts rather than adding a new counter, and say in your report which you chose and why.

Abandoned attempts must be recorded, not only successful ones. They are the negative class -- a corpus of successes alone can compute no precision and evaluate no future router -- so the abandon path writes a row carrying its abandon_reason. Read the docstring on src/sync/remediate/tiered.py, which explains why an empty diff means ownership rather than failure; a run that abandons still happened and still counts.

Record wall_ms honestly by measuring it, and record the tier and strategy actually used rather than a default. The whole point of splitting merge rate by strategy and tier is to check the claim that mechanical changes land more often than agent-written ones, and a defaulted column makes that unanswerable.

A recording failure must never fail a run. If the corpus write raises, the pipeline continues and the failure is visible in logs -- losing one row is bad, losing the pull request because bookkeeping failed is worse. Test that explicitly.

Report what you built, which attempt counter you chose and why, how you proved an abandoned run writes a row, and for each test the exact mutation you ran.

</details>

---

## M3-W15: build observed_shape, the second dataset that cannot be backfilled.

`task_e173f21b0051` · created `2026-07-28 16:54:50` · status **completed**

### Result

{"completedBy":"term_e3aac1ed-88ac-4795-9d19-10a20c4ee7f3","filesModified":["src/sync/core/models.py","src/sync/graph/schema.sql","src/sync/graph/store.py","tests/test_observed_shape.py"],"completedAt":"2026-07-28T17:21:34.548Z"}

<details><summary>Brief</summary>

M3-W15: build observed_shape, the second dataset that cannot be backfilled.

Own ONLY src/sync/core/models.py (one new model), src/sync/graph/schema.sql, src/sync/graph/store.py, and tests/test_observed_shape.py. Do not edit src/sync/remediate/, src/sync/mcp/, src/sync/route/ or docs/ -- other workers own those right now.

Read CLAUDE.md first; it is binding. Read .claude/rules/graph-grain.md, which applies to every file you touch here. Test-first: prove each test RED before implementing, and actually run every command you claim to have run.

Set up: export SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_w15 and create that database. Rebase onto origin/main before starting. Three gates before committing: uv run pytest, uv run lint-imports (run it unredirected -- redirecting it crashes rich's Windows console renderer and looks exactly like a contract failure), and uv run python scripts/lint_encoding.py src tests.

The specification is docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md, which declares the table and calls the schema binding. It does not exist in code. Read that spec before writing anything.

Your precedent is the migration_outcome table, added in commit bf675b6: src/sync/core/models.py (MigrationOutcome), src/sync/core/corpus.py, the tail of src/sync/graph/schema.sql, and tests/test_migration_corpus.py. Match its shape, its testing style, and its docstring style. In particular it declares the table's grain as a SQL comment above the table before any column, and its natural key carries ON CONFLICT DO NOTHING so a re-run converges rather than inflating the table.

What to build. The observed_shape table per the spec's DDL, an ObservedShape model beside MigrationOutcome, a store method to record a shape, and a store method to read shapes back for a vendor and operation. The grain is one row per (vendor_id, operation_id, field_path, json_type, source) tuple, which is why sample_count is a counter column rather than a row multiplier -- recording the same shape twice must increment the count and the last_seen timestamp, not append a row. That behaviour is the most important test in this task.

The privacy rule is the point of the table and must be tested, not commented. Record field paths, JSON types, nullability and presence counts. Record an enum value ONLY when that value appears in the vendor's published specification. Free-form values -- amounts, names, tokens, identifiers -- must never reach a column. Write a test that feeds a payload containing obviously sensitive values and asserts against the serialised row that none of them survive, the way tests/test_migration_corpus.py::test_no_source_text_reaches_the_row does.

Do NOT build the detector, the replay tier, or any shape extraction from live traffic. This task is the table, the model, and the store methods only. The spec sequences the detector at M2 and it is not yours.

Report what you built, the grain you declared and why, the exact mutation you ran to prove each test could fail, and anything the spec does not mention that you had to decide.

</details>

---

## M3-W16: record migration outcomes from the remediation graph, so the corpus a...

`task_edca24e45f09` · created `2026-07-28 16:55:31` · status **completed**

### Result

{"completedBy":"term_ed3a02b9-4556-4dbe-a1ae-9e96d3e4e372","filesModified":["src/sync/remediate/corpus.py","src/sync/remediate/nodes.py","src/sync/remediate/state.py","src/sync/remediate/tiered.py","src/sync/remediate/graph.py","tests/test_migration_recording.py"],"completedAt":"2026-07-28T17:26:14.969Z"}

<details><summary>Brief</summary>

M3-W16: record migration outcomes from the remediation graph, so the corpus actually fills.

Own ONLY src/sync/remediate/ and tests for it. Do not edit src/sync/graph/, src/sync/core/, src/sync/mcp/, src/sync/route/ or docs/ -- other workers own those right now.

Read CLAUDE.md first; it is binding. Read .claude/rules/remediate-stage.md, which applies to every file you touch. Test-first: prove each test RED before implementing, and actually run every command you claim to have run.

Set up: export SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_w16 and create that database. Rebase onto origin/main before starting. Three gates before committing: uv run pytest, uv run lint-imports (unredirected -- redirecting it crashes rich's Windows renderer and looks like a contract failure), and uv run python scripts/lint_encoding.py src tests.

The state you are walking into. Commit bf675b6 added the migration_outcome table, the MigrationOutcome model with a from_attempt constructor that performs the whole privacy reduction, and three store methods: record_migration_outcome, migration_outcomes, and set_merge_outcome. Read src/sync/core/models.py and tests/test_migration_corpus.py before writing anything. Nothing anywhere in src/ calls record_migration_outcome. The table exists and stays empty, which is the same failure as not having built it.

What to build. Wire the recording into the remediation graph so every attempt writes exactly one row. The grain is one row per attempt, not per finding: a finding that takes three tries writes three rows, and attempt_index distinguishes them. src/sync/remediate/state.py already carries static_attempts and ci_attempts; use whichever genuinely counts attempts rather than adding a new counter, and say in your report which you chose and why.

Abandoned attempts must be recorded, not only successful ones. They are the negative class -- a corpus of successes alone can compute no precision and evaluate no future router -- so the abandon path writes a row carrying its abandon_reason. Read the docstring on src/sync/remediate/tiered.py, which explains why an empty diff means ownership rather than failure; a run that abandons still happened and still counts.

Record wall_ms honestly by measuring it, and record the tier and strategy actually used rather than a default. The whole point of splitting merge rate by strategy and tier is to check the claim that mechanical changes land more often than agent-written ones, and a defaulted column makes that unanswerable.

A recording failure must never fail a run. If the corpus write raises, the pipeline continues and the failure is visible in logs -- losing one row is bad, losing the pull request because bookkeeping failed is worse. Test that explicitly.

Report what you built, which attempt counter you chose and why, how you proved an abandoned run writes a row, and for each test the exact mutation you ran.

</details>

---

## M3-W17: give the graph surface a stdio transport and its fourth tool, so an a...

`task_ca69e744d090` · created `2026-07-28 16:55:32` · status **failed**

<details><summary>Brief</summary>

M3-W17: give the graph surface a stdio transport and its fourth tool, so an agent can actually reach it.

Own ONLY src/sync/mcp/ and tests for it. Do not edit src/sync/graph/, src/sync/core/, src/sync/remediate/, src/sync/route/ or docs/ -- other workers own those right now. You may IMPORT from any of them; you may not change them.

Read CLAUDE.md first; it is binding. Test-first: prove each test RED before implementing, and actually run every command you claim to have run.

Set up: export SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_w17 and create that database. Rebase onto origin/main before starting. Three gates before committing: uv run pytest, uv run lint-imports (unredirected -- redirecting it crashes rich's Windows renderer and looks like a contract failure), and uv run python scripts/lint_encoding.py src tests.

The specification is docs/superpowers/specs/2026-07-25-sync-graph-surface-design.md and the plan is docs/superpowers/plans/2026-07-25-sync-mcp-graph-surface.md. Read both. The tool set is frozen on first publish and may only grow, so do not add a fifth tool or rename an existing one.

The state you are walking into. src/sync/mcp/tools.py implements three of the four tools as a GraphSurface class over a narrow GraphReader protocol that GraphStore already satisfies structurally. tests/test_mcp_tools.py covers them, including the four response rules. Read both before writing anything; tools.py is your precedent for shape and docstring style.

Two things are missing.

First, there is no transport. Nothing exposes GraphSurface over stdio, so no agent can call it. Build the stdio MCP server. Keep the transport thin: it translates a tool call into a GraphSurface method and its return value into a response, and holds no logic of its own. Every tool schema must be declared with its arguments, since an agent composes against the schema rather than against your docstrings.

Second, sync_propose_patch is unimplemented. Per the spec it runs the existing remediation pipeline as far as static verification and stops -- no branch, no push, no pull request -- and returns the diff, the static_verify result, and the evidence. Import from src/sync/remediate/ rather than reimplementing anything; another worker owns that directory and is editing it, so treat its public surface as fixed and do not change it. If you find you cannot do this without editing remediate/, stop and report that rather than editing it.

The four response rules in the spec are binding and already tested for the other three tools: never return file contents, stay shallow with drill-down by identifier, paginate every list, and carry provenance plus context_savings on every response. sync_propose_patch returns a diff, which is the one deliberate exception to "never return file contents" -- the diff IS the answer there. Say so in a comment so nobody later reads it as a violation.

The server must never write to the customer's repository. It is a read surface plus a patch proposal; the spec is explicit that Sync returns patches as data and never writes.

Report what you built, the tool schemas you declared, how you proved the transport works without a live agent, whether sync_propose_patch was reachable without editing remediate/, and for each test the exact mutation you ran.

</details>

---

## M3-W18: close the residual defects an audit reproduced in the edit primitives.

`task_4b581fbb949e` · created `2026-07-28 16:55:32` · status **completed**

### Result

{"completedBy":"term_a6120af8-0e4e-41be-9377-d9bd0b9be45b","filesModified":["src/sync/route/templates.py","tests/test_route_defects.py"],"completedAt":"2026-07-28T17:21:33.406Z"}

<details><summary>Brief</summary>

M3-W18: close the residual defects an audit reproduced in the edit primitives.

Own ONLY src/sync/route/ and tests for it. Do not edit src/sync/graph/, src/sync/core/, src/sync/remediate/, src/sync/mcp/ or docs/ -- other workers own those right now.

Read CLAUDE.md first; it is binding. Test-first: prove each test RED before implementing, and actually run every command you claim to have run.

Set up: rebase onto origin/main before starting. No database is needed for this task. Three gates before committing: uv run pytest, uv run lint-imports (unredirected -- redirecting it crashes rich's Windows renderer and looks like a contract failure), and uv run python scripts/lint_encoding.py src tests.

Context. An audit reproduced several defects in src/sync/route/templates.py. Three were fixed in commit 138ec4b -- byte versus character columns, overlapping deletion spans, and a duplicate-key guard blind to shorthand and computed keys. Read that commit and tests/test_route_defects.py first; they are your precedent, and the pattern is that each fix is pinned by a test using the exact input that reproduced it.

Two confirmed defects remain, both reproduced by the audit against real input.

First: removing the sole entry of an inline object leaves a double space. create({ model: "claude-opus-5" }) becomes create({  }) after the only remaining property is removed. It parses, so nothing fails, but it puts a whitespace change into a diff whose only claimed purpose was removing an argument -- and the same discipline already applied elsewhere in this file says that is worth avoiding.

Second: _call_at resolves calls that share a start position by traversal order rather than deliberately. Given wrap(cfg)({ receipt_email: 'x' }), both wrap(cfg) and the outer call start at the same position, and the wrong one is chosen, which returns the source unchanged -- a silent no-op that reads as "nothing to fix" rather than as a miss. Given stripe.p.create({}).then(h) the current behaviour happens to be right, but by traversal luck rather than by rule. Decide the rule deliberately, implement it, and record what you chose. A call whose argument list actually contains an object literal is a better candidate than one that does not, and that is a hint rather than an instruction -- justify whatever you pick.

While you are in this file, check one thing the audit did not: omit_parameter now re-parses between removals in a bounded loop. Satisfy yourself that the bound cannot be hit by any realistic object, and if it can, say so rather than raising it.

Do not restructure the module. These are targeted fixes with pinned tests, not a refactor, and another worker is importing from this file right now.

Report each defect, the input that reproduced it, the rule you chose for the ambiguous-call case and why, and for each test the exact mutation you ran.

</details>

---

## M3-W19: build the observed-drift detector, the one no shipped competitor has.

`task_5f72d83fe2d8` · created `2026-07-28 17:33:41` · status **completed**

### Result

{"completedBy":"term_e3aac1ed-88ac-4795-9d19-10a20c4ee7f3","filesModified":["src/sync/detect/observed_drift.py","tests/test_observed_drift.py"],"completedAt":"2026-07-28T17:43:50.163Z"}

<details><summary>Brief</summary>

M3-W19: build the observed-drift detector, the one no shipped competitor has.

Own ONLY src/sync/detect/observed_drift.py and tests/test_observed_drift.py. Do not edit src/sync/core/, src/sync/graph/, src/sync/remediate/, src/sync/mcp/, src/sync/route/, src/sync/signals/ or docs/ -- other workers own those. You may IMPORT from any of them; you may not change them. If you find you cannot finish without editing one, stop and report that rather than editing it.

Read CLAUDE.md first; it is binding. Test-first: prove each test RED before implementing, and actually run every command you claim to have run. Report the exact mutation you ran for each test.

Set up: export SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_w19 and create that database. Rebase onto origin/main before starting. Three gates before committing: uv run pytest, uv run lint-imports (run it UNREDIRECTED and with PYTHONIOENCODING=utf-8 -- it renders through rich, whose Windows path encodes with cp1252 and dies on its own spinner emoji, and a dead linter looks exactly like a broken contract), and uv run python scripts/lint_encoding.py src tests.

The specification is docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md. Read it before writing anything. It sequences the detector after the shape store, and the shape store now exists: src/sync/core/models.py holds ObservedShape with a from_observation reduction, and src/sync/graph/store.py holds record_observed_shape and observed_shapes. Read those and tests/test_observed_shape.py first.

Your precedent for detector shape is src/sync/detect/parameter_deprecation.py, which is the closest analogue -- it takes its inputs in the constructor, emits Findings, and satisfies the Detector protocol in src/sync/core/protocols.py. Match its structure and its docstring style.

What to build. ObservedDriftDetector, comparing the shape baseline against two references and emitting the same Finding type as every other detector.

The first comparison is observed versus specification: a field arriving null that the spec marks required, a type that changed, a field present in traffic that the spec does not describe. This is the unpublished-change case and it is the reason the detector exists -- no shipped competitor sees it, because specification diffing sees only what vendors publish and error-triggered tools see only what has already broken.

The second is observed now versus observed before: the baseline shifted between windows even where the spec is silent. The spec calls this a weaker signal, useful as severity enrichment rather than as a lone trigger. Implement it that way -- it must not raise a finding by itself.

Three constraints that are not negotiable.

The sample floor. A shape seen too few times is not a baseline. Below the floor the detector stays silent regardless of how large the divergence looks, because a false drift finding spends reviewer trust exactly the way a false review comment does. Choose the floor, state your reasoning, and make it a named constant rather than a literal.

Safe-miss over false-positive. Where you cannot tell whether a divergence is real, emit nothing. Precision over recall is the committed position and this detector is the one most able to violate it, because traffic is noisy in ways a specification is not.

The severity must not overstate. Observed-versus-spec is evidence about the vendor, not proof: a field can be absent from a sample for reasons that have nothing to do with a contract change. Say what the finding rests on in the rationale, the way parameter_deprecation.py says that it did not resolve the model scope.

There is one thing in the spec you should treat as a live problem rather than a settled design. The privacy rule discards any observed enum value the published specification does not name, which is what keeps free-form values out of the store -- but the spec ALSO lists "an enum value the spec does not name" as a case this detector should catch. Those cannot both hold from that column alone. Do not change the privacy rule. Report the conflict, say what the detector can and cannot detect as a result, and if there is a sound way to detect it without retaining an unpublished value, propose it rather than implementing it unasked.

Do NOT build the replay tier, the interceptor SDK, or any shape extraction from live traffic. This task is the detector over shapes that already exist.

Report what you built, the sample floor and why, what the enum conflict costs, and for each test the exact mutation you ran.

</details>

---

## M3-W20: read Sentry error payloads into the shape store, closing the chain th...

`task_ece09a13d57c` · created `2026-07-28 17:54:15` · status **completed**

### Result

{"completedBy":"term_e3aac1ed-88ac-4795-9d19-10a20c4ee7f3","filesModified":["src/sync/signals/sentry/__init__.py","src/sync/signals/sentry/shapes.py","tests/test_sentry_signal.py","tests/fixtures/sentry/stripe_charge_error.json"],"completedAt":"2026-07-28T18:03:36.326Z"}

<details><summary>Brief</summary>

M3-W20: read Sentry error payloads into the shape store, closing the chain the drift detector needs.

Own ONLY src/sync/signals/sentry/ (a new package) and tests/test_sentry_signal.py. Do not edit src/sync/core/, src/sync/graph/, src/sync/detect/, src/sync/remediate/, src/sync/mcp/, src/sync/route/ or docs/ -- other workers own those. You may IMPORT from any of them; you may not change them. If you cannot finish without editing one, stop and report that rather than editing it.

Read CLAUDE.md first; it is binding. Test-first: prove each test RED before implementing, and report the exact mutation you ran for each test.

Set up: export SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_w20 and create that database. Rebase onto origin/main before starting. Three gates before committing: uv run pytest, uv run lint-imports (run it UNREDIRECTED and with PYTHONIOENCODING=utf-8 -- it renders through rich, whose Windows path encodes with cp1252 and dies on its own spinner emoji, and a dead linter looks exactly like a broken contract), and uv run python scripts/lint_encoding.py src tests.

Why this task exists. Three pieces of a chain already exist and the first link does not. src/sync/core/models.py holds ObservedShape with a from_observation reduction; src/sync/graph/store.py holds record_observed_shape; src/sync/detect/observed_drift.py compares that baseline against the published specification and emits findings. Nothing populates the store. Read all three, plus tests/test_observed_shape.py, before writing anything.

docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md names three sources of ascending cost, and Sentry is the cheapest: error payloads are already captured, cost the customer nothing, and are biased toward failures -- which is a real limitation to state rather than hide, because a baseline built only from errors is not a baseline of normal traffic.

What to build. A module that turns a Sentry error payload into ObservedShape rows and records them with source='error-payload'. Shape extraction is the substance: walk a decoded JSON response body and yield one observation per field path, carrying the JSON-pointer path, the JSON type, and whether it was null.

The privacy rule is the whole point and must be tested, not commented. Values never leave the extraction boundary. Record field paths, JSON types and nullability. Record an enum value ONLY where that value appears in the vendor's published specification -- and note that ObservedShape.from_observation already implements that rule, so use it rather than reimplementing the decision. Free-form values -- amounts, names, tokens, email addresses, identifiers -- must never reach a column. Write a test that feeds a payload stuffed with obviously sensitive values and asserts against the serialised rows that none survive, the way tests/test_migration_corpus.py::test_no_source_text_reaches_the_row does.

Constraints that are not negotiable.

No network and no Sentry API call in any test. Fixtures are committed. Take a real Sentry event payload shape from their public documentation, commit a trimmed copy, and parse that. If you need credentials to make the code work, you have built the wrong thing -- this reads a payload someone hands it.

Nested structure must be handled and arrays are the hard part. An array of ten objects is not ten different shapes; decide how you address elements in a JSON pointer, state the rule, and pin it with a test. Getting this wrong makes every array field look like drift on every observation.

An unparseable or unexpected payload yields no rows rather than raising. This runs over data a third party produced and a malformed event must not stop the others being read. Silence on a single bad payload is correct; silence on all of them is not, so log rather than swallow.

Do NOT build the replay tier, the interceptor SDK, a Sentry API client, or any scheduled polling. This task is payload to rows.

Report what you built, how you address array elements and why, what the error-payload bias means for the baseline, and for each test the exact mutation you ran.

</details>

---

## M3-W21: publish and verify the public change feed, the artifact that commodit...

`task_691068f93cd4` · created `2026-07-28 18:12:06` · status **completed**

### Result

{"completedBy":"term_e3aac1ed-88ac-4795-9d19-10a20c4ee7f3","filesModified":["src/sync/signals/feed/__init__.py","src/sync/signals/feed/publisher.py","src/sync/signals/feed/consumer.py","tests/test_change_feed.py","pyproject.toml","uv.lock"],"completedAt":"2026-07-28T18:21:08.815Z"}

<details><summary>Brief</summary>

M3-W21: publish and verify the public change feed, the artifact that commoditises what Sync does not own.

Own ONLY src/sync/signals/feed/ (a new package) and tests/test_change_feed.py. You may also add ONE dependency line to pyproject.toml and nothing else in that file. Do not edit src/sync/core/, src/sync/graph/, src/sync/detect/, src/sync/remediate/, src/sync/mcp/, src/sync/route/, other packages under src/sync/signals/, or docs/ -- other workers own those. You may IMPORT from any of them; you may not change them. If you cannot finish without editing one, stop and report rather than editing it.

Read CLAUDE.md first; it is binding. Test-first: prove each test RED before implementing, and report the exact mutation you ran for each test.

Set up: no database is needed. Rebase onto origin/main before starting. Three gates before committing: uv run pytest, uv run lint-imports (run it UNREDIRECTED and with PYTHONIOENCODING=utf-8 -- it renders through rich, whose Windows path encodes with cp1252 and dies on its own spinner emoji, and a dead linter looks exactly like a broken contract), and uv run python scripts/lint_encoding.py src tests.

The specification is docs/superpowers/specs/2026-07-26-sync-public-change-feed.md and it is binding. Read it, and read docs/superpowers/specs/2026-07-25-sync-positioning-and-open-core.md for why the feed exists at all: several companies now alert on consumed-API change, none binds it to a call site, and publishing the normalised feed for free is the move that makes Sync's schema the default one a competitor's tooling speaks. The feed is the giveaway; the binding engine is not.

What to build. Two halves, both in your package.

The publisher: take VendorChange rows and render one JSON array per vendor, plus a detached Ed25519 signature. No wrapper object, no pagination envelope, no version field -- the format is versioned by never breaking it. New fields may be added as optional; nothing is renamed or removed.

The consumer: verify a signature against a public key and parse the array into VendorChange rows. Verification runs BEFORE parsing. A signature proves origin, not correctness, so a validly signed payload carrying a malformed change must still fail at parse -- two different failure modes, two gates, and neither substitutes for the other. Test both orders explicitly: a tampered payload rejected before any row is constructed, and a well-signed but schema-invalid payload rejected after.

Four properties the spec makes binding, each of which is a test rather than a comment.

Byte-identical republication. Regenerating a feed for a vendor whose changes have not moved must produce the same bytes, so a consumer's cached copy is never invalidated by a no-op run. That means sorting deterministically and never embedding a generation timestamp. This is the property most easily lost and the one nobody notices until every client redownloads daily.

No customer data, ever. The feed is vendor-side public information produced before any customer relationship exists. No observed shapes, no call sites, no telemetry-derived anything. Write a test that asserts against the rendered bytes, not against the input, so a future field cannot leak one in.

The array is the whole contract. Assert a bare JSON array parses and a top-level object is rejected, matching what the spec froze.

A missing or wrong signature is a hard failure, never a warning. This feed drives code changes, so a forged entry proposes a patch against real code.

Ed25519 needs a library; add `cryptography` as the one dependency line you are permitted. Generate keys in tests rather than committing any, and do not commit a private key anywhere -- if you find yourself writing one to disk outside a tmp_path, stop.

Do NOT build hosting, a CDN uploader, a publish schedule, or key rotation. This task is render, sign, verify, parse. The spec calls the keypair and the publish job operational and out of scope.

Report what you built, how you made republication byte-identical, what you sorted on and why that ordering is stable, and for each test the exact mutation you ran.

</details>

---

## M3-W22: index a second language, which is the first real test of whether Lang...

`task_89baf4c72ebf` · created `2026-07-28 18:34:30` · status **completed**

### Result

{"completedBy":"term_e3aac1ed-88ac-4795-9d19-10a20c4ee7f3","filesModified":["src/sync/index/python_lang.py","tests/test_python_index.py","tests/fixtures/py","pyproject.toml","uv.lock"],"completedAt":"2026-07-28T18:50:49.247Z"}

<details><summary>Brief</summary>

M3-W22: index a second language, which is the first real test of whether LanguageAdapter is a plugin boundary or a shape one implementation happens to fit.

Own ONLY src/sync/index/python_lang.py and tests/test_python_index.py. You may also add ONE dependency line to pyproject.toml and nothing else in that file. Do not edit src/sync/core/, src/sync/graph/, src/sync/detect/, src/sync/remediate/, src/sync/mcp/, src/sync/route/, src/sync/signals/, other files under src/sync/index/, or docs/ -- other workers own those. You may IMPORT from any of them; you may not change them. If you cannot finish without editing one, stop and report rather than editing it.

Read CLAUDE.md first; it is binding. Test-first: prove each test RED before implementing, and report the exact mutation you ran for each test.

Set up: no database is needed. Rebase onto origin/main before starting. Three gates before committing: uv run pytest, uv run lint-imports (run it UNREDIRECTED and with PYTHONIOENCODING=utf-8 -- it renders through rich, whose Windows path encodes with cp1252 and dies on its own spinner emoji, and a dead linter looks exactly like a broken contract), and uv run python scripts/lint_encoding.py src tests.

Why this task matters more than it looks. docs/superpowers/specs/2026-07-25-sync-competitive-position.md argues the moat is the synthesis machinery that produces coverage without hand-authored adapters, and that coverage is the market requirement rather than the moat itself. Every language claim in this repository currently rests on one implementation. src/sync/core/protocols.py declares LanguageAdapter as a plugin protocol, and exactly one type satisfies it. A protocol with one implementation is a shape that implementation happens to fit; a protocol with two is a boundary. Finding out which this is, is the point.

What to build. A Python LanguageAdapter -- indexing call sites in a customer's PYTHON source, not in Sync's own. Add tree-sitter-python as the one dependency line you are permitted; tree-sitter itself is already a dependency.

Read src/sync/index/typescript.py first and read it closely. It is your precedent and it is also the thing under test: where you find yourself unable to follow it, that is a finding about the protocol rather than about Python, and I want it reported rather than worked around silently.

Satisfy the protocol as declared: language_id, matches, index, prepare, static_verify. Two of those will not mean for Python what they mean for TypeScript.

`static_verify` is the interesting one. TypeScript has tsc and the whole verification story rests on it. Python has no equivalent gate that is present in every project -- mypy is optional, often unconfigured, and frequently failing on code that ships. Do NOT invent a gate. Decide what static_verify honestly returns when a project has no typechecker configured, make that decision explicit in the code and in your report, and be aware of what CLAUDE.md says: nothing reaches a pull request unverified. If Python cannot honour that with the same strength TypeScript does, say so plainly -- that is a real limitation of extending to this language and the project would rather know it than have it papered over.

`prepare` similarly: TypeScript installs dependencies with the customer's lockfile manager before typechecking. Decide what the Python equivalent is, or whether there is one worth doing.

For `index`, the target shape is a call site that binds to a vendor operation. In Python that is `stripe.Charge.create(...)` or `client.charges.create(...)` -- a dotted attribute chain ending in a call, with keyword arguments. Record the same CallSite fields typescript.py records, including args_keys, because the parameter-deprecation detector already joins on those and gets the second language for free if you populate them.

Constraints.

No network in any test. Fixtures are committed Python source files under tests/fixtures/, in the shape the TypeScript fixtures already take.

Non-ASCII source must be handled. tree-sitter reports byte offsets and Python string slicing is by character; src/sync/route/templates.py carries a fix for exactly that confusion and its docstring explains the failure. Every fixture in this repository is ASCII, so no existing test would catch it -- write one that does.

Do not weaken anything to make the protocol fit. If a method cannot be honestly implemented, implement what is honest and report the gap.

Report what you built, every place the protocol did not fit and what you did about it, what static_verify returns without a typechecker and why, and for each test the exact mutation you ran.

</details>

---

## M3-W23: turn the generated-SDK manifest reader into a vendor adapter, so one...

`task_1bea86018a05` · created `2026-07-28 18:56:22` · status **completed**

### Result

{"completedBy":"term_e3aac1ed-88ac-4795-9d19-10a20c4ee7f3","filesModified":["src/sync/signals/generated/adapter.py","src/sync/signals/generated/__init__.py","tests/test_generated_adapter.py"],"completedAt":"2026-07-28T19:06:52.969Z"}

<details><summary>Brief</summary>

M3-W23: turn the generated-SDK manifest reader into a vendor adapter, so one adapter covers many vendors.

Own ONLY src/sync/signals/generated/adapter.py, src/sync/signals/generated/__init__.py, and tests/test_generated_adapter.py. Do not edit src/sync/signals/generated/manifest.py (it is correct and tested), nor src/sync/core/, src/sync/graph/, src/sync/detect/, src/sync/remediate/, src/sync/mcp/, src/sync/route/, src/sync/index/, other packages under src/sync/signals/, or docs/. You may IMPORT from any of them. If you cannot finish without editing one, stop and report rather than editing it.

Read CLAUDE.md first; it is binding. Test-first: prove each test RED before implementing, and report the exact mutation you ran for each test.

Set up: no database is needed. Rebase onto origin/main before starting. Three gates before committing: uv run pytest, uv run lint-imports (run it UNREDIRECTED and with PYTHONIOENCODING=utf-8 -- it renders through rich, whose Windows path encodes with cp1252 and dies on its own spinner emoji, and a dead linter looks exactly like a broken contract), and uv run python scripts/lint_encoding.py src tests.

Why this is the highest-value item left. docs/superpowers/specs/2026-07-27-sync-adapter-targets.md argues coverage is the market requirement and hand-written adapters are the wrong way to get it. SDK generators commit a manifest naming the specification they generated from -- Stainless writes .stats.yml, Speakeasy writes .speakeasy/workflow.yaml -- and they do it for their own reasons, so no vendor has to cooperate and no agreement can be withdrawn. src/sync/signals/generated/manifest.py already parses both and is well tested. Nothing consumes it. Read that module and tests/test_generated_manifest.py first; the parsing is done and is not your job.

What to build. A VendorAdapter satisfying src/sync/core/protocols.py, driven by a manifest rather than by hand-written vendor knowledge.

fetch_changes: given a manifest, resolve the spec location, retrieve the two versions being compared, and hand them to the existing oasdiff wrapper in src/sync/signals/oasdiff.py to produce VendorChange rows. Do not reimplement diffing; run_oasdiff_breaking and to_vendor_changes already exist and are tested.

Inject the fetch as a callable, the way src/sync/signals/deprecations/adapter.py does. No test may touch the network. Read that adapter first -- its caching, its stale-cache fallback, and its refusal to treat an empty result as "nothing changed" are the pattern to follow, and its reasoning applies here unchanged.

The cheap trigger is the point and it must be tested. When a manifest carries openapi_spec_hash, a run that finds the hash unmoved must NOT download the spec at all. Assert that with a fetch counter, not by inspection. That property is the entire economic argument: polling a text file in a public repository costs nothing, and only vendors whose hash actually moved pay for a spec fetch and an oasdiff run.

Four things the spec already measured that you must handle rather than discover.

Not every manifest carries a hash, and some carry no URL either -- Cloudflare and Orb publish only configured_endpoints. SpecSource.is_fetchable already reports this. A vendor that is not fetchable yields no changes and is not an error; it still needs a hand-written adapter, and saying so is the honest answer.

openapi_spec_url points at generator-hosted storage rather than the vendor. That is acceptable as a change HINT and not as the authoritative artifact. Where a vendor-published spec is available, prefer it. Record which was used, because a diff taken from a mirror is weaker evidence than one taken from the vendor.

A hash that is absent on either side means the answer is unknown, and unknown must read as changed rather than unchanged. The deprecation adapter makes exactly this call for the same reason: reporting "no change" from missing evidence silently skips a vendor forever, and nothing surfaces it.

operation_for_symbol has no honest answer here. This adapter knows a specification, not an SDK's symbol scheme -- that is precisely the vendor-specific knowledge it exists to avoid. Return None and say why in the docstring rather than inventing a naming convention; src/sync/signals/deprecations/adapter.py has the precedent for a protocol method that honestly answers nothing.

Do NOT build a scheduler, a repository crawler, or a list of vendors to poll. This task is manifest to VendorChange rows.

Report what you built, how you proved the hash trigger avoids the download, what a non-fetchable vendor does, and for each test the exact mutation you ran.

</details>

---

## M3-W24: run the two detectors nothing runs, so findings they can already prod...

`task_1109c65b0bad` · created `2026-07-28 19:35:07` · status **completed**

### Result

{"completedBy":"term_e3aac1ed-88ac-4795-9d19-10a20c4ee7f3","filesModified":["src/sync/cli.py","tests/test_cli.py"],"completedAt":"2026-07-28T19:47:49.212Z"}

<details><summary>Brief</summary>

M3-W24: run the two detectors nothing runs, so findings they can already produce actually reach the pipeline.

Own ONLY src/sync/cli.py and tests/test_cli.py. Do not edit src/sync/core/, src/sync/graph/, src/sync/detect/, src/sync/remediate/, src/sync/mcp/, src/sync/route/, src/sync/index/, src/sync/signals/, or docs/ -- other workers own those. You may IMPORT from any of them; you may not change them. If you cannot finish without editing one, stop and report rather than editing it.

Read CLAUDE.md first; it is binding. Test-first: prove each test RED before implementing, and report the exact mutation you ran for each test.

Set up: export SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_w24 and create that database. Rebase onto origin/main before starting. Three gates before committing: uv run pytest, uv run lint-imports (run it UNREDIRECTED and with PYTHONIOENCODING=utf-8 -- it renders through rich, whose Windows path encodes with cp1252 and dies on its own spinner emoji, and a dead linter looks exactly like a broken contract), and uv run python scripts/lint_encoding.py src tests.

The problem, stated precisely. Three detectors exist, all satisfying the Detector protocol in src/sync/core/protocols.py, all tested. Exactly one is ever called: src/sync/cli.py line 243 runs VendorChangeDetector and nothing else. ParameterDeprecationDetector in src/sync/detect/parameter_deprecation.py and ObservedDriftDetector in src/sync/detect/observed_drift.py are unreachable from any entry point. They are finished work that cannot produce a single finding, which is the same as not having built them.

Read src/sync/cli.py in full first, then each detector's module and its tests, so you know what inputs each genuinely needs rather than guessing.

What to build. Bring both into the scan path so a run produces every finding the graph can support.

Each detector needs different inputs and this is the substance of the task, not a formality.

ParameterDeprecationDetector takes parsed parameter deprecations and call sites. The deprecations come from src/sync/signals/deprecations/ -- parse_parameter_deprecations over a vendor page, and DeprecationAdapter already knows how to fetch and cache one. The call sites must carry args_keys, which src/sync/index/literals.py populates and which the TypeScript indexer also records.

ObservedDriftDetector compares the observed_shape baseline against a published specification. Read its constructor and give it what it asks for. If the baseline is empty -- which it will be on any repository where nothing has fed Sentry payloads in -- it must produce no findings and must not error. An empty baseline is the normal case today, not a fault.

Four constraints.

A detector that cannot run must not stop the ones that can. If the drift detector has no baseline, or a vendor page cannot be fetched, the scan still reports what the other detectors found. Losing one detector's findings is bad; losing the whole run because one input was missing is worse. Test that explicitly.

Do not fetch anything in a test. The deprecation adapter takes an injected fetch callable precisely so tests need no network; use it. Fixtures are committed.

Findings from every detector go into the same store through the same path. Do not add a second write path or a second Finding shape -- the whole architecture rests on one Finding type reaching one remediation pipeline, and CLAUDE.md says so.

Report per detector how many findings each produced, so a run tells an operator which detector is silent. A detector that silently produces nothing forever is indistinguishable from one that is broken, and that is the failure this task exists to end.

Do NOT change what any detector does, add a fourth detector, or alter the Finding type. This task is wiring.

Report what you wired, what each detector needed that the CLI did not already have, what happens when the drift baseline is empty, and for each test the exact mutation you ran.

</details>

---

## M3-W25: stop omit_parameter silently leaving matches behind.

`task_228972b84ed3` · created `2026-07-28 19:52:09` · status **completed**

### Result

{"completedBy":"term_e3aac1ed-88ac-4795-9d19-10a20c4ee7f3","filesModified":["src/sync/route/templates.py","tests/test_route_defects.py"],"completedAt":"2026-07-28T20:10:23.841Z"}

<details><summary>Brief</summary>

M3-W25: stop omit_parameter silently leaving matches behind.

Own ONLY src/sync/route/templates.py and tests for it (tests/test_parameter_omit.py, tests/test_route_defects.py). Do not edit src/sync/core/, src/sync/graph/, src/sync/detect/, src/sync/remediate/, src/sync/mcp/, src/sync/index/, src/sync/signals/, src/sync/cli.py or docs/ -- other workers own those. You may IMPORT from any of them; you may not change them. If you cannot finish without editing one, stop and report rather than editing it.

Read CLAUDE.md first; it is binding. Test-first: prove each test RED before implementing, and report the exact mutation you ran for each test.

Set up: no database is needed. Rebase onto origin/main before starting. Three gates before committing: uv run pytest, uv run lint-imports (run it UNREDIRECTED and with PYTHONIOENCODING=utf-8 -- it renders through rich, whose Windows path encodes with cp1252 and dies on its own spinner emoji, and a dead linter looks exactly like a broken contract), and uv run python scripts/lint_encoding.py src tests.

The defect, which a previous worker found, measured and deliberately left in place rather than papering over. src/sync/route/templates.py line 42 sets _MAX_REMOVALS = 200 and omit_parameter loops that many times. The bound counts passes over the WHOLE SOURCE, and each pass makes exactly one removal, so a file containing more matching calls than the bound keeps the remainder. Measured by that worker: 201 calls each passing the key leaves one behind, 250 leaves fifty. It happens silently and the output parses.

That is the worst class of failure this project recognises -- a patch that compiles, type-checks, and is quietly wrong. No realistic object carries two hundred copies of one key, but a file carrying two hundred calls that each pass it is ordinary, and a large customer file is exactly where nobody reads the diff line by line.

The previous worker's conclusion was that the real fix is a caller-visible signal, which changes omit_parameter's contract. Consider that, and consider one alternative before choosing.

The bound exists to stop an infinite loop from a span that fails to shrink the source. But a pass that removes something IS progress, and the function already returns early when a computed span is empty. If the loop instead continued while the source is still shrinking and stopped when a pass changes nothing, it would terminate naturally when no match remains, never truncate, and need no contract change at all. Satisfy yourself whether that is sound -- in particular whether any input can make a pass shrink the source without removing a match, which would turn a natural-termination loop into a slow corruption.

Choose whichever is actually correct, not whichever is smaller. If you change the contract, every caller must be updated -- src/sync/remediate/parameters.py calls this and is NOT yours, so if the contract change reaches it, stop and report rather than editing it, and I will schedule that separately.

Two tests are required whichever way you go. One proves a file with more matching calls than the old bound now has every one removed -- construct it, do not hand-write two hundred calls. One proves the loop still terminates on whatever pathological input motivated the bound; if you conclude no such input exists, say so and show why rather than deleting the guard on faith.

While you are here, check one thing the earlier audit did not: rename_parameter builds all its edits from a single parse and applies them together, where omit_parameter re-parses between removals. Satisfy yourself that renames cannot overlap the way deletions did -- a rename replaces a key in place and does not consume a separator, so it probably cannot, but "probably" is why I am asking rather than telling.

Report which fix you chose and why the other was wrong, whether any input can shrink the source without removing a match, what you concluded about rename_parameter, and for each test the exact mutation you ran.

</details>

---

## M3-W26: compute the benchmark axes from the corpus, so the measurement exists...

`task_2a143ad09239` · created `2026-07-28 21:42:52` · status **completed**

### Result

{"completedBy":"term_e3aac1ed-88ac-4795-9d19-10a20c4ee7f3","filesModified":["src/sync/benchmark/__init__.py","src/sync/benchmark/axes.py","tests/test_benchmark_axes.py"],"completedAt":"2026-07-28T21:49:22.303Z"}

<details><summary>Brief</summary>

M3-W26: compute the benchmark axes from the corpus, so the measurement exists before the rows do.

Own ONLY src/sync/benchmark/ (a new package) and tests/test_benchmark_axes.py. Do not edit src/sync/core/, src/sync/graph/, src/sync/detect/, src/sync/remediate/, src/sync/mcp/, src/sync/route/, src/sync/index/, src/sync/signals/, src/sync/cli.py or docs/ -- other workers own those. You may IMPORT from any of them; you may not change them. If you cannot finish without editing one, stop and report rather than editing it.

Read CLAUDE.md first; it is binding. Test-first: prove each test RED before implementing, and report the exact mutation you ran for each test.

Set up: export SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_w26 and create that database. Rebase onto origin/main before starting. Three gates before committing: uv run pytest, uv run lint-imports (run it UNREDIRECTED and with PYTHONIOENCODING=utf-8 -- it renders through rich, whose Windows path encodes with cp1252 and dies on its own spinner emoji, and a dead linter looks exactly like a broken contract), and uv run python scripts/lint_encoding.py src tests.

The specification is docs/superpowers/specs/2026-07-28-sync-benchmark-gates.md. Read it before writing anything, and read src/sync/core/models.py (MigrationOutcome) and the store methods in src/sync/graph/store.py that read the corpus.

Scope, stated precisely because it is easy to overreach here. The spec blocks tier B on the corpus holding rows, and it holds zero today -- no real pipeline run has produced one. That blocks the GATE, which is a pass/fail verdict in CI. It does not block the COMPUTATION. Build the computation now, tested against synthetic rows, so the measurement works the day real ones arrive. Do NOT wire anything into CI, do NOT add a pass/fail threshold, and do NOT invent a number to gate on -- the spec is explicit that a gate at an invented threshold either fires constantly and gets disabled or never fires and gives false assurance.

What to build. A module that reads MigrationOutcome rows and computes the five axes the spec names: merge rate split by change_kind and by tier, routing accuracy (of attempts routed to tier 0, the share that passed verification without falling back), cost per merged patch in tokens and wall_ms, and the counts that binding precision and false-positive rate will need. Return them as data, not as printed text -- something a caller can serialise, compare across runs, and later gate on.

Four properties the spec makes binding, each a test rather than a comment.

Every axis reports its sample size alongside its value. The spec is blunt about why: a merge rate over four pull requests is not a merge rate, and presenting it as one is how a solo founder talks themselves into a wrong conclusion with nobody in the room to object. An axis that cannot report n is not finished.

An empty corpus produces zero-sample axes, not zeros. There is a real difference between "the merge rate is 0%" and "no attempts have been recorded", and code that returns 0.0 for both makes the distinction unrecoverable. This is the normal case today, so it is the case most likely to be got wrong.

The grain is one row per ATTEMPT, not per finding. A finding retried three times contributes three rows and one outcome. Any rate that divides by row count where it means finding count is wrong, and wrong quietly. Decide which denominator each axis needs, state it, and test a multi-attempt finding.

Nothing derived from arg_key_hashes may be aggregated across deployments. src/sync/core/corpus.py explains why: that column is salted per deployment, so grouping on it across customers returns one bucket per customer and looks exactly like an answer. If an axis is tempted toward it, use the shape columns instead.

Do NOT build the ground-truth mining harness the spec describes. That is a separate and much larger piece, and the spec says its first deliverable is a count rather than a harness.

Report what you built, which denominator each axis uses and why, what an empty corpus returns, and for each test the exact mutation you ran.

</details>

---

## M3-W27: reconcile the specs with what is actually built, so a fresh session d...

`task_54cd2ae1e246` · created `2026-07-28 21:52:49` · status **completed**

### Result

{"completedBy":"term_e3aac1ed-88ac-4795-9d19-10a20c4ee7f3","filesModified":["docs/superpowers/specs/2026-07-25-sync-graph-surface-design.md","docs/superpowers/specs/2026-07-25-sync-latency-architecture.md","docs/superpowers/specs/2026-07-25-sync-migration-corpus.md","docs/superpowers/specs/2026-07-25-sync-threat-model.md","docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md","docs/superpowers/specs/2026-07-26-sync-public-change-feed.md","docs/superpowers/specs/2026-07-27-sync-adapter-targets.md","docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md","docs/superpowers/specs/2026-07-27-sync-routing-matrix.md","docs/superpowers/specs/2026-07-28-sync-deprecation-signal.md","docs/superpowers/specs/2026-07-28-sync-domain-specific-thesis.md"],"completedAt":"2026-07-28T22:03:10.171Z"}

<details><summary>Brief</summary>

M3-W27: reconcile the specs with what is actually built, so a fresh session does not rebuild finished work.

Own ONLY docs/superpowers/specs/*.md. Do not touch docs/superpowers/BACKLOG.md (another coordinator owns it), docs/superpowers/plans/, docs/superpowers/reports/, or ANY file under src/ or tests/. This task changes prose only. If you find a genuine code defect while reading, report it -- do not fix it.

Read CLAUDE.md first; it is binding, including its rule that comments and docs state constraints rather than narrate changes.

Set up: no database is needed. Rebase onto origin/main before starting. Gates before committing: uv run pytest and uv run python scripts/lint_encoding.py src tests must still pass (they should be untouched by a docs-only change; if they are not, you edited something you should not have).

The problem. Twelve specs were written ahead of the code, which was correct at the time. A great deal has since been built, and several specs still describe finished work as unbuilt. This already caused real harm in the other direction: four specs once asserted migration_outcome existed when it did not, and the routing matrix instructed an implementer to write into columns that were never created. The failure mode is now mirrored -- a fresh session reading these would rebuild things that exist.

These exist in code today and at least one spec still says otherwise: the migration_outcome table and its model, the observed_shape table and its model, src/sync/benchmark/ computing the benchmark axes, src/sync/mcp/ with three of the four graph-surface tools, src/sync/detect/observed_drift.py, src/sync/signals/sentry/, src/sync/signals/feed/, src/sync/signals/generated/adapter.py, src/sync/index/python_lang.py, and the tier-0 codemods under src/sync/remediate/.

Your method, and it matters more than the edits. For every claim you change, open the file that proves it and cite it in the spec by path. Do not update a spec because this brief listed something -- verify it yourself. This brief is a starting point and it may itself be wrong or stale by the time you read it.

Four rules.

Correct, do not rewrite. These specs carry arguments that are still sound and reasoning that took work to arrive at. Change the claims that are false and leave the rest alone. A spec that reads as though it were written after the fact loses the record of what was decided under uncertainty, which is most of its value.

Where a spec is still right, leave it and say so in your report. Several things genuinely remain unbuilt -- the fourth MCP tool, a Datadog adapter, the replay tier, the interceptor SDK, the ground-truth mining harness, the benchmark GATE as distinct from its computation. Do not mark those done. Marking unbuilt work as built is worse than the drift you are fixing.

Preserve the corrections already recorded. Several specs carry explicit "an earlier version of this document claimed X and was wrong" passages. Those are the most valuable prose in the repository and they must survive. If you find yourself deleting one because it is now obsolete, you have misread it -- it documents a mistake, not a state.

Note what you cannot verify. If a claim is about something outside this repository -- a competitor, a vendor's behaviour, a measurement taken on a date -- do not touch it. You have no way to check it and a confident edit would be worse than staleness.

Report every claim you changed with the file and line that proves it, every claim you left alone and why, and anything you found that looks like a code defect rather than a documentation one.

</details>

---

## M3-W28: make the routing table actually select the tier, which it currently d...

`task_7281690049a0` · created `2026-07-28 22:08:03` · status **completed**

### Result

{"completedBy":"term_e3aac1ed-88ac-4795-9d19-10a20c4ee7f3","filesModified":["src/sync/remediate/tiered.py","tests/test_tiered_remediator.py"],"completedAt":"2026-07-28T22:19:17.285Z"}

<details><summary>Brief</summary>

M3-W28: make the routing table actually select the tier, which it currently does not.

Own ONLY src/sync/remediate/tiered.py and tests/test_tiered_remediator.py. Do not edit src/sync/route/ (the table is correct and another concern), src/sync/core/, src/sync/graph/, src/sync/mcp/, src/sync/index/, src/sync/signals/, src/sync/cli.py or docs/. You may IMPORT from any of them. If you cannot finish without editing one, stop and report rather than editing it.

Read CLAUDE.md first; it is binding. Test-first: prove each test RED before implementing, and report the exact mutation you ran for each test.

Set up: export SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_w28 and create that database. Rebase onto origin/main. Three gates before committing: uv run pytest, uv run lint-imports (UNREDIRECTED, with PYTHONIOENCODING=utf-8 -- it renders through rich, dies on its own emoji under cp1252, and a dead linter looks exactly like a broken contract), and uv run python scripts/lint_encoding.py src tests.

The gap, found while reconciling the specs against the code. docs/superpowers/specs/2026-07-27-sync-routing-matrix.md specifies a nine-row decision table that assigns a tier to every oasdiff rule, and src/sync/route/matrix.py implements it with tests. Nothing calls it to choose a remediator. src/sync/remediate/tiered.py picks by asking each remediator can_handle in list order, so the table is decorative: the tier a finding actually gets is decided by which remediator happens to be first in a list, and route() is never consulted.

Two consequences the specs already record. The benchmark spec notes tier and strategy record which tier ran but the deciding row does not exist to record, so "tier 0 was wrong for this change kind" stays unanswerable. And the matrix spec's tier -1 -- the 21 lifecycle rules where no edit in a consumer repository resolves anything -- has no effect at all today, so a lifecycle finding still reaches a remediator that will try to patch it.

What to build. Consult route() to decide the tier, then pick the remediator that serves it. Read src/sync/route/matrix.py, its tests, and tiered.py's existing docstring first -- that docstring contains two decisions that are correct and must survive: an empty diff does not fall through to the next tier, and a retry skips deterministic tiers because a codemod re-run with feedback re-emits the byte-identical patch that just failed.

Three constraints.

Tier -1 must produce no patch at all. A lifecycle finding is a complaint about how a vendor documented a deprecation; no edit resolves it, and routing one to an agent produces a confident patch against code that was never wrong.

RoutingFacts must be populated from what is actually known, not defaulted to favourable. Every field defaults to None meaning not established, and the table declines when a fact is unknown -- that is what stops an unpopulated graph routing work to a codemod. Where the call site genuinely does not tell you a fact, leave it None.

The row that decided must be recorded so it can reach migration_outcome. That is the whole reason route() returns it.

Report what you wired, how a lifecycle finding now terminates, which RoutingFacts you could populate and which you had to leave unknown, and for each test the exact mutation you ran.

</details>

---

## M3-W29: receive the merge webhook, so the one measurement that tests the prod...

`task_0a60f82e416a` · created `2026-07-28 22:08:04` · status **completed**

### Result

{"completedBy":"term_9db05c37-3503-42b5-8add-64a8d747099b","filesModified":["src/sync/forge/webhook.py","tests/test_merge_webhook.py"],"completedAt":"2026-07-28T22:27:15.933Z"}

<details><summary>Brief</summary>

M3-W29: receive the merge webhook, so the one measurement that tests the product claim has a numerator.

Own ONLY src/sync/forge/webhook.py (new) and tests/test_merge_webhook.py. Do not edit src/sync/forge/github.py, src/sync/core/, src/sync/graph/, src/sync/remediate/, src/sync/mcp/, src/sync/route/, src/sync/index/, src/sync/signals/, src/sync/cli.py or docs/. You may IMPORT from any of them. If you cannot finish without editing one, stop and report rather than editing it.

Read CLAUDE.md first; it is binding. Test-first: prove each test RED before implementing, and report the exact mutation you ran for each test.

Set up: export SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_w29 and create that database. Rebase onto origin/main. Three gates before committing: uv run pytest, uv run lint-imports (UNREDIRECTED, with PYTHONIOENCODING=utf-8), and uv run python scripts/lint_encoding.py src tests.

The gap. docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md audits its own preconditions and finds this one does not hold: GraphStore.set_merge_outcome exists as the update path and nothing calls it. No webhook receiver is built, so pr_merged and human_edits_before_merge stay null forever and the merge rate -- the direct test of the product claim that binding-driven patches land more often -- has no numerator. The corpus spec says the same thing more bluntly: merge outcome arrives days after the run and must be collected, not inferred.

What to build. A pure function that turns a GitHub pull-request webhook payload into a call to GraphStore.set_merge_outcome. Read that method's signature and tests/test_migration_corpus.py first.

No network, no server, no framework. This is payload plus store to a recorded outcome. A caller mounts it wherever they like; that is not your problem and adding a web framework would be the wrong call.

Constraints.

Signature verification is required and is not optional theatre. GitHub signs webhooks with HMAC-SHA256 over the raw body. An unverified receiver lets anyone write to the corpus, which is the table every future routing decision is measured against. Verify before parsing, the way src/sync/signals/feed/consumer.py verifies before parsing, and for the same reason: a signature proves origin, not correctness, so a validly signed payload that is malformed must still be rejected at parse. Use hmac.compare_digest, never ==; a timing-variable comparison on a signature is a real weakness rather than a style point.

human_edits_before_merge means commits on the branch that Sync did not author. Decide how you identify Sync's own commits, state the rule, and test it. Getting this wrong makes every merged patch look either fully human-edited or fully untouched, and that column exists precisely to tell those apart.

A payload for a pull request Sync never opened is not an error. Other automation and humans open pull requests in the same repository. Ignore it quietly and test that.

Only merges and closures matter. A webhook fires on many actions; recording an outcome on the wrong one writes a merge that has not happened.

Report what you built, how you identify a Sync-authored commit, what an unknown pull request does, and for each test the exact mutation you ran.

</details>

---

## M3-W30: read Datadog error and trace payloads into the shape store, giving th...

`task_66ed930d7f0f` · created `2026-07-28 22:08:34` · status **completed**

### Result

{"completedBy":"term_a6120af8-0e4e-41be-9377-d9bd0b9be45b","filesModified":["src/sync/signals/datadog/__init__.py","src/sync/signals/datadog/shapes.py","tests/fixtures/datadog/stripe_charge_error.json","tests/test_datadog_signal.py"],"completedAt":"2026-07-28T22:23:06.001Z"}

<details><summary>Brief</summary>

M3-W30: read Datadog error and trace payloads into the shape store, giving the drift detector a second feeder.

Own ONLY src/sync/signals/datadog/ (a new package) and tests/test_datadog_signal.py. Do not edit src/sync/core/, src/sync/graph/, src/sync/detect/, src/sync/remediate/, src/sync/mcp/, src/sync/route/, src/sync/index/, other packages under src/sync/signals/, src/sync/cli.py or docs/. You may IMPORT from any of them. If you cannot finish without editing one, stop and report rather than editing it.

Read CLAUDE.md first; it is binding. Test-first: prove each test RED before implementing, and report the exact mutation you ran for each test.

Set up: export SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_w30 and create that database. Rebase onto origin/main. Three gates before committing: uv run pytest, uv run lint-imports (UNREDIRECTED, with PYTHONIOENCODING=utf-8), and uv run python scripts/lint_encoding.py src tests.

Why. docs/superpowers/specs/2026-07-25-sync-competitive-position.md sequences Sentry and Datadog as M2 signal sources and is explicit that Sync must NOT build OTLP ingestion -- competing with Datadog on infrastructure is a losing position, while joining against the graph is not. So this consumes what Datadog already holds; it does not receive telemetry.

Your precedent is src/sync/signals/sentry/shapes.py, which does exactly this job for Sentry payloads. Read it and tests/test_sentry_signal.py first, along with ObservedShape.from_observation in src/sync/core/models.py and GraphStore.record_observed_shape. The reduction rules are already implemented there; use them rather than reimplementing the decision.

What to build. A module turning a Datadog payload into ObservedShape rows recorded with source='error-payload'. Walk a decoded JSON response body and yield one observation per field path, carrying the JSON-pointer path, the JSON type, and nullability.

The privacy rule is the point and must be tested, not commented. Values never leave the extraction boundary. Record paths, types, nullability. Record an enum value ONLY where it appears in the vendor's published specification -- from_observation already enforces that. Free-form values, amounts, names, tokens, email addresses, identifiers must never reach a column. Write a test that feeds a payload stuffed with obviously sensitive values and asserts against the serialised rows that none survive, the way tests/test_migration_corpus.py::test_no_source_text_reaches_the_row does.

Constraints.

No network and no Datadog API client in any test or in the module. Fixtures are committed. Take a real payload shape from Datadog's public documentation, commit a trimmed copy, parse that.

Arrays are the hard part and Sentry's module already made this decision. Read how it addresses array elements in a JSON pointer and follow it -- two modules feeding one table must agree, or the same field looks like drift depending on which source saw it. If you believe Sentry's rule is wrong, report that rather than diverging from it.

A malformed payload yields no rows rather than raising. This reads third-party data and one bad event must not stop the others. Log rather than swallow: silence on one payload is correct, silence on all of them is not.

State the bias. Error-payload shapes are biased toward failures, so a baseline built only from them is not a baseline of normal traffic. Sentry's module says so; say it here too rather than letting two sources quietly imply broader coverage than they have.

Report what you built, whether you followed Sentry's array rule and why, what the bias means when two error-shaped sources feed one baseline, and for each test the exact mutation you ran.

</details>

---

## M3-W31: run the ground-truth mining count, and do not build the harness

`task_c1a0e77d4a4c` · created `2026-07-28 22:19:02` · status **completed**

### Result

{"completedBy":"term_a3b1c9f4-f03a-45a1-8760-d19db3e4e314","filesModified":["scripts/mine_stripe_migrations.py","tests/test_mine_stripe_migrations.py","tests/fixtures/github_search/code_pins_page.json","tests/fixtures/github_search/code_pins_incomplete.json","tests/fixtures/github_search/search_rate_limited.json","tests/fixtures/github_search/search_empty.json","docs/superpowers/specs/2026-07-28-sync-ground-truth-count.md"],"completedAt":"2026-07-28T22:31:39.383Z"}

<details><summary>Brief</summary>

M3-W31: run the ground-truth mining count, and do not build the harness

## Why this task exists

`docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` says two of Sync's five
quality axes — binding precision and binding recall — cannot be computed at all today,
for a reason no amount of engineering fixes: the migration corpus records what Sync
*did*, not what was *correct*. Precision and recall need a labelled reference, and a
solo founder with no users has no labels.

The spec's proposal is to mine migrations that already happened. Open-source
repositories pin a Stripe API version. Some later bump it across a release Stripe
classifies as breaking. The human's own migration commit is a labelled patch — a
correct answer, authored by someone with full context.

The spec is then unusually emphatic about sequencing, and this task exists to honour it:

> **The first deliverable is measurement, not construction.** Before building a harness,
> count: how many public repositories pin a Stripe API version, and of those, how many
> contain a commit that bumps it across a release Stripe classifies as breaking? If the
> answer is a handful, the approach fails on sample size and something else is needed —
> synthetic mutation of real repositories is the fallback, at the cost of realism.
> **Do not build the harness before running the count.** That is the whole discipline of
> this section.

So: **you are producing a number and a written verdict, not a mining harness.** If you
find yourself writing code that clones repositories, checks out parent commits, or runs
Sync's pipeline, you have left this task's scope. Stop and finish the count.

## Read first

- `CLAUDE.md` at the repository root. It is binding. Every rule in it applies here.
- `docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md`, the section titled
  "Ground truth without customers" in full, including the three stated weaknesses
  (survivorship, the human is not always right, commit granularity). Your report must
  address all three.

## Files you own

Nothing outside this list. Other tasks are running in parallel in this same repository
and touching a file you do not own will collide with them.

- Create: `scripts/mine_stripe_migrations.py`
- Create: `tests/test_mine_stripe_migrations.py`
- Create: `tests/fixtures/github_search/` and the fixture files inside it
- Create: `docs/superpowers/specs/2026-07-28-sync-ground-truth-count.md`

You may read anything in the repository. You may write only the paths above.

## What the script does

`scripts/mine_stripe_migrations.py` is a measurement instrument, run by hand. It has two
responsibilities, and the split between them is the whole design:

1. **Fetching** — issue GitHub code-search and commit-search queries through the `gh`
   CLI, which is already authenticated on this machine. This is the part that touches the
   network.
2. **Counting and classifying** — take raw search-result JSON and reduce it to the
   numbers the spec asks for. This is pure, takes JSON in and returns a structure out, and
   is the only part that is tested.

Keep these in separate functions with the pure part taking parsed JSON as an argument.
A pure counting function that a test can drive from a committed fixture is the entire
reason this task is testable at all.

### The queries

Stripe pins appear in source as an `apiVersion` assignment. Search for the pin, then for
commits that change it. GitHub's code search API is rate-limited and caps results, so:

- Record the **total count** the API reports, not just the length of the page you
  received. GitHub reports `total_count` in its search response and that is the number the
  spec is asking for.
- If a query is truncated, incomplete, or rate-limited, say so in the output. A count
  that silently reflects one page of results, presented as a total, is exactly the kind of
  wrong-and-quiet number `CLAUDE.md` warns about.
- Handle the case where `gh` returns an error or a rate-limit response by reporting it,
  not by returning zero. Zero and "could not measure" are different answers and the
  difference decides whether the whole approach is viable.

Which Stripe releases count as breaking: Stripe publishes dated API versions and
classifies its releases. Use whatever list you can establish from the repository's own
committed fixtures first — check `tests/fixtures/` for Stripe spec pairs already present
— and if the repository does not carry a release list, state in your report that the
breaking-release boundary was determined from the versions you could observe, and name
them. Do not invent a list of dates.

## Test discipline

`CLAUDE.md` is binding and says two things that decide the shape of these tests.

**No test calls a vendor API or a model API.** The GitHub API is a vendor API. Your tests
therefore never invoke `gh` and never touch the network. They drive the pure counting
function from committed fixture JSON in `tests/fixtures/github_search/`.

**A test that cannot fail is worse than no test.** Prove each test fails before the code
exists. Write the test, run it, watch it fail for the reason you expect, then implement.

The fixtures you commit must include, at minimum:

- A normal search response with a `total_count` and a page of items.
- A response where `incomplete_results` is true, asserting the counter reports truncation
  rather than presenting the number as final.
- An error or rate-limited response, asserting the counter distinguishes "could not
  measure" from "measured zero". This is the test that matters most; make sure it fails
  before you write the branch that satisfies it.

## The report is the deliverable

`docs/superpowers/specs/2026-07-28-sync-ground-truth-count.md` is what this task is for.
Write it in normal prose, in the voice of the other specs in that directory — they are
your model for tone and structure. It must contain:

- **The numbers**, each with the query that produced it and the date it was run. A count
  with no query beside it cannot be reproduced or challenged.
- **A verdict on viability.** The spec sets the bar itself: if the answer is a handful,
  the approach fails on sample size. State plainly whether the mining approach is viable,
  and if it is not, say that the fallback is synthetic mutation of real repositories at
  the cost of realism.
- **The three weaknesses**, each addressed against what you actually measured rather than
  restated from the spec: survivorship bias, the human not always being right, and
  migrations bundled into large refactors that cannot be isolated.
- **What you could not measure and why.** Rate limits, search caps, private repositories.
  A benchmark whose bias is undocumented is worse than none — that is the spec's own
  standard and it applies to this count.

Do not write a recommendation to build the harness, and do not sketch its design. The
next decision belongs to whoever reads your number.

## Before you commit

Set your own `SYNC_DSN` to a database no other task is using so a parallel worker's
schema changes cannot affect your run.

Run all three gates and make them pass:

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its
reporter emits emoji, and on this machine a redirected run dies on a cp1252 encode error
that looks exactly like a contract violation but is not one.

`scripts/lint_encoding.py` will fail your script if any `open`, `read_text`, `write_text`,
or `subprocess.run(..., text=True)` call omits `encoding="utf-8"`. `subprocess` is the one
that is easy to forget and it fails worst: a decode error there is raised on the reader
thread and never propagates, so the call returns with `stdout` set to `None` and the next
line that touches it raises `TypeError` somewhere unrelated. You are shelling out to `gh`,
so this applies to you directly.

Commit with a Conventional Commits subject and a body in normal prose explaining why.
Then report back: the numbers you measured, your viability verdict in one line, and the
three gate results.

</details>

---

## M3-W32: make tier -1 reach the end without entering the patch node

`task_d793fedf3597` · created `2026-07-28 22:27:43` · status **completed**

### Result

{"completedBy":"term_ed3a02b9-4556-4dbe-a1ae-9e96d3e4e372","filesModified":["src/sync/remediate/graph.py","src/sync/remediate/nodes.py","src/sync/remediate/state.py","src/sync/cli.py","tests/test_no_patch_route.py","tests/test_cli.py"],"completedAt":"2026-07-28T22:43:04.784Z"}

<details><summary>Brief</summary>

M3-W32: make tier -1 reach the end without entering the patch node

## The defect, and how to see it for yourself

`src/sync/remediate/tiered.py` raises `NoPatchWarranted` when the decision table routes a
finding to tier -1 — the report-only tier, for the 21 `kind=lifecycle` oasdiff rules that
describe how a vendor documented a deprecation and imply no edit to the customer's code at
all.

That exception is raised from inside the cascade, and the cascade is invoked from inside
the `patch` node. Grep for the exception across the repository:

```
grep -rn "NoPatchWarranted" src/ tests/
```

Every hit outside `tiered.py` is in `tests/test_tiered_remediator.py`. Nothing in
`src/sync/remediate/nodes.py` or `src/sync/remediate/graph.py` catches it. So a lifecycle
finding today takes this path:

1. `route_after_prepare` looks only at `state["prepare_ok"]` and returns `"patch"`.
2. The `patch` node runs.
3. The cascade raises `NoPatchWarranted`, which nothing in the graph handles.

`docs/superpowers/specs/2026-07-27-sync-routing-matrix.md` names this exact outcome in its
Verification section, and the second half of the sentence is the part that makes it a
defect rather than a cosmetic complaint:

> **Tier -1 emits no patch.** A `lifecycle` finding must produce a report and reach `END`
> without entering `patch`. Assert on the node sequence, not on the absence of a diff — a
> patch node that ran and produced nothing is a different bug wearing the same result.

That is the bug we currently have, precisely: the patch node runs and produces nothing.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-27-sync-routing-matrix.md` — the tiers table, the section
  "Tier -1 exists because 21 breaking rules are not about the consumer's code", the section
  "Where it goes in the graph", and the Verification section.
- `docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` — specifically the rule
  that abandoned runs are data and `abandon_reason` stays queryable. A tier -1 report is not
  an abandonment, and you will need to be careful about the difference.
- `src/sync/remediate/tiered.py`, especially `tier_for` and its docstring. Read it as
  context you must not break; you do not own it.

## Files you own

Nothing outside this list. Five other tasks are running in parallel in this repository
right now and each owns files you must not touch.

- Modify: `src/sync/remediate/graph.py`
- Modify: `src/sync/remediate/nodes.py`
- Modify: `src/sync/remediate/state.py`
- Create: `tests/test_no_patch_route.py`

**Explicitly forbidden, each owned by a live task:** `src/sync/graph/schema.sql`,
`src/sync/core/models.py`, anything under `src/sync/signals/`, anything under
`src/sync/index/`, anything under `src/sync/mcp/`, `src/sync/forge/webhook.py`, and
`src/sync/remediate/tiered.py`. Read any of them freely. Write none of them.

If your design appears to require editing a forbidden file, stop and report that instead of
doing it. A collision with a parallel worker costs more than the delay.

## The design constraint that decides the shape

There is an obvious wrong fix: catch `NoPatchWarranted` inside the `patch` node and return
early. **Do not do that.** It leaves the patch node in the executed node sequence, which is
the precise thing the spec's verification bullet forbids, and it makes the corpus record a
patch attempt where none was warranted.

The routing decision has to be made before the branch, and `route_after_static` already
models the discipline the new predicate must follow. From the same spec:

> `route_after_static` already models the discipline any new predicate must follow: it
> branches on `verify_ok`, an explicit boolean a node set deliberately, rather than on
> whether `diagnostics` happens to be non-empty. A real `tsc` failure can exit non-zero with
> nothing on either stream. Routing predicates read state that was set on purpose.

So: a node decides the tier deliberately and writes it to `RunState`; `route_after_prepare`
reads that stored value and branches. The predicate does not recompute the route and does
not infer it from the presence or absence of something else.

**Compute the route exactly once.** The same spec warns why, in the context of a future
learned policy:

> **Features are computed by one shared function**, used both when routing live and when
> fitting offline. Two implementations that agree today diverge on the first edge case, and
> the failure is silent — good offline scores, bad live routing.

Two call sites that both ask the table, and can disagree, is the same failure in miniature.
Whatever you write, there must be one place the tier is determined and one place it is
stored.

## What the report node does

Add a report-only destination out of the same conditional edge that already chooses between
`patch` and `abandon`. It records the finding as reported, not patched, not abandoned, and
reaches `END`.

Three things about it are load-bearing:

- **A tier -1 outcome is not an abandonment.** Abandonment means Sync tried and could not
  finish; tier -1 means there was correctly nothing to try. The pipeline-discipline spec
  makes `abandon_reason` the field where routing learns which change kinds are not
  mechanically safe, and polluting it with "this kind never needed a patch" corrupts exactly
  that signal. Keep them distinguishable.
- **The routing decision reaches the corpus.** `migration_outcome` already has `tier` and
  `strategy` columns and `RunState` already carries what the corpus recorder needs. Record
  the tier that fired and the decision-table row that chose it, using the machinery that is
  already there. **You may not add a column** — `schema.sql` belongs to another task right
  now. If you conclude a column is genuinely required, report that conclusion rather than
  making the change.
- **It is a real finding and worth surfacing.** The spec says these are "real findings and
  worth surfacing; they are simply not remediation findings." The node reports; it does not
  silently drop.

## Test discipline

`CLAUDE.md` is binding: test first, always. Write the failing test, run it, watch it fail
for the reason you expect, then implement. A test that has never failed has never been shown
to test anything.

`tests/test_no_patch_route.py` must contain, at minimum:

- **The node-sequence assertion.** Drive a `kind=lifecycle` finding through the graph and
  assert `patch` is not in the executed node sequence. Assert on the sequence itself — the
  spec is explicit that asserting the absence of a diff is a weaker test that a broken
  implementation passes. Prove this test fails against the current code before you change
  anything: it should fail today, since the patch node is entered.
- **A non-lifecycle finding still reaches `patch`.** Without this, an implementation that
  routes everything away from `patch` passes the first test. This is the test that makes the
  first one mean something.
- **The recorded outcome distinguishes report-only from abandoned.** Assert the corpus row
  for a tier -1 finding is not indistinguishable from an abandoned attempt.
- **The tier is computed once.** Assert the stored tier on `RunState` is what the branch
  acted on, rather than the predicate having recomputed it.

Use your own `SYNC_DSN` pointing at a database no other task is using — several workers are
running migrations in parallel right now.

## Before you commit

Run all three gates and make them pass:

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter
emits emoji and on this machine a redirected run dies on a cp1252 encode error that looks
exactly like a contract violation but is not one.

The full suite is currently 1050 passing. If your change breaks a test you did not write,
that is a real signal about the graph's shape and not something to route around — read the
failure before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why, not
what. Then report: the node sequence your test asserts, how a report-only outcome is
distinguished from an abandoned one in the corpus, and the three gate results.

</details>

---

## M3-W33: compute binding precision and recall, split by rung, and gate nothing

`task_34cc7452a629` · created `2026-07-28 22:37:16` · status **completed**

### Result

{"completedBy":"term_26b15093-5760-4bbb-a865-38b2be53aee8","filesModified":["src/sync/benchmark/binding.py","src/sync/benchmark/__init__.py","tests/test_binding_accuracy.py","tests/fixtures/binding_labels/known_answer.json","tests/fixtures/binding_labels/rung_split.json","tests/fixtures/binding_labels/missed_call_sites.json"],"completedAt":"2026-07-28T22:49:25.412Z"}

<details><summary>Brief</summary>

M3-W33: compute binding precision and recall, split by rung, and gate nothing

## Why this task exists

`docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` lists five quality axes. Three
are computed today by `src/sync/benchmark/axes.py`. Two are not: binding precision and
binding recall, which the spec calls the ones that matter most.

> | **Binding precision** | Of findings emitted, the share whose call site genuinely depends
> on the changed operation | A false finding spends reviewer trust, and trust does not
> recover at the rate it is spent |
> | **Binding recall** | Of call sites genuinely affected, the share that produced a finding
> | A missed break is the failure the product exists to prevent |

They are uncomputable today for a reason no engineering fixes: the corpus records what Sync
*did*, not what was *correct*. Precision and recall need a labelled reference.

**The computation is not blocked by that. Only the score is.** This is the same distinction
the spec draws for tier B — *"What remains blocked is the gate, not the computation"* — and
it is why three of the five axes are already built against a corpus that holds no rows. Your
job is the function, tested against fixtures, ready for the day labels exist.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` — the tier B table, the
  section "Ground truth without customers", and all of "Gate tier C".
- `docs/superpowers/specs/2026-07-28-sync-ground-truth-count.md` — the measurement that just
  landed. It tells you the label source is not what anyone assumed, which is why your
  function must take labels as an argument rather than know where they come from.
- `src/sync/benchmark/axes.py` — your model for tone, shape, and how an axis reports a null
  rather than a zero. Match it. You are adding a sibling, not a new style.
- `docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` — the rung rule, quoted
  below, which decides this module's most important signature detail.

## Files you own

Nothing outside this list. Three other tasks are running in parallel and own most of `src/`.

- Create: `src/sync/benchmark/binding.py`
- Modify: `src/sync/benchmark/__init__.py`
- Create: `tests/test_binding_accuracy.py`
- Create: `tests/fixtures/binding_labels/` and the fixtures inside it

**Explicitly forbidden, each owned by a live task:** `src/sync/core/`, `src/sync/graph/`,
`src/sync/mcp/`, `src/sync/remediate/`, `src/sync/route/`, `src/sync/signals/`,
`src/sync/detect/`, `src/sync/index/`, `src/sync/telemetry/`, `src/sync/cli.py`. Read any of
them. Write none. `src/sync/benchmark/axes.py` is also not yours — read it as your model, do
not edit it.

If your design appears to require editing a forbidden file, stop and report that instead of
doing it.

## The signature detail that matters most

Precision and recall must each be reportable **split by provenance rung**, not only in
aggregate. `CLAUDE.md` and the pipeline-discipline spec both make this binding:

> **Every binding carries the rung it came from** — `static`, `resolved`, or `observed` — and
> so does every artifact derived from it. A false positive that cannot be attributed to a
> rung cannot be fixed.

An aggregate precision of 0.7 tells you nothing actionable. Precision of 0.95 on `observed`
bindings and 0.4 on `static` ones tells you exactly where the binder is guessing. Design the
return type so the split is the primary output and the aggregate is derived from it, rather
than the other way round — a caller that wants only the aggregate can sum, but a caller
handed only an aggregate cannot recover the split.

The same discipline the spec demands of merge rate applies here and for the same reason:
*"Unsplit it is meaningless — a high rate driven by one easy kind says nothing."*

## What the function takes and returns

A pure function. Findings in, labels in, scores out. It does not query the database, does not
know where labels come from, and does not read a file. `axes.py` reads the corpus because its
axes are about what Sync did; yours are about what was correct, and correctness arrives from
outside.

Requirements on the result:

- **Every axis reports its sample size.** The spec is emphatic: *"A merge rate over four pull
  requests is not a merge rate, and presenting it as one is how a solo founder talks
  themselves into a wrong conclusion with nobody in the room to object."* The same applies to
  a precision over four findings.
- **An axis with no samples reports a null, not a zero.** Zero precision means every finding
  was wrong. No samples means nothing was measured. Conflating them turns an empty corpus
  into a false alarm. `axes.py` already draws this distinction — follow how it does it.
- **Excluded items are counted and returned, not silently dropped.** The spec's Verification
  section: *"Silent exclusion turns a biased sample into an unqualified number."* If a finding
  has no corresponding label, it cannot be scored — return how many were excluded and why,
  alongside the score.

Precision and recall have different denominators and different exclusion rules, and the
difference is the whole point of computing both. A finding with no label is excluded from
precision. A labelled call site with no finding is a **false negative**, not an exclusion —
it is precisely what recall exists to count. Getting this backwards produces a recall of 1.0
on any input, which is the failure mode to write a test against.

## What you must not do

**Do not add a threshold, a gate, or a CI step.** The spec forbids it in terms:

> **do not invent a threshold.** A gate at an invented number either fires constantly and
> gets disabled, or never fires and provides false assurance. Until the numbers are
> established, tier B axes are **recorded, not gated**.

Nothing you write goes into `.github/workflows/ci.yml`. No constant in your module is a pass
mark. If you find yourself writing a comparison against a number you chose, delete it.

**Do not build a label source.** `2026-07-28-sync-ground-truth-count.md` establishes that the
obvious source — mined migration commits — is viable on sample size but unproven on label
quality, and that decision is not yours or mine to make inside this task. Your fixtures are
hand-written label sets that exercise the arithmetic. They are not a corpus and must not be
presented as one.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you
expect, then implement. A test that has never failed has never been shown to test anything.

At minimum:

- **Known-answer arithmetic.** A hand-built set where precision and recall are different
  numbers you can verify by hand. If a bug swaps the two, this test must catch it — so do not
  choose a fixture where they happen to be equal.
- **The rung split.** A fixture where one rung scores well and another scores badly, asserting
  both appear separately and that the aggregate does not hide the bad one.
- **Null, not zero, on an empty input.** Assert the type distinguishes them.
- **A labelled call site with no finding lowers recall and does not raise precision.** This is
  the test that catches the denominator confusion described above. Prove it fails before you
  write the code.
- **Exclusions are reported.** A finding with no label must appear in an exclusion count
  rather than vanishing.

Use your own `SYNC_DSN` pointing at a database no other task is using, even though this module
should not touch the database — several workers are running migrations in parallel.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter
emits emoji and on this machine a redirected run dies on a cp1252 encode error that looks
exactly like a contract violation but is not one.

The suite is currently 1085 passing. A test you did not write going red is a real signal —
read it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: the return type you chose and why the rung split is primary in it, how a false
negative is kept distinct from an exclusion, and the three gate results.

</details>

---

## M3-W34: re-audit every spec's self-audit against the repository

`task_5b2747805ef9` · created `2026-07-28 22:37:17` · status **completed**

### Result

{"completedBy":"term_b64d2f71-f51d-4c54-a60b-36cc381b4fdb","filesModified":["docs/superpowers/specs/2026-07-25-sync-migration-corpus.md","docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md","docs/superpowers/specs/2026-07-26-sync-review-integration.md","docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md","docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md","docs/superpowers/specs/2026-07-27-sync-routing-matrix.md","docs/superpowers/specs/2026-07-28-sync-deprecation-signal.md","docs/superpowers/specs/2026-07-28-sync-domain-specific-thesis.md","docs/superpowers/specs/2026-07-28-sync-spec-audit-log.md"],"completedAt":"2026-07-28T22:53:53.579Z"}

<details><summary>Brief</summary>

M3-W34: re-audit every spec's self-audit against the repository, and correct what has gone stale

## Why this task exists

The specs in `docs/superpowers/specs/` are unusual and deliberately so: several of them audit
their own preconditions and state plainly which hold and which do not. That is the property
that makes them a coordination substrate rather than aspirational prose — an agent reads a
spec, sees "Does not hold", and knows there is work there.

The property decays. Work lands, and the sentence that described the gap stays. Two examples
that are wrong at this moment:

- `2026-07-27-sync-benchmark-gates.md:92` says of the merge webhook precondition: **"Does not
  hold. `GraphStore.set_merge_outcome` exists as the update path, and nothing calls it: no
  webhook receiver is built, so both columns stay null and the merge rate has no numerator."**
  A webhook receiver was built and merged. `src/sync/forge/webhook.py` exists, verifies an
  HMAC-SHA256 signature before parsing, and calls the update path.
- `2026-07-27-sync-routing-matrix.md` says in "What is built": **"The decision table below
  still does not drive the routing. `sync.route.matrix.route()` is imported by nothing outside
  `src/sync/route/`."** It is now imported and called by `src/sync/remediate/tiered.py`. That
  claim needs correcting — but read the rest of this brief before you correct it, because the
  correction is not the obvious one.

A stale "does not hold" sends a worker to build something that exists. A stale "built" is
worse: it stops anyone from building something that does not. Both have happened here.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full. Note especially the code-style rule
  about comments that talk to a reviewer, because the equivalent applies to spec prose: write
  what is true now, not a changelog of what changed.
- Every file in `docs/superpowers/specs/`. All of them. This task is a sweep and a partial
  sweep is worse than none, because it leaves no signal about which files were checked.

## Files you own

- Modify: any file under `docs/superpowers/specs/`.
- Create: `docs/superpowers/specs/2026-07-28-sync-spec-audit-log.md`

Nothing under `src/`, `tests/`, or `scripts/`. Not one line. Four other tasks are running in
parallel and own most of the source tree; this task is documentation only, which is exactly
what makes it safe to run alongside them.

You must **read** source freely — the entire point is checking claims against code — but every
write goes to `docs/superpowers/specs/`.

## What to do

For every spec, find each claim it makes about the state of the repository. They appear as
**Status:** lines in the header, as "Holds" / "Does not hold" / "Holds in part" verdicts, as
"Built" / "Not built" cells in sequencing tables, and as prose assertions like "X is imported
by nothing" or "no Y exists".

For each such claim, verify it against the repository as it stands right now. Read the code.
Run `grep`. Do not reason from the git log about what probably landed — check the file.

Then, for each claim:

- **True** — leave it alone. Do not reword it, do not add "still true as of", do not touch it.
  An unnecessary edit to a spec costs a reviewer the same attention as a necessary one.
- **False** — correct it to what is true now, in the spec's own voice, with the same
  specificity the original had. The originals name files and line numbers; yours should too.
- **Half-true** — this is the interesting case and the one to be careful with. See below.

## The half-true case, which is most of the value here

A claim can become false in a way that hides a new gap, and replacing it with "this is built
now" destroys information.

The routing-matrix example is exactly this. `route()` is now called from `tiered.py`, so
"imported by nothing" is false. But a decision gate raised on this build established that
`src/sync/cli.py` constructs `TieredRemediator` with no catalogue argument, so `_catalogue` is
empty and the table has jurisdiction over nothing in production. A task is in flight to wire
it. So the honest correction is neither "does not drive the routing" nor "drives the routing"
— it is that the wiring exists and whether it is reachable depends on the catalogue, plus
whatever you find to be true when you check.

Check that one yourself rather than taking this brief's word for it; a task may have landed
since this was written. That caution applies to every example here.

When you hit a half-true claim, write what is true with its qualification, the way the specs
already do elsewhere. `CLAUDE.md` itself models the register:

> Two honest qualifications on that, both measured rather than theorised

That is the voice. A qualification that a reader can act on beats a verdict that is clean.

## The audit log

`docs/superpowers/specs/2026-07-28-sync-spec-audit-log.md` records the sweep so the next
person knows what was checked and when. It must contain:

- **Every spec file, listed** — including the ones you changed nothing in. A file absent from
  the list is indistinguishable from a file you forgot, which defeats the purpose.
- **For each: the claims checked, and the verdict on each.** Correct, corrected, or qualified.
- **The evidence for each correction** — the file, and the line or symbol you checked. A
  correction with no evidence beside it cannot be challenged by the next reader, and this
  document's whole job is to be challengeable.
- **Claims you could not verify, and why.** Some claims are about things no query settles —
  hosting that does not exist, a keypair nobody generated, a customer nobody has. Say so
  plainly rather than guessing. The spec corpus already prefers a stated unknown to a
  confident wrong answer, and this log must match that standard.

Write it in normal prose, in the voice of the other specs. It is not a table dump.

## What you must not do

**Do not rewrite specs you find disagreeable.** You are correcting claims about repository
state. Design decisions, arguments, and conclusions are out of scope even where you think they
are wrong — if you believe a spec's reasoning is mistaken, say so in the audit log and leave
the spec's argument standing.

**Do not mark anything built that you have not seen the code for.** The failure mode this task
exists to fix is a claim nobody checked. Reproducing it in the other direction would be worse,
because a false "built" is the one that stops work from happening.

**Do not add a changelog section to any spec.** Correct the sentence in place. Git holds the
history and the audit log holds the sweep; a spec carrying its own revision history is noise
that grows forever.

## Before you commit

There is no test to write here, so `verification-before-completion` is satisfied differently:
your evidence is the audit log's per-claim entries, each naming the file or symbol you checked.
A correction in the log with no evidence beside it does not count as verified.

Run the gates anyway — you may have touched nothing they cover, and confirming that is the
point:

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter
emits emoji and on this machine a redirected run dies on a cp1252 encode error that looks
exactly like a contract violation but is not one.

The suite is currently 1085 passing. If it is not still 1085 passing, a parallel worker landed
something — say so in your report rather than investigating it, since the source is not yours.

Commit with a Conventional Commits subject (`docs:`) and a body in normal prose explaining why.
Then report: how many claims you checked, how many were stale, and the single most consequential
correction you made.

</details>

---

## M3-W35: synthesize a mock response where observed reality outranks the publis...

`task_4f523c348458` · created `2026-07-28 22:47:25` · status **completed**

### Result

{"completedBy":"term_ed3a02b9-4556-4dbe-a1ae-9e96d3e4e372","filesModified":["src/sync/verify/__init__.py","src/sync/verify/mock_response.py","tests/test_mock_response.py","tests/fixtures/mock_response/payment_intent.json"],"completedAt":"2026-07-28T23:02:41.216Z"}

<details><summary>Brief</summary>

M3-W35: synthesize a mock response where observed reality outranks the published spec

## Why this task exists

`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` specifies a replay
verification tier and records it as **Not built**. The gap it closes is stated plainly:

> The gap it closes: the design's risk table already concedes that repositories without CI
> have no verification path. The quieter problem is that a green CI run proves little when no
> test exercises the patched call. Most customers have no test covering their Stripe
> integration; a passing suite that never runs the patched path is weak evidence presented as
> strong.

The tier has three steps. **You are building the first one only:**

> 1. For each patched call site, synthesize a mock response from the **new** specification
>    version — and from the observed baseline where one exists, which catches the case where
>    reality and spec disagree.

Steps 2 and 3 execute customer code in a sandbox. **You are not building them, not
scaffolding them, and not writing a placeholder for them.** If you find yourself writing
anything that runs a subprocess, spawns a sandbox, or executes a call path, you have left
this task's scope — stop and finish the synthesizer.

The synthesizer is worth building alone because it is pure, it is the input to everything
downstream, and it can be tested completely without executing anything.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` — all of it. Especially
  "The shape store" (the privacy rule), "The replay verification tier", and the Verification
  section.
- `src/sync/core/models.py`, the `ObservedShape` model. Read only.
- `src/sync/detect/observed_drift.py`, especially its `MIN_SAMPLES` constant and its module
  docstring, which states honestly what the detector can and cannot see. Read only. Your
  sample floor must agree with its sample floor; two floors that can drift is the same defect
  the Datadog signal module avoided by importing Sentry's array rule rather than copying it.

## Files you own

`src/sync/verify/` does not exist yet. You are creating it.

- Create: `src/sync/verify/__init__.py`
- Create: `src/sync/verify/mock_response.py`
- Create: `tests/test_mock_response.py`
- Create: `tests/fixtures/mock_response/` and the fixtures inside it

**Explicitly forbidden, each owned by a live task:** `src/sync/core/`, `src/sync/graph/`,
`src/sync/mcp/`, `src/sync/remediate/`, `src/sync/route/`, `src/sync/signals/`,
`src/sync/detect/`, `src/sync/index/`, `src/sync/telemetry/`, `src/sync/benchmark/`,
`src/sync/cli.py`, and everything under `docs/superpowers/specs/`. Read any of them. Write
none.

Note on the import boundary: `sync.core` must import nothing from a sibling, and
`tests/test_import_boundary.py` enforces that. The rule is directional — your new
`sync.verify` package may import from `sync.core` freely, and must not be imported by it.

## What the function does

A pure function. A schema and a set of observed shapes go in; a mock response body comes out.
It does not query the database, does not fetch a specification, and does not read a file. The
caller supplies both inputs.

**The precedence rule is the entire point of this task.** Where the published specification
and the observed baseline disagree about a field, **the observed shape wins.** The spec's
argument for why:

> A specification says what the vendor promised. Observed traffic says what the vendor did.
> When those diverge, something changed that nobody announced.

A mock built only from the specification tests the patch against the vendor's promise. A mock
that prefers observation tests it against reality, and reality is what breaks customers. Make
the precedence explicit and obvious in the code — a reader should not have to infer which
source won.

Three constraints on the output:

- **Never emit a value the specification does not name.** The shape store's privacy rule
  means observed baselines carry field paths, JSON types, nullability, and presence rates,
  plus enum values *only where the published spec names them*. There is no free-form value in
  the store to leak, and your synthesizer must not invent one that looks real either. Where a
  string is needed and the spec names no enum, emit an obviously synthetic placeholder, not a
  plausible-looking identifier. A mock carrying something that reads like a real customer
  identifier is a bug even when the value was fabricated.
- **Respect the sample floor.** A shape seen too few times is not a baseline. Below the floor,
  fall back to the specification rather than trusting thin observation. Take the floor from
  `sync.detect.observed_drift` rather than declaring your own number.
- **Arrays follow the store's addressing rule.** Observed field paths collapse every array
  element to `-`, the one array token RFC 6901 defines. `src/sync/signals/sentry/shapes.py`
  carries the reasoning in its module docstring — read it, because a synthesizer that expects
  indexed pointers will match nothing.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you
expect, then implement. A test that has never failed has never been shown to test anything.

At minimum:

- **Observed beats spec.** A fixture where the spec says a field is a required string and the
  observation says it is nullable, asserting the mock reflects the observation. This is the
  test the task exists for; prove it fails before you write the precedence.
- **Spec fills what observation does not cover.** A field present in the spec and absent from
  the baseline still appears in the mock. Without this, a synthesizer that ignores the spec
  entirely passes the first test.
- **Below the floor, the spec wins.** A baseline with too few samples does not override the
  specification. Assert on the boundary, not far from it — a floor that is off by one is a
  real bug and a test at ten times the floor cannot see it.
- **No plausible values.** Assert the output contains no string that could pass for a real
  identifier, token, or amount. State in the test what rule you are asserting, because this
  one protects a threat-model commitment rather than a behaviour.
- **Nested objects and arrays round-trip.** A JSON Pointer three levels deep, and an array
  path using `-`, both produce correctly shaped output.

Use your own `SYNC_DSN` pointing at a database no other task is using, even though this module
should not touch the database — several workers are running migrations in parallel.

## What to record rather than build

The spec says every replay run is also a shape-store writer (`source = 'replay'`), which is
how the baseline accumulates before any customer installs anything. **That writer is not
yours** — it belongs to the execution step you are not building, and the store is owned by
another task right now. Note it in your module docstring as the caller's job, so the next
person does not rediscover it.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter
emits emoji and on this machine a redirected run dies on a cp1252 encode error that looks
exactly like a contract violation but is not one. Your new package makes this gate matter more
than usual — `sync.verify` is a new node in the import graph, so run it and read the output
rather than skimming for green.

The suite is currently 1098 passing. A test you did not write going red is a real signal —
read it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: how the precedence rule is expressed in the code, what your sample floor is and where
you took it from, and the three gate results.

</details>

---

## M3-W36: give the two uncalled adapters a caller

`task_28fce0feae0f` · created `2026-07-28 23:01:33` · status **completed**

### Result

{"completedBy":"term_26b15093-5760-4bbb-a865-38b2be53aee8","filesModified":["src/sync/cli.py","tests/test_cli.py","tests/test_cli_wiring.py"],"completedAt":"2026-07-28T23:23:23.951Z"}

<details><summary>Brief</summary>

M3-W36: give the two uncalled adapters a caller, so their paths exist outside tests

## Why this task exists

`docs/superpowers/specs/2026-07-28-sync-spec-audit-log.md` swept the spec corpus against the
code and found two complete, tested components that nothing in `src/` ever calls. Both were
verified with `grep`, and the log quotes the commands.

**The model-retirement deprecation path.** From the audit log:

> `DeprecationAdapter` is the only caller of `parse_deprecation_table` and `to_vendor_changes`
> (`src/sync/signals/deprecations/adapter.py:129,145`), and `grep -rn "DeprecationAdapter("`
> over `src/` returns nothing. So no `ModelDeprecation` becomes a `VendorChange`, and
> `LiteralSwapRemediator` sits in the cascade with nothing to act on — which is the document's
> headline path, unreachable.

**OTLP span ingestion.** From the same log:

> `ingest_payload` has no caller in `src/` outside the package's own `__init__`.

`src/sync/telemetry/otlp.py` decodes OTLP/JSON export payloads and `src/sync/telemetry/ingest.py`
folds client spans into `observed_call`. Both are built and tested. Nothing runs them.

This is the same defect four times over in this repository: a complete, tested component whose
only callers are its own tests. It is not a testing failure — the tests pass and they test
something real. It is that the component is unreachable in production, so the capability the
specs claim does not exist where it matters.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-28-sync-spec-audit-log.md`, the sections "The deprecation
  signal" and "OTLP".
- `docs/superpowers/specs/2026-07-28-sync-deprecation-signal.md` — its Sequencing table now
  narrows the outstanding work to exactly one missing call site. That is the one you are adding.
- `src/sync/cli.py`, and in particular how `load_catalogue()` at line 70 is called once at line
  557 and its result handed to two consumers. That is the pattern for wiring something once and
  sharing it, and it is the pattern to follow.
- `src/sync/signals/deprecations/adapter.py` and `src/sync/telemetry/ingest.py`. Read only —
  both are owned by another live task.

## Files you own

- Modify: `src/sync/cli.py`
- Create: `tests/test_cli_wiring.py`
- Modify: `tests/test_cli.py` — **only** to update assertions your change breaks. Do not add
  new tests there; new tests go in your own file.

**Explicitly forbidden, each owned by a live task or out of scope:** everything under
`src/sync/signals/`, `src/sync/telemetry/`, `src/sync/index/`, `src/sync/detect/`,
`src/sync/core/`, `src/sync/graph/`, `src/sync/mcp/`, `src/sync/remediate/`, `src/sync/route/`,
`src/sync/verify/`, `src/sync/benchmark/`, and `docs/superpowers/specs/`.

You are adding call sites, not changing the things being called. If a component turns out to
need a signature change before it can be wired, **stop and report that** rather than editing a
forbidden file — that is a finding worth more than the wiring.

## What to build

Two call sites, each wired the way `load_catalogue()` is: constructed once where the run has
what it needs, and handed to whatever consumes it.

**`DeprecationAdapter`.** `cli.py:409` already constructs `ParameterDeprecationDetector` for the
parameter half of the deprecation signal. The model-retirement half needs the equivalent. When
it is wired, a `ModelDeprecation` becomes a `VendorChange` and `LiteralSwapRemediator` — already
in the cascade — has something to act on.

**`ingest_payload`.** OTLP payloads arrive from outside; the decode and fold already exist. Wire
the path that takes a payload and lands client spans in `observed_call`.

Be careful about one thing here. `2026-07-27-sync-pipeline-discipline.md` records a deliberate
strategic refusal of ingestion *infrastructure* — the audit log confirms it still holds:
*"there is no server, no port and no collector protocol."* **Do not build one.** No HTTP
listener, no port binding, no collector. You are wiring the existing decode-and-fold to a caller
that already has the bytes. If your design starts to need a server, you have misread the scope.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement. A test that has never failed has never been shown to test anything.

The tests that matter here are the ones that would have caught the original defect, so write
those:

- **The path exists outside tests.** Assert the wiring from the production entry point, not by
  calling the adapter directly. A test that constructs `DeprecationAdapter` itself re-creates
  exactly the situation this task fixes — the component works, and nothing reaches it.
- **A model retirement produces a `VendorChange` end to end**, from whatever the production path
  takes as input through to the change reaching the remediation cascade. Prove this fails before
  you wire it.
- **An OTLP payload lands rows in `observed_call`** through the production path.
- **No server is started.** Assert the ingest path binds no port and starts no listener. This
  protects a stated strategic refusal, so state in the test what it is protecting.

`tests/test_cli.py` contains source-text proxy assertions — they read `cli.run`'s source with
`inspect.getsource` and assert on substrings. One already broke on a legitimate change during
this build, because it pinned a literal spelling rather than the property. If yours break the
same way, weaken the literal, preserve the property, and say so in your report. Do not contort
`cli.py` to satisfy a string.

Use your own `SYNC_DSN` pointing at a database no other task is using — several workers are
running migrations in parallel.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

The suite is currently 1131 passing. A test you did not write going red is a real signal — read
it before adjusting anything, and if it is a proxy assertion, say so.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: the two call sites you added with their line numbers, how your tests assert the
production path rather than the component, whether anything needed a signature change you did
not make, and the three gate results.

</details>

---

## M3-W37: make the dead-link pattern a lint

`task_a7bf9eb782dc` · created `2026-07-28 23:01:34` · status **completed**

### Result

{"completedBy":"term_b64d2f71-f51d-4c54-a60b-36cc381b4fdb","filesModified":[".github/workflows/ci.yml","scripts/lint_dead_links.py","scripts/dead_links_baseline.txt","tests/test_lint_dead_links.py","tests/fixtures/dead_links/"],"completedAt":"2026-07-28T23:16:35.543Z"}

<details><summary>Brief</summary>

M3-W37: make the dead-link pattern a lint, so it stops being found by hand

## Why this task exists

Four times in this repository, a complete and well-tested component has shipped with no caller
anywhere in `src/`. Each was found by a human reading code, weeks apart, and each had passing
tests the entire time:

- `GraphStore.set_merge_outcome` — the update path existed, no webhook receiver called it, and
  the merge rate had no numerator.
- `sync.route.matrix.route()` — the decision table was imported by nothing outside its own
  package, so the routing it specified never ran.
- `DeprecationAdapter` — `grep -rn "DeprecationAdapter(" src/` returns nothing, so no model
  retirement ever becomes a `VendorChange`.
- `ingest_payload` — OTLP decode and fold both built, nothing calls either.

The tests were not wrong and they were not weak. Every one of those components was tested
properly, in isolation, and worked. The defect is that **being tested and being reachable are
different properties, and this repository only ever checked the first.**

`CLAUDE.md` already treats a certain class of defect this way: the encoding rule cannot be caught
by any test, because every fixture is ASCII, so `scripts/lint_encoding.py` exists to catch it
statically instead. This is the same shape of problem and wants the same shape of answer.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `scripts/lint_encoding.py` — your model. It is an AST lint over the source tree with a CLI that
  exits non-zero on a violation. Match its structure, its argument handling, and its output
  format. You are writing a sibling, not a new kind of thing.
- `tests/test_lint_encoding.py` — your model for how a lint is proven able to fail.
- `docs/superpowers/specs/2026-07-28-sync-spec-audit-log.md` — the sweep that found two of the
  four. It quotes the exact `grep` commands used, which is the manual process you are replacing.
- `.github/workflows/ci.yml` — where lints run, and in what order, and why they run before the
  suite.

## Files you own

- Create: `scripts/lint_dead_links.py`
- Create: `tests/test_lint_dead_links.py`
- Create: `tests/fixtures/dead_links/` and the fixtures inside it
- Modify: `.github/workflows/ci.yml`

**Explicitly forbidden:** everything under `src/`, and everything under
`docs/superpowers/specs/`. Five other tasks are running in parallel and own most of the source
tree.

This matters more here than usual: **your lint will report real violations in `src/`, and fixing
them is not your task.** Two of the four listed above are being wired by another task right now.
Report what you find; change none of it.

## What the lint does

Find every public symbol defined under `src/sync/` whose only references are in `tests/`, in its
own module, or in its own package's `__init__.py`.

The hard part is not finding them. It is not drowning the signal, and this is where the task
succeeds or fails.

**A great many public symbols legitimately have no internal caller**, and a lint that reports all
of them is noise that gets disabled within a week — which is worse than no lint, because it also
consumes the attention that would have gone to a real finding. At minimum these are legitimate:

- Everything a third party imports. `CLAUDE.md` is explicit that `sync.core` is the public
  surface a vendor-adapter author depends on, so a `sync.core` model with no internal caller is
  the design working, not a defect.
- CLI entry points, invoked by name from `pyproject.toml` rather than by a Python caller.
- Anything registered by decorator, plugin discovery, or a string name.
- Test helpers and fixtures.

Design the scope so those do not report, and **write down the rule you chose in the module
docstring, with its reasoning**. A future reader needs to know what the lint deliberately does
not look at, because that is where the next dead link will hide.

Provide an explicit, greppable opt-out marker for the cases your rule cannot know about, and
require that each use carries a reason on the same line. An opt-out with no reason is how a lint
degrades into decoration.

## The bar this must clear

`CLAUDE.md`: *"A test that cannot fail is worse than no test — it manufactures confidence. When a
test asserts on a subprocess, an exit code, or an external tool, prove it detects a real
violation before trusting it. This has already bitten us once: the import-boundary test's
original form exited 0 without parsing its own argument."*

Your lint is exactly that kind of thing — a script CI checks by exit code. So:

- **Prove it exits non-zero on a known-bad fixture.** A tree containing a symbol referenced only
  from tests must fail the lint. Assert on the exit code *and* on the output naming the symbol,
  in that order, because a non-zero exit with unrelated output is a broken lint that looks like a
  working one.
- **Prove it exits zero on a known-good fixture**, including one containing each legitimate case
  above. This is the test that stops the lint from being noise.
- **Prove the opt-out works and that an opt-out without a reason does not.**
- **Run it against the real `src/` tree and record what it reports** in your commit body. If it
  reports the four known cases, say so — that is the lint validating itself against known
  ground truth, and it is the strongest evidence you can offer. If it reports something nobody
  knew about, that is a finding: report it, do not fix it.

## Wiring it into CI

Add it to `.github/workflows/ci.yml` alongside the existing lints. Two constraints from
`2026-07-27-sync-benchmark-gates.md`:

- **Lints run before the suite.** *"A lint failure is a fact about the source; it needs no
  database, no downloaded binary, and no test run to establish."* Put yours with the others,
  before `pytest`.
- If the lint currently fails against `main` because real dead links exist, **do not weaken the
  lint to make CI green, and do not fix `src/` to make it green.** Report the situation and
  propose how to land it — a baseline of known-accepted violations is the usual answer, and it
  must be a checked-in list that shrinks, never a threshold. State clearly in your report if you
  land it in a non-blocking mode, because a gate that cannot fail is the thing this whole task
  exists to argue against.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one. Your own script must set `encoding="utf-8"` on every file
read — `lint_encoding.py` will fail you otherwise, which is a fitting way to find out.

Use your own `SYNC_DSN` even though this task should not touch the database.

The suite is currently 1131 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: the scoping rule you chose and what it deliberately ignores, what the lint reports
against the real tree today, whether you landed it blocking or non-blocking and why, and the
three gate results.

</details>

---

## M3-W17b: give the graph surface a stdio transport and its fourth tool (redisp...

`task_bb8f567921d3` · created `2026-07-28 23:05:09` · status **completed**

### Result

{"completedBy":"term_a3b1c9f4-f03a-45a1-8760-d19db3e4e314","filesModified":["src/sync/mcp/server.py","src/sync/mcp/registry.py","src/sync/mcp/propose.py","src/sync/mcp/tools.py","src/sync/mcp/__init__.py","tests/test_mcp_server.py","tests/test_mcp_registry.py","tests/test_mcp_propose_patch.py","tests/golden/tool_schemas.json"],"completedAt":"2026-07-28T23:30:45.282Z"}

<details><summary>Brief</summary>

M3-W17: give the graph surface a stdio transport and its fourth tool, so an agent can actually reach it.

Own ONLY src/sync/mcp/ and tests for it. Do not edit src/sync/graph/, src/sync/core/, src/sync/remediate/, src/sync/route/ or docs/ -- other workers own those right now. You may IMPORT from any of them; you may not change them.

Read CLAUDE.md first; it is binding. Test-first: prove each test RED before implementing, and actually run every command you claim to have run.

Set up: export SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_w17 and create that database. Rebase onto origin/main before starting. Three gates before committing: uv run pytest, uv run lint-imports (unredirected -- redirecting it crashes rich's Windows renderer and looks like a contract failure), and uv run python scripts/lint_encoding.py src tests.

The specification is docs/superpowers/specs/2026-07-25-sync-graph-surface-design.md and the plan is docs/superpowers/plans/2026-07-25-sync-mcp-graph-surface.md. Read both. The tool set is frozen on first publish and may only grow, so do not add a fifth tool or rename an existing one.

The state you are walking into. src/sync/mcp/tools.py implements three of the four tools as a GraphSurface class over a narrow GraphReader protocol that GraphStore already satisfies structurally. tests/test_mcp_tools.py covers them, including the four response rules. Read both before writing anything; tools.py is your precedent for shape and docstring style.

Two things are missing.

First, there is no transport. Nothing exposes GraphSurface over stdio, so no agent can call it. Build the stdio MCP server. Keep the transport thin: it translates a tool call into a GraphSurface method and its return value into a response, and holds no logic of its own. Every tool schema must be declared with its arguments, since an agent composes against the schema rather than against your docstrings.

Second, sync_propose_patch is unimplemented. Per the spec it runs the existing remediation pipeline as far as static verification and stops -- no branch, no push, no pull request -- and returns the diff, the static_verify result, and the evidence. Import from src/sync/remediate/ rather than reimplementing anything; another worker owns that directory and is editing it, so treat its public surface as fixed and do not change it. If you find you cannot do this without editing remediate/, stop and report that rather than editing it.

The four response rules in the spec are binding and already tested for the other three tools: never return file contents, stay shallow with drill-down by identifier, paginate every list, and carry provenance plus context_savings on every response. sync_propose_patch returns a diff, which is the one deliberate exception to "never return file contents" -- the diff IS the answer there. Say so in a comment so nobody later reads it as a violation.

The server must never write to the customer's repository. It is a read surface plus a patch proposal; the spec is explicit that Sync returns patches as data and never writes.

Report what you built, the tool schemas you declared, how you proved the transport works without a live agent, whether sync_propose_patch was reachable without editing remediate/, and for each test the exact mutation you ran.

## Note on this redispatch

An earlier attempt at this task ran for seven hours, produced no commits, and left its worktree
clean before going silent. Nothing of it survives, so start from the specification above rather
than looking for partial work. src/sync/mcp/ still contains only __init__.py and tools.py.

Commit early and often. A commit per completed step is better than one at the end -- it is what
makes the work recoverable if this session ends the way the last one did.

</details>

---

## M3-W38: report the benchmark axes, and put the parameter remediators in the c...

`task_94a610518012` · created `2026-07-28 23:29:00` · status **completed**

### Result

{"completedBy":"term_26b15093-5760-4bbb-a865-38b2be53aee8","filesModified":["src/sync/cli.py","src/sync/benchmark/report.py","src/sync/benchmark/__init__.py","scripts/dead_links_baseline.txt","tests/test_benchmark_report.py"],"completedAt":"2026-07-28T23:43:35.421Z"}

<details><summary>Brief</summary>

M3-W38: report the benchmark axes, and put the parameter remediators in the cascade

## Why this task exists

`scripts/dead_links_baseline.txt` is now a verified list of components that are built, tested,
and reachable from nothing. Two groups on it are both wired from the same file, and both close a
gap a spec records as open.

**The benchmark axes compute and nobody can see them.** `compute_axes`,
`compute_binding_accuracy` and `BindingAccuracy.unlabelled_findings` have no caller in `src/`.
`docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` says what should happen to them:

> Until the numbers are established, tier B axes are **recorded, not gated** — written to the
> corpus every run, reviewed by a human, and reported with their sample size.

"Reviewed by a human" requires a way for a human to see them. There is none.

**The parameter remediators are not in the cascade.** `ParameterOmitRemediator` and
`ParameterRenameRemediator` in `src/sync/remediate/parameters.py` are complete and tested.
`build_remediator` in `src/sync/cli.py` composes `LiteralSwapRemediator`, `PropertyOmitRemediator`
and `TerminalTier(AgentRemediator())` — the two parameter strategies are absent, so a finding
that one of them could handle deterministically reaches the agent instead. That is the exact cost
the tiering exists to avoid: a model call against a change a codemod handles.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` — all of "Gate tier B" and all of
  "Gate tier C".
- `scripts/dead_links_baseline.txt`, including its header. The rules there bind you.
- `src/sync/benchmark/axes.py` and `src/sync/benchmark/binding.py` — what you are reporting.
- `src/sync/remediate/parameters.py` — the two remediators, and their `can_handle`.
- `src/sync/cli.py`, especially `build_remediator` and how `load_catalogue()` is called once at
  line 557 and shared.

## Files you own

- Modify: `src/sync/cli.py`
- Create: `src/sync/benchmark/report.py`
- Modify: `src/sync/benchmark/__init__.py`
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**, see below
- Create: `tests/test_benchmark_report.py`
- Modify: `tests/test_cli.py` — only to update assertions your change breaks

**Explicitly forbidden, each owned by a live task or out of scope:** `src/sync/index/`,
`src/sync/detect/`, `src/sync/core/`, `src/sync/graph/`, `src/sync/mcp/`, `src/sync/signals/`,
`src/sync/telemetry/`, `src/sync/remediate/` (read `parameters.py`, do not edit it),
`src/sync/route/`, `src/sync/verify/`, and `docs/superpowers/specs/`.

## The baseline rule, which will bite you if you ignore it

Wiring a symbol makes its baseline entry stale, and `scripts/lint_dead_links.py` **fails** on an
entry that no longer describes anything. From the file's own header:

> The file only shrinks. Adding a line is a decision, not a formality.

So in the same commit that wires a symbol, delete its line. You may only delete. If your change
creates a *new* unreachable symbol, do not add it to the baseline — that means you built
something with no caller, which is the defect this whole task is fixing. Wire it or do not build
it.

Run `uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt`
before you commit. It is a CI gate now.

## What to build

**The report.** A rendering of the tier B axes with, for each, its value and its sample size. The
spec is emphatic that the sample size travels with the number: *"A merge rate over four pull
requests is not a merge rate, and presenting it as one is how a solo founder talks themselves
into a wrong conclusion with nobody in the room to object."* An axis with no samples reports a
null, never a zero — `axes.py` already draws that distinction, so carry it through to the output
rather than flattening it.

Expose it as a CLI subcommand. The corpus currently holds no rows, so the honest output today is
every axis reporting null with a sample size of zero, and **that must render as a legible report
rather than as an error or an empty string**. A reporting surface that only works once data
exists cannot be tested before data exists.

**Do not add a threshold, a gate, or a CI step.** The spec forbids it in terms: *"do not invent a
threshold."* Nothing you write goes into `.github/workflows/ci.yml`. If you find yourself writing
a comparison against a number you chose, delete it.

**The cascade.** Add both parameter remediators to `build_remediator`. Order matters — the
cascade asks each remediator in sequence and the routing table narrows which are eligible, so
place them where a deterministic strategy is tried before the agent. Read the existing
composition and follow its logic rather than appending to the end.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement.

- **The report renders with an empty corpus.** Null axes, zero sample sizes, legible output.
  Prove it fails before the renderer exists.
- **A populated corpus reports real numbers with real sample sizes.** Build the rows in the test.
- **The sample size cannot be dropped.** Assert it appears for every axis, not just some.
- **Both parameter remediators are reachable from the production cascade.** Assert through
  `build_remediator()`, not by constructing the remediator directly — a test that constructs it
  itself re-creates exactly the situation this task fixes.
- **A finding one of them handles does not reach the agent tier.** This is the economic claim;
  assert it rather than assuming the ordering is right.

`tests/test_cli.py` contains source-text proxy assertions that read `cli.run`'s source and assert
on substrings. Two of them have already broken on legitimate changes during this build. If yours
break the same way, weaken the literal, preserve the property the test's name states, and say so
in your report. Do not contort `cli.py` to satisfy a string.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

The suite is currently 1187 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: what the report renders against an empty corpus, where you placed the two remediators in
the cascade and why there, which baseline lines you deleted, and the four gate results.

</details>

---

## M3-W39: close what can be closed on the tier-0 surface, and name exactly what...

`task_6bde5571c59e` · created `2026-07-28 23:29:01` · status **completed**

### Result

{"completedBy":"term_b64d2f71-f51d-4c54-a60b-36cc381b4fdb","filesModified":["src/sync/remediate/tiered.py","src/sync/remediate/property_omit.py","src/sync/route/templates.py","src/sync/route/matrix.py","scripts/dead_links_baseline.txt","tests/test_tier_zero_reach.py","tests/test_tiered_remediator.py"],"completedAt":"2026-07-28T23:45:27.369Z"}

<details><summary>Brief</summary>

M3-W39: close what can be closed on the tier-0 surface, and name exactly what cannot

## Why this task exists

Tier 0 is the deterministic codemod tier — the one that skips a model call entirely. It is the
whole economic claim: `CLAUDE.md` says *"knowing which change kinds are safely mechanical is what
lets Sync skip a model call and beat competitors on both cost and merge rate."*

`docs/superpowers/specs/2026-07-27-sync-routing-matrix.md` now records, in its "What is built"
section, that the tier-0 surface cannot fire:

> Even with a catalogue, rows 3 and 4 cannot fire from the default facts. `routing_facts` in
> `tiered.py` can establish `field_resolved` and `value_already_passed` from the one call site it
> is handed; `call_sites_reading_field` is a count across the whole graph and
> `field_passed_as_literal` is not recorded by the indexer at all. Both stay unestablished, and
> the rows that need them decline rather than guess. Tier 0 is therefore unreachable through the
> default, and the two mechanical rows are the entire tier-0 surface.

Rows 3 and 4 are the entire tier-0 surface. Both decline. So every finding that could have been
patched deterministically reaches a model instead.

**This task does not promise to fix all of it.** One of the two missing facts needs the indexer,
which another task owns. Your job is to close what is closeable inside your files, and to
establish precisely — with evidence, not estimation — what the remainder costs and who must do
it. A clear, measured statement of the blocker is a real deliverable here, not a consolation.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-27-sync-routing-matrix.md` — the table, rows 3 through 6, the
  section "Why a decision table rather than an `if` chain", and all of "What is built".
- `src/sync/remediate/tiered.py` — `routing_facts`, `_facts_for`, `tier_for`, and their
  docstrings, which already explain what the cascade can and cannot see.
- `src/sync/route/matrix.py` — the nine rows and the `RoutingFacts` they read.
- `scripts/dead_links_baseline.txt`, including its header. Two entries there are yours:
  `src/sync/route/templates.py:omit_property_at` and `src/sync/route/matrix.py:matching_rows`.

## Files you own

- Modify: `src/sync/remediate/tiered.py`
- Modify: `src/sync/remediate/property_omit.py`
- Modify: `src/sync/route/templates.py`
- Modify: `src/sync/route/matrix.py`
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_tier_zero_reach.py`
- Modify: existing tests in `tests/` only where your change breaks them

**Explicitly forbidden, each owned by a live task:** `src/sync/index/`, `src/sync/graph/`,
`src/sync/core/`, `src/sync/detect/`, `src/sync/signals/`, `src/sync/telemetry/`,
`src/sync/mcp/`, `src/sync/benchmark/`, `src/sync/cli.py`, `src/sync/verify/`, and
`docs/superpowers/specs/`.

`call_sites_reading_field` is a count across the whole graph, and `field_passed_as_literal` needs
the indexer. **Both live behind forbidden files.** Do not reach into them. If establishing a fact
requires one, that is a finding to report, not an edit to make.

## What to do

**First, establish the truth rather than trusting the spec.** The quoted passage is a claim about
code. Check it. Which facts can `routing_facts` establish today, from what it is actually handed?
Which cannot, and what would each need? Report what you find even where it contradicts the
quotation — a spec sentence has been wrong before on this exact subject, twice.

**Then close what is closeable.** Some of the gap may be reachable from what the cascade already
holds. Where a fact can be established honestly from data in hand, establish it. Where it cannot,
**leave the row declining.** The table is default-deny for a stated reason:

> The fall-through direction matters: an unrecognised change routed to an agent costs money,
> while an unrecognised change routed to a codemod corrupts code.

Guessing a fact to make a row fire converts a cost problem into a correctness problem. Do not.

**Wire `omit_property_at`.** It is a span primitive in `src/sync/route/templates.py` with no
caller outside its tests, and `src/sync/remediate/property_omit.py` is the remediator whose job
it plausibly is. Check whether that is genuinely its caller before wiring it — if the two do not
actually fit, say so and leave it, because forcing a call site that does not belong is worse than
a baselined dead link.

**Decide `matching_rows` honestly.** It exists so the overlap test can assert no two rows
contradict, which the spec's Verification section requires. A symbol that legitimately exists for
a test is not a dead link — but it must be marked as such deliberately rather than sitting in a
baseline that implies someone will one day wire it. Use the lint's opt-out marker with a reason
if that is what it is, and delete the baseline line.

## The baseline rule

Wiring a symbol makes its baseline entry stale, and `scripts/lint_dead_links.py` **fails** on an
entry that no longer describes anything. Delete the line in the same commit that wires the
symbol. You may only delete. Do not add lines — a new unreachable symbol means you built
something with no caller.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement. A test that has never failed has never been shown to test anything.

- **A finding that should reach tier 0 does.** For whichever row you make reachable, drive it
  through the cascade and assert the deterministic remediator handles it and the agent is never
  consulted. Prove it fails first — today it should route to the agent.
- **A finding whose fact cannot be established still declines.** Assert the row declines rather
  than guessing. This is the test that stops the previous one from being satisfied by a
  loosened predicate.
- **The overlap property still holds.** Whatever you do to `matching_rows`, the assertion it
  supports must still run and must still be able to fail.
- **`omit_property_at`, if you wire it, is asserted through its caller**, not called directly.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

The suite is currently 1187 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: which facts `routing_facts` can and cannot establish and how you verified each, which
rows you made reachable and which still decline, what the remaining blockers are and which
forbidden file each lives behind, what you decided about `matching_rows` and why, and the four
gate results.

</details>

---

## M3-W40: build FeedCache, the consumer that makes the signed feed worth signing

`task_87987e9d13ef` · created `2026-07-28 23:37:15` · status **failed**

<details><summary>Brief</summary>

M3-W40: build FeedCache, the consumer that makes the signed feed worth signing

## Why this task exists

`docs/superpowers/specs/2026-07-26-sync-public-change-feed.md` records its own state precisely:

> **Status:** Built, unpublished. `src/sync/signals/feed/publisher.py` renders and signs the
> array; `src/sync/signals/feed/consumer.py` verifies before parsing, with `FeedSignatureError`
> and `FeedFormatError` keeping the two failures apart. What does not exist is everything
> operational — no keypair, no committed public key, no hosting, no `FeedCache`.

`scripts/dead_links_baseline.txt` confirms the consequence with evidence: `render_feed`,
`sign_feed`, `public_key_bytes` and `verify_and_parse` are all reachable from nothing. A feed
that is rendered by nobody and verified by nobody is cryptography with no security property.

`FeedCache` is the piece that turns those four functions into a path. It is specified in
`2026-07-25-sync-mcp-graph-surface.md` Task 4 and extended by the feed spec:

```python
def store(self, vendor_id: str, payload: bytes, signature: bytes) -> FeedSnapshot:
    if not verify(payload, signature, PUBLISHER_PUBLIC_KEY):
        raise ValueError(f"feed signature for {vendor_id} does not verify")
    changes = _parse(payload)
    ...
```

Hosting and the production keypair are operational and stay out of scope. The consumer is not.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full. The import-boundary rule matters here.
- `docs/superpowers/specs/2026-07-26-sync-public-change-feed.md` — all of it, especially
  "Integrity", "What it is", and the Verification section.
- `src/sync/signals/feed/consumer.py` and `publisher.py`. Read both fully before designing —
  `verify_and_parse` already composes verification and parsing in the required order, and the
  two error types already keep authenticity and validity apart. Do not reimplement any of it.
- `src/sync/forge/webhook.py` — its `verify_signature` docstring explains why a verifier raises
  rather than returning a boolean, and the same argument binds you.
- `scripts/dead_links_baseline.txt`, including its header.

## Files you own

- Create: `src/sync/signals/feed/cache.py`
- Modify: `src/sync/signals/feed/__init__.py`
- Create: `src/sync/core/keys.py`
- Modify: `src/sync/core/__init__.py`
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_feed_cache.py`
- Create: `tests/fixtures/feed/` and the fixtures inside it

**Explicitly forbidden, each owned by a live task:** `src/sync/core/protocols.py`,
`src/sync/detect/`, `src/sync/index/`, `src/sync/graph/schema.sql`, `src/sync/remediate/`,
`src/sync/route/`, `src/sync/benchmark/`, `src/sync/cli.py`, `src/sync/mcp/`, and
`docs/superpowers/specs/`.

Do not modify `consumer.py` or `publisher.py`. They are correct; you are giving them a caller.

## The import boundary, which decides where the key lives

`CLAUDE.md`: *"`sync.core` imports nothing from any sibling package. Not `sync.graph`, not
`sync.signals`, not anything."* `tests/test_import_boundary.py` enforces it and it is not
advisory.

The feed spec says the public key is *"committed in the `sync.core` package and rotatable only
through a release."* That works only if the key is inert data. `src/sync/core/keys.py` must hold
raw key bytes and nothing else — no `cryptography` import, no verification helper, no
`Ed25519PublicKey` object. Parsing the bytes into a key belongs to `sync.signals.feed`, which
already has `load_public_key` for it.

Run the boundary test before you commit. It has caught this class of mistake before.

## What to build

A cache that holds fetched feed payloads per vendor and answers questions about them without
refetching. Three properties are not negotiable.

**Verification runs before parsing, always.** From the spec's Verification section:

> **A tampered payload is rejected.** Flip one byte in a fixture feed, confirm `FeedCache.store()`
> raises before any `VendorChange` is constructed from it — signature verification must run
> before parsing, not after.

**Both gates are required, in order.** A signature proves origin, not correctness. `CLAUDE.md`
says it directly: *"A validly signed feed carrying a malformed `VendorChange` fails at parse,
before any row is built from it."* Signed-and-invalid and unsigned-and-valid are different
failures and must stay distinguishable — the two error types already exist for this.

**The digest and the signature are both kept.** The spec: *"The existing SHA-256 digest stays as
a corruption check; the signature is the authenticity check, and both are required — corruption
and forgery are different failure modes and one check does not stand in for the other."*

Also carry `feed_fetched_at`, which the graph-surface design already reports, so a stale cached
feed degrades legibly rather than silently.

## The generated keypair

Generate a keypair for **development fixtures only** and commit the public key to
`src/sync/core/keys.py`. Say clearly in that module's docstring that it is a development key,
that the production key is generated operationally and is not in this repository, and that a
release is the only way to rotate it.

**Never commit a private key.** Not in `src/`, not in `tests/`, not in a fixture. Tests that need
to sign generate a throwaway key at runtime; the committed artefacts are the public key and
signed payloads. `CLAUDE.md`: *"We never hold customer secrets. That one is unqualified."* The
same discipline applies to our own.

## The baseline rule

Wiring a symbol makes its baseline entry stale, and `scripts/lint_dead_links.py` **fails** on an
entry that no longer describes anything. Delete each line in the same commit that wires it. You
may only delete. If your change leaves something new unreachable, wire it or do not build it.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement.

- **A flipped byte raises before any `VendorChange` exists.** Assert on the ordering, not just on
  the exception — a test that only checks "it raised" passes an implementation that parses first
  and verifies second.
- **A validly signed, schema-invalid payload still fails**, with the parse error, not the
  signature error.
- **A bare JSON array is accepted and a top-level object is rejected.** The spec is explicit that
  the array is the whole contract and never gains a wrapper.
- **A regenerated feed for a vendor with zero new changes is byte-identical** to the previous
  publish, so a cached copy is never invalidated by a no-op run. This exercises `render_feed`
  and is the reason canonical ordering exists.
- **No private key is committed.** Assert no fixture or source file under your ownership contains
  a private key header. State in the test what it protects.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

Feed payloads are bytes, not text. `CLAUDE.md`: *"When handling bytes that are not text, use
`read_bytes`/`write_bytes` and do not decode at all."* Signature verification over a
locale-decoded payload is a bug that only appears off ASCII.

The suite is currently 1218 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: how you assert verification precedes parsing rather than merely occurring, where the
public key lives and how you confirmed the import boundary still holds, which baseline lines you
deleted, and the four gate results.

</details>

---

## M3-W41: let a second vendor actually run, by making vendor selection data

`task_d9846de2208e` · created `2026-07-28 23:56:06` · status **completed**

### Result

{"completedBy":"term_26b15093-5760-4bbb-a865-38b2be53aee8","filesModified":["src/sync/cli.py","src/sync/signals/registry.py","src/sync/signals/__init__.py","scripts/dead_links_baseline.txt","tests/test_vendor_registry.py","tests/test_cli.py","tests/test_cli_wiring.py"],"completedAt":"2026-07-29T00:17:48.308Z"}

<details><summary>Brief</summary>

M3-W41: let a second vendor actually run, by making vendor selection data

## Why this task exists

`CLAUDE.md` states the plugin story as a non-negotiable:

> **Vendor-specific knowledge lives in adapters, never in core.** Stripe's URL conventions, its
> `operationId` scheme, its SDK naming — all of it belongs to `sync.signals.stripe`. The moment
> core knows a vendor's name, the plugin story is dead.

A second vendor adapter now exists. `src/sync/signals/twilio/adapter.py` implements both halves
of `VendorAdapter`, with tests, built specifically to prove the interface generalises past
Stripe. And `scripts/dead_links_baseline.txt` lists `TwilioAdapter` as reachable from nothing.

The reason is at the entry point. `src/sync/cli.py:580` and `:746` both construct
`StripeAdapter` directly, and line 44 imports it by name. There is no path by which a run uses
any other vendor, so the generality the adapter proves is unreachable — the claim holds in the
type system and fails in the product.

This is the fourth instance of the same defect and the most consequential, because what is
unreachable here is not a feature but the architectural claim the project rests on.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-27-sync-adapter-targets.md` — which vendors are viable targets
  and why, including the ones recorded as unresolved.
- `src/sync/signals/twilio/adapter.py` and `src/sync/signals/stripe/adapter.py`. Read both
  together: what they share is the interface, what differs is what must not leak into `cli.py`.
- `src/sync/core/protocols.py`, for the `VendorAdapter` protocol itself.
- `src/sync/cli.py`, especially lines 44, 580 and 746.
- `scripts/dead_links_baseline.txt`, including its header. Its rules bind you.

## Files you own

- Modify: `src/sync/cli.py`
- Create: `src/sync/signals/registry.py`
- Modify: `src/sync/signals/__init__.py`
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_vendor_registry.py`
- Modify: `tests/test_cli.py` — only to update assertions your change breaks

**Forbidden:** `src/sync/signals/feed/` and `src/sync/core/keys.py` (a live task owns both),
`src/sync/verify/` (a live task owns it), `src/sync/core/protocols.py`, `src/sync/graph/`,
`src/sync/mcp/`, `src/sync/index/`, `src/sync/detect/`, and `docs/superpowers/specs/`.

You may read `src/sync/signals/stripe/` and `src/sync/signals/twilio/` freely. Change them only
if a genuine interface defect blocks you — and if one does, report it, because a divergence
between two adapters is more valuable as a finding than as a quiet fix.

## What to build

A registry that maps a vendor id to the adapter that serves it, and a `cli.py` that selects
through it rather than naming a class.

The test of whether you have done this correctly is simple and worth stating up front: **after
your change, `grep -n "Stripe" src/sync/cli.py` should return no line that constructs or imports
a Stripe class.** Prose mentioning Stripe in a docstring is fine. An import of `StripeAdapter`
is the defect.

Two things to be careful about, both of which will tempt you into re-hardcoding:

**Stripe-shaped arguments.** `StripeAdapter` takes `spec_dir` and `symbol_map_path`. Twilio's
may not take the same things. Do not solve this by giving the registry a union of every
adapter's parameters — that is the vendor knowledge you just removed, moved one file over.
Whatever the registry hands an adapter must be vendor-neutral, and anything vendor-specific
belongs inside the adapter or its own configuration.

**The error path.** An unknown vendor id must fail with a message naming what is available. It
must not fall back to Stripe. A silent default is how "we support many vendors" becomes "we
support one and lie about it" — and `CLAUDE.md` warns against exactly this shape elsewhere:
`deps.py` refuses to substitute one package manager for another, because a different manager
resolves a different tree.

**Do not add a vendor.** No new adapter, no third vendor. Two is enough to prove selection is
data, and building a third would hide whether the second actually works.

## The baseline rule

Wiring a symbol makes its baseline entry stale, and `scripts/lint_dead_links.py` **fails** on an
entry that no longer describes anything. Delete each line in the same commit that wires it. You
may only delete. If your change leaves something new unreachable, wire it or do not build it.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement.

- **A Twilio run reaches `TwilioAdapter`.** Drive it from the production entry point, not by
  constructing the adapter — constructing it yourself re-creates the exact situation this task
  fixes. Prove this fails first; today there is no path.
- **A Stripe run still reaches `StripeAdapter`.** The regression that matters. Without it, a
  registry that resolves everything to Twilio passes the first test.
- **An unknown vendor id fails, naming what is available**, and does not silently become Stripe.
- **`cli.py` imports no vendor adapter class.** Assert it, because this is the property the whole
  task exists to establish and it is the one a later change will quietly undo. If you assert it
  by reading source text, say so in the test — `tests/test_cli.py` already has proxy assertions
  of that kind and two have broken on legitimate changes during this build.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one. It matters more than usual here: you are changing the import
graph at the point the boundary rule is about.

The suite is currently 1259 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: what the registry hands an adapter and why that is vendor-neutral, what
`grep -n "Stripe" src/sync/cli.py` returns after your change, any interface divergence you found
between the two adapters, which baseline lines you deleted, and the four gate results.

</details>

---

## M3-W42: execute the patched call path against the mock, and make replay able...

`task_902f214c5608` · created `2026-07-28 23:56:07` · status **completed**

### Result

{"completedBy":"term_b64d2f71-f51d-4c54-a60b-36cc381b4fdb","filesModified":["src/sync/verify/replay.py","src/sync/verify/__init__.py","scripts/dead_links_baseline.txt","tests/test_replay.py","tests/fixtures/replay/"],"completedAt":"2026-07-29T00:10:09.732Z"}

<details><summary>Brief</summary>

M3-W42: execute the patched call path against the mock, and make replay able to fail

## Why this task exists

`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` specifies a three-step replay
verification tier. Step 1 exists: `src/sync/verify/mock_response.py` synthesizes a mock response
from the new specification and the observed baseline, with observation outranking the spec. It is
in `scripts/dead_links_baseline.txt` because nothing consumes it.

You are building steps 2 and 3:

> 2. Execute the patched call path against that mock in the credential-free sandbox the threat
>    model already mandates. No network, no secrets, no vendor calls, no live side effects —
>    replaying a real charge is not legally an option, so mock-first is forced here, not chosen.
> 3. Assert the patched code consumes the response without error, and that fields the code reads
>    (`response_fields_read`) are satisfied by the mocked shape.

The gap it closes is real and the spec states it plainly:

> The quieter problem is that a green CI run proves little when no test exercises the patched
> call. Most customers have no test covering their Stripe integration; a passing suite that never
> runs the patched path is weak evidence presented as strong.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full — especially the two qualifications it
  makes about executing customer code, which are the most important paragraphs for this task.
- `docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` — "The replay verification
  tier" and the Verification section, in full.
- `src/sync/verify/mock_response.py` — what you consume, and its module docstring.
- `src/sync/index/typescript.py`, specifically `static_verify` and how it prepares a clone. The
  sandbox discipline you need already exists there; read it before inventing your own.
- `scripts/dead_links_baseline.txt`, including its header.

## Files you own

- Create: `src/sync/verify/replay.py`
- Modify: `src/sync/verify/__init__.py`
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_replay.py`
- Create: `tests/fixtures/replay/` and the fixtures inside it

**Forbidden:** `src/sync/cli.py` and `src/sync/signals/` (a live task owns both),
`src/sync/signals/feed/` and `src/sync/core/keys.py` (another live task), `src/sync/index/`,
`src/sync/graph/`, `src/sync/core/`, `src/sync/mcp/`, `src/sync/remediate/`,
`src/sync/detect/`, and `docs/superpowers/specs/`.

Read `src/sync/index/typescript.py` as much as you need. Do not edit it. If replay genuinely
requires a change there, report that — it is a finding about where the sandbox boundary sits, and
it is worth more than a quiet edit across an ownership line.

## The execution boundary, which is the part to get right

`CLAUDE.md` is careful and qualified here, and you must be too:

> **"We never execute customer code" is the intent, not yet the invariant.** `run_tsc` prefers
> the clone's own `node_modules/.bin/tsc`, resolved through the customer's `.npmrc`, and the
> patch agent holds `Bash` inside the clone. Dependency installs pass `--ignore-scripts`, so no
> lifecycle script runs, and Sync never runs the customer's application — but it does execute
> their toolchain.

Replay changes that, and the spec is explicit that this is acceptable only because the surface
already exists:

> **Boundary:** the replay tier verifies the *call path*, not the whole application. It executes
> customer code only inside the sandbox the threat model requires for `tsc` already — this adds
> no new execution surface, only new use of one that must exist anyway.

So the rules are hard:

- **No network.** Not to the vendor, not anywhere. The mock is the only response.
- **No credentials, ever.** `CLAUDE.md`: *"We never hold customer secrets. That one is
  unqualified."* If a call path needs an API key to run, it gets a synthetic one that cannot
  authenticate anywhere, and the test asserts nothing real is read from the environment.
- **The call path, not the application.** Do not start the customer's server, run their test
  suite, or execute an entry point. Execute the patched call and what it directly needs.
- **No lifecycle scripts.** Follow the existing `--ignore-scripts` discipline.

If you cannot satisfy one of these, **stop and report it.** A replay tier that quietly weakens
the sandbox is worse than no replay tier, because the verification gate is the thing customers
are trusting.

## What "able to fail" means here

The spec's Verification section names the one property that decides whether this is worth
anything:

> **The replay tier is proven able to fail**: a patch that mishandles the new shape must fail
> replay before the tier is trusted to pass anything.

This is the whole task. A replay that passes everything is not a verification tier, it is a
delay. `CLAUDE.md` says the same thing generally — *"A test that cannot fail is worse than no
test — it manufactures confidence"* — and it applies with full force to a gate whose output goes
in a pull request body a human will read as evidence.

So build the failing case first, before the passing one. Write a fixture patch that mishandles
the new shape, watch replay reject it, and only then make a correct patch pass.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement.

- **A patch that mishandles the new shape fails replay.** The first test you write. Prove it goes
  red against a stub that passes everything.
- **A patch that handles it passes.** Second, so the first cannot be satisfied by a tier that
  rejects everything.
- **A field in `response_fields_read` that the mock does not satisfy fails**, naming the field.
  This is step 3 and it is distinct from "the code threw" — code can consume a response without
  error while reading a field that is now absent.
- **No network is reachable during replay.** Assert it rather than documenting it.
- **No real credential is read.** Assert the environment is not consulted for one.

Local toolchain access is fine — `CLAUDE.md` permits the Postgres container and `npx` fetching a
compiler. A vendor API or a model API is not, and the mock exists precisely so neither is needed.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## What is not yours

Every replay run is also a shape-store writer (`source = 'replay'`), which is how the baseline
accumulates before any customer installs anything. **The store is owned elsewhere.** Shape the
return value so a caller can write those rows in one step, note it in the module docstring, and
do not write them yourself.

Wiring replay into the verification cascade is also not yours — `cli.py` belongs to a live task.
Expect to leave your entry point baselined, with a comment saying what has to exist before the
line can be deleted.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

You are shelling out, so `subprocess` is your sharpest hazard. `CLAUDE.md`: a missing
`encoding="utf-8"` on `subprocess.run(..., text=True)` raises on the reader thread, never
propagates, returns `stdout` as `None`, and blows up somewhere unrelated. One accented identifier
in a customer's project is enough. Pass it explicitly on every call.

The suite is currently 1259 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: how you proved replay can fail before you made anything pass, exactly what executes and
what does not, how you established that no network and no credential are reachable, what you left
baselined and why, and the four gate results.

</details>

---

## M3-W43: put replay between the typechecker and CI, where the spec says it bel...

`task_782715d050f1` · created `2026-07-29 00:16:07` · status **completed**

### Result

{"completedBy":"term_b64d2f71-f51d-4c54-a60b-36cc381b4fdb","filesModified":["src/sync/remediate/graph.py","src/sync/remediate/nodes.py","src/sync/remediate/state.py","scripts/dead_links_baseline.txt","tests/test_replay_stage.py"],"completedAt":"2026-07-29T00:26:05.593Z"}

<details><summary>Brief</summary>

M3-W43: put replay between the typechecker and CI, where the spec says it belongs

## Why this task exists

The replay verification tier now exists. `src/sync/verify/replay.py` executes a patched call
path against a synthesized mock in a sandbox with no network, no credentials, no writes and no
child processes, and it rejects a patch that mishandles the new shape. It is in
`scripts/dead_links_baseline.txt` as `replay_from_specification`, because nothing calls it.

`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` says exactly where it goes:

> This sits between `tsc` and customer CI: stronger than typechecking (it exercises runtime
> behavior against the new shape), cheaper and earlier than CI, and it produces evidence for the
> PR body that a reviewer can read — "the patched path was executed against the new response
> shape and consumed it cleanly."

And why the gap matters:

> The quieter problem is that a green CI run proves little when no test exercises the patched
> call. Most customers have no test covering their Stripe integration; a passing suite that never
> runs the patched path is weak evidence presented as strong.

A verification tier nothing invokes verifies nothing. That is the fifth instance of this pattern
in this repository, and the lint exists so it is the last found by hand.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full. **"Nothing reaches a pull request
  unverified"** is the rule this task extends, and the two honest qualifications it makes about
  executing customer code bind you as they bound the tier itself.
- `docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` — "The replay verification
  tier" in full.
- `src/sync/verify/replay.py` — its module docstring states the four enforcement properties and
  what it returns. Read it before designing; it already tells you what a caller must supply and
  what it deliberately does not do.
- `src/sync/remediate/graph.py` and `src/sync/remediate/nodes.py` — the verification stage,
  `route_after_static`, and how `static_verify` sets `verify_ok` deliberately rather than
  inferring it from whether `diagnostics` is non-empty. Your routing predicate follows that
  discipline.
- `scripts/dead_links_baseline.txt`, including its header.

## Files you own

- Modify: `src/sync/remediate/graph.py`
- Modify: `src/sync/remediate/nodes.py`
- Modify: `src/sync/remediate/state.py`
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_replay_stage.py`
- Modify: existing tests in `tests/` only where your change breaks them

**Forbidden, each owned by a live task:** `src/sync/cli.py`, `src/sync/signals/`,
`src/sync/index/`, `src/sync/core/`, `src/sync/graph/schema.sql`, and
`docs/superpowers/specs/`. Also do not edit `src/sync/verify/replay.py` — it is finished and you
are giving it a caller.

`src/sync/cli.py` being forbidden is the constraint that shapes this task. If the stage cannot be
reached without a `cli.py` edit, **say so and leave your entry point baselined with a comment
naming what has to exist** — do not reach across the line, and do not pretend the stage is live
when it is not.

## What to build

A replay stage in the remediation graph, after `static_verify` and before whatever hands the
branch to CI.

Four things decide whether this is right.

**Replay runs only on a patch that already typechecks.** Running it on a patch `tsc` rejected
spends a sandboxed execution to discover something the compiler said for free. Order the stage so
a failed static verification never reaches it.

**A replay failure is a verification failure, not an abandonment.** It means this patch is wrong,
which is what the retry loop exists for — the same distinction `route_after_static` already
draws. Feed it back the way a `tsc` failure is fed back.

**Replay cannot always run, and not running is not passing.** The spec's own scope says the tier
verifies the call path, not the application; a call path replay cannot execute — no resolvable
entry, an unsupported language, a missing file — must be recorded as *not verified by replay*,
distinct from *verified and passed*. Collapsing those two is how a gate silently stops gating,
and `CLAUDE.md` is unambiguous that a path skipping the gate is a bug in the approach rather than
a shortcut.

**The evidence is the point.** The spec promises a reviewer a sentence they can read. Whatever
the stage records must be enough to produce it, and must not overclaim: replay proves the patched
path consumed the mocked shape, not that the application works.

## The shapes replay offers

Every replay run is also a shape-store writer (`source = 'replay'`), which is how the observed
baseline accumulates before any customer installs anything. `replay.py` deliberately *offers*
shapes rather than writing them, and its docstring says why — they describe the mock the code was
exercised against, not traffic a vendor sent.

Writing them touches the store, which is not yours. **Carry them on `RunState` and report that
the write is unwired.** If they reach the store looking like observed traffic, the drift detector
compares reality against a mock Sync itself built, and that is worse than an empty baseline.

## The baseline rule

Wiring a symbol makes its baseline entry stale, and `scripts/lint_dead_links.py` **fails** on an
entry that no longer describes anything. Delete each line in the same commit that wires it. You
may only delete.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement.

- **A patch that mishandles the new shape does not reach CI.** Assert on the node sequence, the
  way `tests/test_no_patch_route.py` does — asserting the absence of a pull request is a weaker
  test that a stage which ran and did nothing would pass.
- **A patch that handles it does reach CI.** Without this, a stage that blocks everything passes
  the first test.
- **A patch that fails `tsc` never reaches replay.** Assert the ordering.
- **Replay declining to run is distinguishable from replay passing**, in whatever the stage
  records. This is the test that stops the gate from silently opening.
- **The offered shapes are carried and not written.** Assert nothing reaches the store.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

The suite is currently 1274 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: the node sequence your tests assert, how "replay could not run" is kept distinct from
"replay passed", whether the stage is reachable without a `cli.py` edit and what remains if not,
what you did with the offered shapes, and the four gate results.

</details>

---

## M3-W44: let a vendor be added by configuration, through the generated-SDK man...

`task_a82e10250724` · created `2026-07-29 00:25:25` · status **completed**

### Result

{"completedBy":"term_26b15093-5760-4bbb-a865-38b2be53aee8","filesModified":["src/sync/signals/registry.py","src/sync/signals/__init__.py","generated-vendors.yaml","scripts/dead_links_baseline.txt","tests/test_generated_registry.py","tests/fixtures/manifests/"],"completedAt":"2026-07-29T00:40:37.504Z"}

<details><summary>Brief</summary>

M3-W44: let a vendor be added by configuration, through the generated-SDK manifest

## Why this task exists

`src/sync/signals/generated/` holds a complete, tested path that nothing calls.
`scripts/dead_links_baseline.txt` lists three of its symbols: `GeneratedSpecAdapter`,
`parse_manifest`, and `SpecSource.has_cheap_change_trigger`.

What is unreachable is the project's coverage argument. From `manifest.py`'s own docstring:

> supporting a generator costs a day and yields every vendor using it, while supporting a vendor
> under a known generator costs a configuration line. Coverage stops scaling with vendor count
> and starts scaling with generator count, and there are few generators.

And the economics, from `adapter.py`:

> A Stainless manifest publishes `openapi_spec_hash`. Comparing that string across two commits of
> the SDK repository is free -- it is a text file in a public repository -- and it answers "did
> the specification move" without downloading anything. Only a vendor whose hash actually moved
> pays for two spec fetches and an oasdiff run.

Until this week there was nowhere to wire it: `cli.py` named `StripeAdapter` directly. That is
fixed — `src/sync/signals/registry.py` now resolves a vendor id to an adapter, and `cli.py` names
no vendor class. The registry is the seam this path was waiting for.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full. **"Vendor-specific knowledge lives in
  adapters, never in core"** is the rule this task extends rather than bends.
- `docs/superpowers/specs/2026-07-27-sync-adapter-targets.md` — the whole argument, including the
  targets it records as **unresolved**. Do not treat an unresolved target as viable because it
  would be convenient.
- `src/sync/signals/generated/manifest.py` and `adapter.py`, both in full. They are finished. You
  are giving them a caller, not redesigning them.
- `src/sync/signals/registry.py` — how a vendor id resolves today, what the registry hands an
  adapter, and why that had to stay vendor-neutral.
- `scripts/dead_links_baseline.txt`, including its header.

## Files you own

- Modify: `src/sync/signals/registry.py`
- Modify: `src/sync/signals/generated/adapter.py` and `manifest.py` — **only** if a genuine
  interface defect blocks wiring. Prefer reporting one to fixing it quietly.
- Modify: `src/sync/signals/__init__.py`
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_generated_registry.py`
- Create: `tests/fixtures/manifests/` and the fixtures inside it

**Forbidden, each owned by a live task or out of scope:** `src/sync/signals/feed/` and
`src/sync/core/keys.py`, `src/sync/remediate/`, `src/sync/verify/`, `src/sync/signals/stripe/`,
`src/sync/signals/twilio/`, `src/sync/index/`, `src/sync/core/`, `src/sync/graph/`,
`src/sync/mcp/`, and `docs/superpowers/specs/`.

**`src/sync/cli.py` is not yours.** Another task may need it. If the registry cannot reach the
generated path without a `cli.py` edit, say so and leave the entry point baselined with a comment
naming what has to exist. Do not cross the line.

## What to build

Registration of a vendor whose adapter is `GeneratedSpecAdapter`, configured rather than coded.

The test of whether this is right: **adding a vendor that uses a supported generator should be a
configuration entry, not a new module.** If your design requires a Python file per vendor, you
have rebuilt the thing the generated path exists to replace.

Four constraints.

**No vendor name in shared code.** The registry stays vendor-neutral, as it was built to be. A
configured vendor supplies its own manifest location and repository; the registry supplies
nothing vendor-specific.

**The cheap trigger has to actually be cheap.** `has_cheap_change_trigger` exists so a vendor
whose spec hash has not moved costs nothing. Wire it so that is true — if your path fetches specs
before consulting the hash, the economics that justify the whole approach are gone, and this task
achieved nothing but reachability.

**No network in tests.** `CLAUDE.md`: *"No test calls a vendor API or a model API. Fixtures are
committed."* `manifest.py` is deliberately pure and says so — *"Network access belongs to the
caller, which keeps the parsing testable against committed fixtures."* Keep that separation: the
fetch is injectable, and your tests drive committed manifest fixtures.

**An unresolved target stays unresolved.** The adapter-targets spec records vendors whose manifest
or spec repository does not exist — it names `sendgrid/sendgrid-oai` and `workos/workos-openapi`
among them. Do not configure a vendor whose source you have not confirmed. A configuration entry
pointing at a repository that does not exist is a runtime failure wearing the costume of support.

## The baseline rule

Wiring a symbol makes its baseline entry stale, and `scripts/lint_dead_links.py` **fails** on an
entry that no longer describes anything. Delete each line in the same commit that wires it. You
may only delete. If your change leaves something new unreachable, wire it or do not build it.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement. A test that has never failed has never been shown to test anything.

- **A configured generated-SDK vendor resolves to `GeneratedSpecAdapter`** through the registry,
  not by construction in the test. Prove it fails first; today there is no path.
- **The hand-written adapters still resolve to themselves.** The regression that matters — without
  it, a registry resolving everything to the generated adapter passes the first test.
- **An unchanged spec hash fetches nothing.** Assert the fetch is never called. This is the
  economic claim and it is the one most likely to be quietly lost.
- **A changed hash does fetch.** So the previous test cannot be satisfied by a path that never
  fetches at all.
- **A malformed or absent manifest fails naming the path**, rather than resolving to a default.
  `registry.py` already establishes that discipline for unknown vendors; match it.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

Manifests are YAML read from disk. Pass `encoding="utf-8"` explicitly on every read —
`scripts/lint_encoding.py` will fail you otherwise, and on this machine the default is cp1252, so
a vendor manifest with one accented character would fail only in production.

The suite is currently 1284 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: what a new vendor under a supported generator now costs to add, how you assert the
unchanged-hash path fetches nothing, whether the registry needed anything vendor-specific and how
you avoided it, which baseline lines you deleted, and the four gate results.

</details>

---

## M3-W45: let the deprecation signal say how urgent it is, and emit the paramet...

`task_f1714b18e494` · created `2026-07-29 00:35:55` · status **completed**

### Result

{"completedBy":"term_b64d2f71-f51d-4c54-a60b-36cc381b4fdb","filesModified":["src/sync/signals/deprecations/catalogue.py","src/sync/signals/deprecations/adapter.py","src/sync/cli.py","scripts/dead_links_baseline.txt","tests/test_deprecation_urgency.py"],"completedAt":"2026-07-29T00:44:55.227Z"}

<details><summary>Brief</summary>

M3-W45: let the deprecation signal say how urgent it is, and emit the parameter changes it promised

## Why this task exists

Two symbols in `src/sync/signals/deprecations/` are complete, tested, and called by nothing.
`scripts/dead_links_baseline.txt` lists both. Each one is a capability the deprecation signal
already claims.

**`urgency` is not reaching any finding.** `catalogue.py:288` computes days until a model stops
working, and its docstring explains why the sign matters:

> Negative means the retirement date has passed: the vendor states that requests to a retired
> model fail, so this is an outage already in the code rather than a deadline approaching. That
> distinction is why the return is signed rather than clamped.

Nothing consults it. So a model that stopped working last month and a model retiring in eleven
months arrive at a reviewer looking identical, and the one distinction the vendor's own data
supports is computed and discarded.

**`parameters_to_vendor_changes` emits nothing because nobody calls it.** Its docstring records
that its own objection has already been retired:

> An earlier version of this module deliberately emitted none, on the grounds that a parameter
> joins against `CallSite.args_keys` rather than `operation_id`, so a change no detector could
> join would produce findings pointing at nothing. `ParameterDeprecationDetector` now performs
> that join, which retires the objection.

The detector that made it safe is wired. The function it made safe is not.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-28-sync-deprecation-signal.md` — the whole document, and note
  that the spec audit corrected its Status line in both directions, so read what it says now
  rather than what you expect it to say.
- `src/sync/signals/deprecations/catalogue.py`, `parameters.py` and `adapter.py`, in full.
- `src/sync/detect/parameter_deprecation.py` — the detector that performs the join.
- `src/sync/cli.py`, especially `_model_deprecations` and `_detector_suite`, which is where the
  deprecation signal reaches the pipeline today.
- `scripts/dead_links_baseline.txt`, including its header.

## Files you own

- Modify: `src/sync/signals/deprecations/catalogue.py`, `parameters.py`, `adapter.py`
- Modify: `src/sync/cli.py`
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_deprecation_urgency.py`
- Modify: existing tests in `tests/` only where your change breaks them

**Forbidden, each owned by a live task:** `src/sync/signals/feed/` and `src/sync/core/keys.py`,
`src/sync/signals/generated/` and `src/sync/signals/registry.py` and
`src/sync/signals/__init__.py`, `src/sync/index/`, `src/sync/core/models.py`,
`src/sync/core/protocols.py`, `src/sync/graph/schema.sql`, `src/sync/signals/stripe/`,
`src/sync/signals/twilio/`, and `docs/superpowers/specs/`.

`src/sync/core/models.py` being forbidden is the constraint most likely to bite. If carrying
urgency requires a new field on `Finding` or `VendorChange`, **stop and report that** rather than
editing across the line — and look first at whether `VendorChange.raw` already carries what you
need. `CLAUDE.md` keeps the raw vendor record for exactly this kind of question.

## What to build

**Urgency reaching the finding.** Whatever a reviewer or a router sees about a model deprecation
should distinguish "already failing" from "failing later", and should preserve the sign rather
than clamping it. Where that value lands is your judgement — but it must survive to somewhere a
consumer can act on, not stop at a local variable.

Be careful about one thing: urgency is computed against a date, and a date makes a test
non-deterministic if you let it. `urgency` already takes `today` as an argument for that reason.
Keep it injectable all the way up; do not reach for the system clock inside the pipeline.

**Parameter changes emitted.** Call `parameters_to_vendor_changes` where the parameter half of
the signal is assembled, so the deprecations the detector can join actually become
`VendorChange` rows.

Watch for the `from_version`/`to_version` argument. The model-retirement path already has a
comment about this — a version range is Stripe's notion and means nothing to a deprecation, which
happens on a date rather than across a release. Whatever you pass must be honest about that
rather than borrowing a range that does not apply.

## The baseline rule

Wiring a symbol makes its baseline entry stale, and `scripts/lint_dead_links.py` **fails** on an
entry that no longer describes anything. Delete each line in the same commit that wires it. You
may only delete. If your change leaves something new unreachable, wire it or do not build it.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement. A test that has never failed has never been shown to test anything.

- **An already-retired model is distinguishable from one retiring in a year**, at whatever
  consumer-visible point you chose. Prove it fails first — today they are identical there.
- **The sign survives.** Assert a passed retirement date stays negative rather than becoming zero
  or absent. This is the distinction the docstring says the signed return exists for.
- **A model that is not dying yields no urgency**, and that is not the same as urgency zero.
- **Urgency is computed against an injected date.** Assert the same input yields the same output
  on any day — a test that passes today and fails in a year is a test that will be deleted rather
  than fixed.
- **A parameter deprecation becomes a `VendorChange` through the production path**, not by
  calling `parameters_to_vendor_changes` in the test. Calling it directly re-creates exactly the
  situation this task fixes.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

The suite is currently 1292 passing. A test you did not write going red is a real signal — read
it before adjusting anything. `tests/test_cli.py` contains source-text proxy assertions that have
broken on legitimate changes three times during this build; if one breaks, weaken the literal,
preserve the property its name states, and say so.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: where urgency lands and why there, what you passed for the version range and why it is
honest, whether anything needed a `models.py` change you did not make, which baseline lines you
deleted, and the four gate results.

</details>

---

## M3-W46: run the whole pipeline in CI against a fixture repository, and write...

`task_7b58b40582c6` · created `2026-07-29 00:45:46` · status **completed**

### Result

{"completedBy":"term_26b15093-5760-4bbb-a865-38b2be53aee8","filesModified":["tests/test_pipeline_composes.py","tests/fixtures/pipeline/verified/tsconfig.json","tests/fixtures/pipeline/verified/src/summarise.ts","tests/fixtures/pipeline/rejected/tsconfig.json","tests/fixtures/pipeline/rejected/src/models.ts","tests/fixtures/pipeline/rejected/src/summarise.ts"],"completedAt":"2026-07-29T01:07:23.423Z"}

<details><summary>Brief</summary>

M3-W46: run the whole pipeline in CI against a fixture repository, and write real corpus rows

## Why this task exists

Every defect this build has hunted has the same shape. A component is complete, is tested, works
in isolation — and is unreachable from the entry point. It happened with
`GraphStore.set_merge_outcome`, `sync.route.matrix.route()`, `DeprecationAdapter`,
`ingest_payload`, the whole MCP graph surface, `TwilioAdapter`, and the replay tier.
`scripts/lint_dead_links.py` now catches the symbol-level version of it, and the baseline has
gone from 28 entries to 11 by wiring rather than by weakening.

A lint over symbols cannot catch the next size up: components that are each reachable and still
do not compose. Nothing in the default test run drives INDEX through SIGNAL, DETECT, LOCATE,
PATCH and verification in one pass. The one end-to-end test,
`tests/test_e2e_stripe.py::test_one_command_produces_one_green_pull_request`, opens a real pull
request against a real remote, so it is marked `@pytest.mark.e2e` and deselected by default — and
correctly so. That leaves the whole-pipeline path unexercised on every ordinary run.

There is a second thing this closes. `docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md`
says of the five quality axes:

> the table holds no rows, because no real pipeline run has produced one.

Three axes are computed, `sync benchmark` renders them, and every one reports null with a sample
size of zero. A run that goes through the real graph and writes real `migration_outcome` rows is
what turns that reporting surface from plumbing into a measurement.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` — the six rules, especially the
  grain of `migration_outcome` (one row is one *attempt*, not one finding) and idempotence.
- `docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` — "Gate tier B".
- `src/sync/remediate/graph.py`, `nodes.py`, and `corpus.py`. `corpus.py:186` is worth your
  attention specifically; see below.
- `src/sync/mcp/propose.py` — it already composes the node factories to run
  locate-prepare-patch-static_verify and stop, and it never accepts a `Forge`, which is the
  structural reason it cannot push. That boundary is the one you want.
- `tests/test_e2e_stripe.py`, to see what the marked test does and why yours must not do it.

## Files you own

- Create: `tests/test_pipeline_composes.py`
- Create: `tests/fixtures/pipeline/` and the fixtures inside it
- Modify: `.github/workflows/ci.yml`, only if the run needs a step it does not have

**Forbidden — everything under `src/`.** This task adds no production code. If the pipeline
cannot be driven end to end without a change under `src/`, that is the most valuable thing you
could find, and you must report it rather than make the change. Three other tasks own most of
`src/` right now.

Also forbidden: `docs/superpowers/specs/`, and `tests/test_e2e_stripe.py`.

## What to build

An integration test that runs the real remediation graph over a committed fixture repository and
asserts what it produced, running in the default suite with no network and no vendor API.

The boundary is not negotiable:

- **No pull request, no push, no remote.** Use the same structural guarantee `propose.py` relies
  on — a driver holding no `Forge` cannot push, open a pull request, or delete a branch. Do not
  substitute a mocked `Forge`; a mock proves the code calls what you told it to call.
- **No vendor API and no model API.** `CLAUDE.md` is unconditional. Fixtures are committed. If a
  stage needs a model call to proceed, that stage's boundary is where your test stops, and you
  say so.
- **Local toolchain is fine.** The Postgres container and `npx` fetching a compiler are both
  explicitly allowed, and the point of this test is partly that `tsc` really runs.

What to assert, in rough order of value:

- **A finding travels the whole way.** From an indexed call site and a vendor change through to a
  verified patch, in one pass through the real graph rather than through stages called by hand.
- **A `migration_outcome` row exists, and its grain is right.** One row per attempt. A test that
  counts findings by counting rows is the mistake the discipline spec names first; write the
  assertion so it would fail if the grain were wrong.
- **The recorded tier and row are the ones that actually fired**, not defaults. The routing
  matrix's Verification section asks for exactly this, and until now nothing has checked it
  outside a unit test.
- **`sync benchmark` computes a non-null axis over those rows.** This is the moment the benchmark
  stops being plumbing. Assert a real number with a real sample size, not a threshold — there is
  no pass mark and you must not invent one.
- **Re-running is idempotent.** The discipline spec requires every stage to converge on the same
  rows for the same input; `efcc19d` was this bug. Run it twice and assert the second run does
  not duplicate.

## One thing to look at while you are there

`src/sync/remediate/corpus.py:186` reaches the corpus writer through
`getattr(store, "record_migration_outcome", None)` and logs a warning when it is absent. That is
duck typing on the one write that the entire benchmark depends on: a rename would silently stop
recording, the warning would scroll past, and every axis would keep reporting null with nobody
able to tell that from "no runs yet".

Your test is the natural place to catch that, because it is the only thing that will exercise the
real writer. Assert the row is written rather than merely that the call did not raise. **Do not
fix `corpus.py`** — it is not yours. If you conclude the `getattr` is a real hazard, say so and I
will task it.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement — which here means building the fixture until the assertion is meaningful, not
loosening the assertion until it passes. If a stage will not compose, that is a finding; report
it rather than routing around it.

`tests/test_e2e_stripe.py` is deselected by `addopts`. Yours must **not** be marked `e2e`. If the
suite grows slower in a way you think is unacceptable, say so with the measured number rather
than quietly marking your test out of the default run — a test excluded from CI is a test that
will rot.

Use your own `SYNC_DSN` pointing at a database no other task is using. Truncate what you own
rather than assuming an empty database; several workers are running migrations in parallel.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

The suite is currently 1309 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: what the test drives and where it stops, the first real numbers `sync benchmark` produces
over the rows it writes, how long the test adds to the suite, anything that would not compose
without a change under `src/`, your verdict on the `corpus.py` `getattr`, and the four gate
results.

</details>

---

## M3-W47: link a parameter-deprecation finding to its vendor change, so it surv...

`task_82970c7176e0` · created `2026-07-29 00:48:49` · status **completed**

### Result

{"completedBy":"term_b64d2f71-f51d-4c54-a60b-36cc381b4fdb","filesModified":["src/sync/detect/parameter_deprecation.py","src/sync/cli.py","tests/test_parameter_deprecation_link.py","tests/test_parameter_detector.py"],"completedAt":"2026-07-29T00:57:31.683Z"}

<details><summary>Brief</summary>

M3-W47: link a parameter-deprecation finding to its vendor change, so it survives locate

## The defect, verified in the code

`src/sync/detect/parameter_deprecation.py:51` constructs a `Finding` with `detector`,
`call_site_id`, `severity` and `rationale` — and no `vendor_change_id`.

That field is optional at `src/sync/core/models.py:87` (`vendor_change_id: str | None = None`),
so nothing objects at construction. Then `src/sync/remediate/nodes.py:102` runs
`store.get_vendor_change(finding.vendor_change_id)` inside `make_locate`, which is wrapped in a
`try` that sets `fatal` and abandons.

So **every parameter-deprecation finding dies at `locate`**, before a remediator is ever asked.
The detector works, its tests pass, and nothing it produces can be repaired.

This became reachable-and-broken rather than merely dormant a few commits ago. `cli.py` now calls
`parameters_to_vendor_changes`, so the `VendorChange` rows exist in the store — and no finding
points at them. Two halves of one join, both built, not joined.

The remediators are already waiting. `ParameterOmitRemediator` and `ParameterRenameRemediator`
sit in the cascade at `src/sync/cli.py:126-127` and key on `kind == "deprecation/parameter"`.
Nothing reaches them.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-28-sync-deprecation-signal.md`.
- `src/sync/detect/parameter_deprecation.py` in full — especially the comment at line 39 about
  why it refuses to invent a `call_site_id`. The same principle governs what you are about to do
  with `vendor_change_id`.
- `src/sync/signals/deprecations/parameters.py`, particularly `parameters_to_vendor_changes` and
  what it puts in each row: `kind`, `operation_id`, `path_ptr`, `from_version`, `to_version`, and
  `raw`.
- `src/sync/cli.py` around line 459, where the parameter changes are built, and around 126 where
  the cascade is composed.
- `src/sync/remediate/nodes.py`, `make_locate`.

## Files you own

- Modify: `src/sync/detect/parameter_deprecation.py`
- Modify: `src/sync/cli.py`
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_parameter_deprecation_link.py`
- Modify: existing tests in `tests/` only where your change breaks them

**Forbidden, each owned by a live task or out of scope:** `src/sync/signals/feed/` and
`src/sync/core/keys.py`, `src/sync/core/models.py`, `src/sync/core/protocols.py`,
`src/sync/index/`, `src/sync/graph/schema.sql`, `src/sync/signals/stripe/`,
`src/sync/signals/twilio/`, `src/sync/remediate/`, `src/sync/verify/`, and
`docs/superpowers/specs/`. Do not add a test to `tests/test_pipeline_composes.py`; another task
is creating it.

`src/sync/core/models.py` being forbidden matters: if the link needs a new field, **stop and
report it**. It almost certainly does not — `vendor_change_id` already exists and is already
what `make_locate` reads.

## What to build

The detector must emit findings carrying the id of the `VendorChange` the deprecation produced.

**The join must be established, never guessed.** This is the constraint that decides the design,
and the module you are editing already states the principle for the other identifier: inventing a
`call_site_id` would produce "a finding nothing downstream could resolve back to a location."
Same here — a `vendor_change_id` that names the wrong row produces a confident patch against the
wrong change, which is the most expensive false positive this system can make.

So: whatever supplies the detector its deprecations must also supply, or make derivable, the
change each one became. If the correspondence cannot be established for a given deprecation, the
detector must **not** emit a finding pointing at a plausible row. Skip it, the way it already
skips a call site with no id, and make that skip visible rather than silent — a deprecation the
pipeline dropped is exactly the kind of thing that should be countable later.

Be careful about ordering. `parameters_to_vendor_changes` produces rows; the store assigns or
confirms their ids; the detector needs the id. If your design has the detector constructed before
the changes are stored, the id is not available yet and you will be tempted to reach for
something derivable-looking instead. Restructure the wiring rather than inventing a key.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement.

- **A parameter-deprecation finding survives `locate`.** Drive it through the real node, not by
  inspecting the `Finding`. Asserting the field is populated proves the field is populated;
  asserting `locate` returns a change proves the defect is fixed. Prove it fails first — today
  `locate` abandons.
- **It reaches a remediator that can act on it.** The cascade already holds both parameter
  remediators; assert one of them is asked. This is the whole point of the repair, and without it
  a finding that merely survives `locate` is still worth nothing.
- **The linked change is the right one.** Two deprecations for different parameters must not both
  point at the same row. Build the fixture so a wrong-but-plausible join is visibly wrong; a test
  with one deprecation in it cannot catch a mis-join.
- **An unestablishable link emits no finding**, rather than a finding pointing somewhere
  plausible. Prove this one is non-vacuous by deliberately breaking it.
- **The skip is observable.** Assert whatever you chose — a log, a counter, a returned reason —
  actually reports it.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

The suite is currently 1319 passing. A test you did not write going red is a real signal — read
it before adjusting anything. `tests/test_cli.py` holds source-text proxy assertions that have
broken on legitimate changes three times this build; if one breaks, weaken the literal, preserve
the property its name states, and say so.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: how the link is established and why it cannot name the wrong row, what happens to a
deprecation whose change cannot be identified and how that is observable, whether the wiring
order had to change, and the four gate results.

</details>

---

## M3-W48: index Python repositories, and report what cannot be verified instead...

`task_264def00e223` · created `2026-07-29 01:06:19` · status **completed**

### Result

{"completedBy":"term_b64d2f71-f51d-4c54-a60b-36cc381b4fdb","filesModified":["src/sync/cli.py","src/sync/index/python_lang.py","src/sync/remediate/nodes.py","src/sync/remediate/state.py","scripts/dead_links_baseline.txt","tests/test_python_repository.py"],"completedAt":"2026-07-29T03:30:01.757Z"}

<details><summary>Brief</summary>

M3-W48: index Python repositories, and report what cannot be verified instead of attempting it

## Why this task exists

`src/sync/index/python_lang.py` is a complete `LanguageAdapter` for Python — 443 lines, tested,
and constructed nowhere. `scripts/dead_links_baseline.txt` lists `PythonAdapter`. Sync therefore
sees TypeScript repositories and is blind to Python ones, which is a coverage limit nobody chose;
the adapter to lift it has been sitting finished.

Wiring it naively would be wrong, and the adapter itself says why. Its `static_verify` at line
494 fails closed, deliberately:

> The verification promise is that nothing reaches a pull request unverified, and it rests on
> `tsc` being present in every TypeScript project. Python has no equivalent. mypy is optional,
> frequently unconfigured, and routinely failing on code that ships happily… Returning ok=True
> would let an unverified patch through on the strength of a gate that never ran, which breaks
> the promise outright. Passing on a syntax check alone would be the same thing wearing a gate's
> clothes: a renamed field parses perfectly, and that is precisely the class of change this
> system exists to make.

That reasoning is correct and is not up for revision. But follow the consequence through the
graph as it stands: a Python finding would reach `locate`, then `prepare`, then `patch` — which
may call an agent — then `static_verify`, fail, retry, call the agent again, and abandon. The
verdict was knowable before the first token was spent.

This is the same defect the tier -1 work fixed for lifecycle changes, where the old node sequence
was `['locate','prepare','patch','patch','patch','abandon']` — the patch node running three
times on a finding no edit could resolve, spending the whole static-attempt budget and writing
the routing message into `abandon_reason`, the column where routing learns which change kinds are
not mechanically safe.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full. **"Nothing reaches a pull request
  unverified"** is the promise this task must not weaken.
- `src/sync/index/python_lang.py` in full, especially `static_verify`.
- `src/sync/remediate/graph.py` and `nodes.py` — the report node and `route_after_prepare`, added
  when tier -1 was made to reach `END` without entering `patch`. That is the mechanism you are
  reusing, not reinventing.
- `src/sync/remediate/state.py` — how `reported` is kept distinct from `abandoned`, and why.
- `src/sync/cli.py` — how the TypeScript adapter is selected today, and how the vendor registry
  resolves an adapter without naming a class.
- `scripts/dead_links_baseline.txt`, including its header.

## Files you own

- Modify: `src/sync/index/python_lang.py`
- Modify: `src/sync/cli.py`
- Modify: `src/sync/remediate/graph.py`, `nodes.py`, `state.py`
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_python_repository.py`
- Modify: existing tests in `tests/` only where your change breaks them

**Forbidden, each owned by a live task or out of scope:** `src/sync/signals/feed/`,
`src/sync/core/keys.py`, `src/sync/core/models.py`, `src/sync/verify/`, `src/sync/benchmark/`,
`tests/test_pipeline_composes.py`, and `docs/superpowers/specs/`.

## What to build

**Language selection that is data, not a branch.** A repository's language decides its
`LanguageAdapter`. The vendor registry already establishes the pattern for resolving an
implementation without naming a class in `cli.py`; follow it rather than adding an `if` on a file
extension. If you find yourself writing `if language == "python"` in `cli.py`, you have rebuilt
the thing the registry replaced.

**A finding whose adapter cannot verify is reported, not attempted.** Decide it before the branch
out of `prepare`, the way the tier is decided before it — an explicit value a node set
deliberately, read by the router. Do not catch a failure inside `patch` and return early; that
leaves `patch` in the executed node sequence and records an attempt that should never have
started.

Three things this must get right:

- **It is a report, not an abandonment.** Abandonment means Sync tried and could not finish. This
  means Sync knew not to try. `abandon_reason` is where routing learns which change kinds are not
  mechanically safe, and filling it with "this language has no verifier" corrupts that signal
  exactly as the tier -1 routing messages did.
- **It is not a silent drop either.** The finding is real and worth surfacing: a Python
  repository calling a changed vendor operation is a genuine break, and Sync knowing about it and
  saying nothing is worse than the coverage gap it just closed.
- **No agent call.** Assert it. The economic claim of deciding early is that no tokens are spent,
  and a test that only checks the outcome would pass an implementation that reached the agent
  first.

**Do not make `static_verify` return anything but `ok=False`.** Not for a syntax check, not for
mypy-if-present, not behind a flag. If you believe Python verification is achievable, that is a
finding to report and a task of its own — it is not a change to make while wiring an adapter.

## The baseline rule

Wiring a symbol makes its baseline entry stale, and `scripts/lint_dead_links.py` **fails** on an
entry that no longer describes anything. Delete each line in the same commit that wires it. You
may only delete.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement.

- **A Python repository produces call sites.** Drive it from the production entry point against a
  committed fixture repository, not by constructing `PythonAdapter`.
- **A TypeScript repository still produces call sites.** The regression that matters — without
  it, a selector resolving everything to Python passes the first test.
- **A Python finding never enters `patch`.** Assert on the node sequence, as
  `tests/test_no_patch_route.py` does. Asserting the absence of a diff is weaker and a patch node
  that ran and produced nothing would pass it.
- **No agent is consulted.** Assert with a spy that records whether it was asked.
- **The outcome is `reported`, not `abandoned`, and `abandon_reason` is unset.**
- **A TypeScript finding still reaches `patch`**, so none of the above is satisfied by a graph
  that reports everything.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

You are reading source files from a repository. Pass `encoding="utf-8"` explicitly on every read.
Python source is likelier than TypeScript to carry non-ASCII identifiers, and on this machine the
default is cp1252, so the failure would appear first against a real customer repository and never
in a fixture.

The suite is currently 1326 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: how language selection resolves without naming a class, the node sequence a Python
finding takes, how you proved no agent was consulted, how the outcome stays distinct from an
abandonment, and the four gate results.

</details>

---

## M3-W40b: build FeedCache, the consumer that makes the signed feed worth signi...

`task_b3e7f7fd6499` · created `2026-07-29 02:37:24` · status **completed**

### Result

{"completedBy":"term_26b15093-5760-4bbb-a865-38b2be53aee8","filesModified":["src/sync/core/keys.py","src/sync/core/__init__.py","src/sync/signals/feed/cache.py","src/sync/signals/feed/__init__.py","scripts/dead_links_baseline.txt","tests/test_feed_cache.py","tests/fixtures/feed/stripe.json","tests/fixtures/feed/stripe.json.sig","tests/fixtures/feed/empty.json","tests/fixtures/feed/empty.json.sig"],"completedAt":"2026-07-29T03:04:38.035Z"}

<details><summary>Brief</summary>

M3-W40: build FeedCache, the consumer that makes the signed feed worth signing

## Why this task exists

`docs/superpowers/specs/2026-07-26-sync-public-change-feed.md` records its own state precisely:

> **Status:** Built, unpublished. `src/sync/signals/feed/publisher.py` renders and signs the
> array; `src/sync/signals/feed/consumer.py` verifies before parsing, with `FeedSignatureError`
> and `FeedFormatError` keeping the two failures apart. What does not exist is everything
> operational — no keypair, no committed public key, no hosting, no `FeedCache`.

`scripts/dead_links_baseline.txt` confirms the consequence with evidence: `render_feed`,
`sign_feed`, `public_key_bytes` and `verify_and_parse` are all reachable from nothing. A feed
that is rendered by nobody and verified by nobody is cryptography with no security property.

`FeedCache` is the piece that turns those four functions into a path. It is specified in
`2026-07-25-sync-mcp-graph-surface.md` Task 4 and extended by the feed spec:

```python
def store(self, vendor_id: str, payload: bytes, signature: bytes) -> FeedSnapshot:
    if not verify(payload, signature, PUBLISHER_PUBLIC_KEY):
        raise ValueError(f"feed signature for {vendor_id} does not verify")
    changes = _parse(payload)
    ...
```

Hosting and the production keypair are operational and stay out of scope. The consumer is not.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full. The import-boundary rule matters here.
- `docs/superpowers/specs/2026-07-26-sync-public-change-feed.md` — all of it, especially
  "Integrity", "What it is", and the Verification section.
- `src/sync/signals/feed/consumer.py` and `publisher.py`. Read both fully before designing —
  `verify_and_parse` already composes verification and parsing in the required order, and the
  two error types already keep authenticity and validity apart. Do not reimplement any of it.
- `src/sync/forge/webhook.py` — its `verify_signature` docstring explains why a verifier raises
  rather than returning a boolean, and the same argument binds you.
- `scripts/dead_links_baseline.txt`, including its header.

## Files you own

- Create: `src/sync/signals/feed/cache.py`
- Modify: `src/sync/signals/feed/__init__.py`
- Create: `src/sync/core/keys.py`
- Modify: `src/sync/core/__init__.py`
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_feed_cache.py`
- Create: `tests/fixtures/feed/` and the fixtures inside it

**Explicitly forbidden, each owned by a live task:** `src/sync/core/protocols.py`,
`src/sync/detect/`, `src/sync/index/`, `src/sync/graph/schema.sql`, `src/sync/remediate/`,
`src/sync/route/`, `src/sync/benchmark/`, `src/sync/cli.py`, `src/sync/mcp/`, and
`docs/superpowers/specs/`.

Do not modify `consumer.py` or `publisher.py`. They are correct; you are giving them a caller.

## The import boundary, which decides where the key lives

`CLAUDE.md`: *"`sync.core` imports nothing from any sibling package. Not `sync.graph`, not
`sync.signals`, not anything."* `tests/test_import_boundary.py` enforces it and it is not
advisory.

The feed spec says the public key is *"committed in the `sync.core` package and rotatable only
through a release."* That works only if the key is inert data. `src/sync/core/keys.py` must hold
raw key bytes and nothing else — no `cryptography` import, no verification helper, no
`Ed25519PublicKey` object. Parsing the bytes into a key belongs to `sync.signals.feed`, which
already has `load_public_key` for it.

Run the boundary test before you commit. It has caught this class of mistake before.

## What to build

A cache that holds fetched feed payloads per vendor and answers questions about them without
refetching. Three properties are not negotiable.

**Verification runs before parsing, always.** From the spec's Verification section:

> **A tampered payload is rejected.** Flip one byte in a fixture feed, confirm `FeedCache.store()`
> raises before any `VendorChange` is constructed from it — signature verification must run
> before parsing, not after.

**Both gates are required, in order.** A signature proves origin, not correctness. `CLAUDE.md`
says it directly: *"A validly signed feed carrying a malformed `VendorChange` fails at parse,
before any row is built from it."* Signed-and-invalid and unsigned-and-valid are different
failures and must stay distinguishable — the two error types already exist for this.

**The digest and the signature are both kept.** The spec: *"The existing SHA-256 digest stays as
a corruption check; the signature is the authenticity check, and both are required — corruption
and forgery are different failure modes and one check does not stand in for the other."*

Also carry `feed_fetched_at`, which the graph-surface design already reports, so a stale cached
feed degrades legibly rather than silently.

## The generated keypair

Generate a keypair for **development fixtures only** and commit the public key to
`src/sync/core/keys.py`. Say clearly in that module's docstring that it is a development key,
that the production key is generated operationally and is not in this repository, and that a
release is the only way to rotate it.

**Never commit a private key.** Not in `src/`, not in `tests/`, not in a fixture. Tests that need
to sign generate a throwaway key at runtime; the committed artefacts are the public key and
signed payloads. `CLAUDE.md`: *"We never hold customer secrets. That one is unqualified."* The
same discipline applies to our own.

## The baseline rule

Wiring a symbol makes its baseline entry stale, and `scripts/lint_dead_links.py` **fails** on an
entry that no longer describes anything. Delete each line in the same commit that wires it. You
may only delete. If your change leaves something new unreachable, wire it or do not build it.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement.

- **A flipped byte raises before any `VendorChange` exists.** Assert on the ordering, not just on
  the exception — a test that only checks "it raised" passes an implementation that parses first
  and verifies second.
- **A validly signed, schema-invalid payload still fails**, with the parse error, not the
  signature error.
- **A bare JSON array is accepted and a top-level object is rejected.** The spec is explicit that
  the array is the whole contract and never gains a wrapper.
- **A regenerated feed for a vendor with zero new changes is byte-identical** to the previous
  publish, so a cached copy is never invalidated by a no-op run. This exercises `render_feed`
  and is the reason canonical ordering exists.
- **No private key is committed.** Assert no fixture or source file under your ownership contains
  a private key header. State in the test what it protects.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

Feed payloads are bytes, not text. `CLAUDE.md`: *"When handling bytes that are not text, use
`read_bytes`/`write_bytes` and do not decode at all."* Signature verification over a
locale-decoded payload is a bug that only appears off ASCII.

The suite is currently 1218 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: how you assert verification precedes parsing rather than merely occurring, where the
public key lives and how you confirmed the import boundary still holds, which baseline lines you
deleted, and the four gate results.

## Note on this redispatch

An earlier attempt ran three hours, produced no commits, and left its worktree clean before going
silent. Nothing survives; start from the specification above. src/sync/signals/feed/ still holds
only __init__.py, consumer.py and publisher.py, and src/sync/core/keys.py does not exist.

Commit early and often -- a commit per completed step is what makes the work recoverable if this
session ends the way the last one did. The suite is now 1337 passing.

</details>

---

## M3-W49: stop the corpus writer from failing silently, and establish what reco...

`task_ba4f5bdf3efc` · created `2026-07-29 02:38:51` · status **completed**

### Result

{"completedBy":"term_e3aac1ed-88ac-4795-9d19-10a20c4ee7f3","filesModified":["src/sync/remediate/corpus.py","tests/test_corpus_writer.py","tests/test_remediation_graph.py","tests/test_migration_recording.py","tests/test_cli.py"],"completedAt":"2026-07-29T02:53:07.209Z"}

<details><summary>Brief</summary>

M3-W49: stop the corpus writer from failing silently, and find out what it takes to record a success

## Why this task exists

The first whole-pipeline test just landed and produced the corpus's first real rows. It also
recorded two facts about the corpus that are worth more than the rows.

**The writer is reached by duck typing.** `src/sync/remediate/corpus.py:186` does:

```python
write = getattr(store, "record_migration_outcome", None)
```

and logs a warning when it is absent. That is a soft lookup on the single write the entire
benchmark depends on. Rename the method, or hand the recorder an object that does not have it,
and recording stops: the warning scrolls past in a log nobody is reading, every axis keeps
reporting null with a sample size of zero, and **null-because-nothing-ran is indistinguishable
from null-because-the-writer-vanished.** The measurement that tests the product claim would go
quiet without anything going red.

**The positive class is unreachable without a push.** From the pipeline test's own commit
message, recorded as a test rather than as prose:

> A verified patch writes no corpus row at all, because only `open_pr` records a success and it
> takes a forge -- so the positive class, and with it merge rate and cost per merged patch, is
> unreachable from any test that does not push.

So the corpus can currently record that Sync failed and cannot record that Sync succeeded until a
pull request is opened. `docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` says
abandoned runs are data; the same argument applies in the other direction, and a patch that
passed `tsc` and replay is an outcome whether or not anyone pushed it.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` — the grain rule and the
  abandoned-runs-are-data rule.
- `docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` — "Gate tier B", and why an axis
  reporting null with a sample size is not the same as an axis reporting zero.
- `src/sync/remediate/corpus.py` in full.
- `tests/test_pipeline_composes.py` — the run that produced the first rows, and the two tests
  recording what it could not reach.
- `src/sync/graph/store.py`, `record_migration_outcome`.

## Files you own

- Modify: `src/sync/remediate/corpus.py`
- Create: `tests/test_corpus_writer.py`
- Modify: existing tests in `tests/` only where your change breaks them

**Forbidden, each owned by a live task:** `src/sync/remediate/graph.py`, `nodes.py` and
`state.py`, `src/sync/cli.py`, `src/sync/index/`, `src/sync/signals/feed/`,
`src/sync/core/keys.py`, and `docs/superpowers/specs/`. Do not edit
`tests/test_pipeline_composes.py`.

The forbidden list is narrow on purpose and it shapes the second half of this task. See below.

## Part one: make the writer's absence loud

Replace the soft lookup with something that cannot fail quietly. What "loud" means is your
judgement — a raised exception, a typed protocol the store must satisfy, an assertion at
construction — but it must satisfy three things:

- **A store without the writer fails visibly**, at a point a test can assert on, rather than
  producing a run that looks successful and records nothing.
- **The failure names what is missing.** A reader should not have to diff two versions of the
  store to work out why recording stopped.
- **It does not turn a recoverable run into a lost one.** Read `corpus.py` carefully first: if
  the recorder is invoked from inside a node's error path, raising there may abandon a run that
  would otherwise have completed. If that is the case, say so and choose the loudest option that
  does not destroy the run — and state in your report which you chose and why.

`CLAUDE.md` is relevant twice here. It says not to add error handling for conditions that cannot
occur — and this condition can occur, which is the whole point. It also says to validate at
system boundaries and trust internal code; a store handed to the recorder is an internal
collaborator, so the right answer is likely a contract stated once at construction rather than a
check on every write.

## Part two: establish what recording a success actually requires

**Do not build it. Establish it.** `graph.py` and `nodes.py` belong to another task right now, so
the wiring is not yours to make even if it turns out to be small.

Answer these, from the code rather than from reasoning about it:

- Where exactly does the success row get written today, and what does that call site have that a
  post-verification call site would not?
- Is `open_pr` the only writer of a terminal success, or are there others?
- What would a verified-but-unpushed outcome be called, given that `MigrationOutcome` already
  constrains `strategy` to `Literal["codemod", "agent"]` and the finding status to
  `open`/`patched`/`abandoned`? An earlier task established that a tier -1 outcome is
  unrepresentable for exactly this reason — check whether the same wall stands here.
- Which of the five benchmark axes become computable if a verified patch records a row, and which
  still need a real merge webhook?

Write the answer as a **test that documents the gap and fails if it closes** — the same technique
the pipeline test used, so the finding lives in the suite rather than in a report nobody rereads.
If you conclude a schema or model change is required, say so precisely and name the file; do not
make it.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement. And prove the important ones non-vacuous: for part one, break the store
deliberately and watch the test go red before trusting it. A test asserting a loud failure is
exactly the kind that passes for the wrong reason.

- **A store missing the writer fails visibly**, and the failure names the missing method.
- **A store with the writer records the row.** Without this, part one is satisfied by something
  that rejects every store.
- **The grain still holds** — one row per attempt, not per finding.
- **The gap test** from part two, asserting today's behaviour and phrased so it fails when the
  behaviour changes, with a comment saying that failing is the point.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

The suite is currently 1337 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: what you replaced the `getattr` with and why that shape, whether raising could abandon a
recoverable run and what you did about it, and your answers to the four part-two questions with
the file and line behind each.

</details>

---

## M3-W50: serve sync://feed/{vendor}, the resource FeedCache was built for

`task_981734fc9d8f` · created `2026-07-29 03:24:56` · status **completed**

### Result

{"completedBy":"term_26b15093-5760-4bbb-a865-38b2be53aee8","filesModified":["src/sync/mcp/resources.py","src/sync/mcp/server.py","src/sync/mcp/__init__.py","scripts/dead_links_baseline.txt","tests/test_mcp_resources.py","tests/test_mcp_server.py"],"completedAt":"2026-07-29T03:37:12.567Z"}

<details><summary>Brief</summary>

M3-W50: serve sync://feed/{vendor}, the resource FeedCache was built for

## Why this task exists

`FeedCache` landed complete and tested, and it is the newest entry in
`scripts/dead_links_baseline.txt`. Its comment block names precisely what retires it:

> The consuming half is now built and verified — `FeedCache.store` calls `verify_and_parse`…
> the `sync://feed/{vendor}` resource does not exist. `sync.mcp` publishes four frozen tools and
> has no notion of a resource at all, so wiring this is a feature to be built and not a call site
> to be added. **This line leaves when that resource exists.**

The resource is specified, not invented: `docs/superpowers/specs/2026-07-25-sync-graph-surface-design.md:79`
defines it as *"the normalized change feed, served from the server's local cache."*

So the whole feed path exists except its last link. `render_feed` and `sign_feed` publish, the
consumer verifies before parsing, `FeedCache` holds and refreshes — and nothing serves it. Two
more baseline entries are downstream of the same gap.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-25-sync-graph-surface-design.md` — the resource at line 79 and
  everything the document says about the separation between the public feed and the private
  graph.
- `docs/superpowers/specs/2026-07-26-sync-public-change-feed.md` — "Integrity" and "What is never
  in the feed", both of which bind what you may serve.
- `src/sync/mcp/server.py`, `registry.py`, `tools.py`, `propose.py`. The transport is
  hand-written newline-delimited JSON-RPC 2.0 and the four tools are declared as data with a
  golden file pinning their schemas. Read how that golden file works before you touch anything
  near it.
- `src/sync/signals/feed/cache.py` — what you are serving from.
- `scripts/dead_links_baseline.txt`, including its header.

## Files you own

- Modify: `src/sync/mcp/server.py`, `registry.py`, `__init__.py`
- Create: `src/sync/mcp/resources.py` if a resource wants its own module
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_mcp_resources.py`
- Modify: `tests/golden/tool_schemas.json` — only if adding a resource genuinely changes it, and
  see the warning below
- Modify: existing tests in `tests/` only where your change breaks them

**Forbidden, each owned by a live task or out of scope:** `src/sync/cli.py`,
`src/sync/remediate/`, `src/sync/index/`, `src/sync/detect/`, `src/sync/core/`,
`src/sync/graph/`, `src/sync/signals/` (including `feed/` — `FeedCache` is finished and you are
giving it a caller), and `docs/superpowers/specs/`.

## The frozen schemas, which is the trap here

The four tools are frozen. `tests/golden/tool_schemas.json` pins them precisely so that a change
to what the server advertises cannot happen by accident.

**A resource is not a tool.** Adding one must not alter any tool's schema, and the golden file
should still describe the same four tools afterwards. If your change rewrites that file's tool
entries, you have changed a frozen contract — stop and report it rather than regenerating the
golden file to match. Regenerating a golden file to make a test pass converts the one artifact
that would have caught a breaking change into a record of it.

If the golden file needs to grow a resources section alongside the tools, that is a legitimate
extension; say so explicitly in your report and keep the tool half byte-identical.

## What to serve, and what never to serve

`sync://feed/{vendor}` returns the normalized change feed for one vendor, from the local cache.

Three constraints from the specs, all binding:

**Verified before served.** `FeedCache.store` already refuses to write anything until both gates
pass. Do not add a path that serves unverified bytes — no "serve what we have if verification
failed", no bypass flag. The feed drives code changes, which is why it is signed at all.

**Nothing customer-specific.** From the feed spec: *"No customer data, of any kind… No `observed`
bindings, no telemetry-derived shapes — those are customer-specific and stay in the customer's
own graph."* The resource serves vendor-side public information only. A resource that reached
into the graph store for anything would cross the line the whole public/private separation
exists to draw.

**A cache miss is not an error to hide.** If no verified snapshot exists for a vendor, say so —
`sync_whats_changed` already reports `feed_fetched_at` so a stale feed degrades legibly. Serving
an empty array for "we have never fetched this" would read as "this vendor changed nothing",
which is the same false-negative shape the repository has rejected elsewhere.

## The baseline rule

Wiring a symbol makes its baseline entry stale, and `scripts/lint_dead_links.py` **fails** on an
entry that no longer describes anything. Delete each line in the same commit that wires it. You
may only delete.

Note a known limitation before you trust a clean run: the lint matches bare names without
resolving them, so a method can appear reached because an unrelated local variable shares its
name. `FeedCache.snapshot` and `FeedCache.changes` are alive by exactly that coincidence. Do not
take a clean lint as proof your resource is reachable — assert it with a test.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement.

- **A client can read `sync://feed/stripe` over the real transport** and gets the changes a
  verified snapshot holds. Drive it through the server, not by calling a handler directly.
- **An unknown vendor, and a vendor with no snapshot, are distinguishable from each other and
  from an empty feed.** Three outcomes, three answers.
- **Unverified bytes are never served.** Store a payload whose signature fails and assert the
  resource yields nothing derived from it. Prove this one non-vacuous by deliberately bypassing
  the gate and watching it go red.
- **The four tool schemas are unchanged.** Assert against the golden file.
- **No customer data leaves through the resource.** Assert the response carries only
  `VendorChange`-shaped entries and nothing graph-derived.

No test calls a vendor API. Feed payloads are committed fixtures; `tests/fixtures/feed/` already
holds signed ones.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## One process note

Terminals in this workspace are pinned to worktrees, and two coordinators dispatch into the same
pool. A previous task found another worker's untracked files appearing in its tree mid-run. Stage
your own paths explicitly when you commit — **never `git commit -a`** — and if files you did not
create appear under `git status`, say so in your report rather than committing them.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

Feed payloads are bytes, not text. Use `read_bytes`/`write_bytes` and do not decode — a signature
verified over a locale-decoded payload is a bug that appears first off ASCII.

The suite is currently 1379 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: how the resource is declared alongside the frozen tools and whether the golden file
changed, the three distinguishable cache outcomes, how you proved unverified bytes cannot be
served, which baseline lines you deleted, and the four gate results.

</details>

---

## M3-W51: give the merge webhook a caller, so the last two benchmark axes can b...

`task_6dcfb7b25690` · created `2026-07-29 03:35:57` · status **completed**

### Result

{"completedBy":"term_b64d2f71-f51d-4c54-a60b-36cc381b4fdb","filesModified":["src/sync/cli.py","scripts/dead_links_baseline.txt","tests/test_merge_outcome_command.py","tests/fixtures/webhook/"],"completedAt":"2026-07-29T03:46:05.460Z"}

<details><summary>Brief</summary>

M3-W51: give the merge webhook a caller, so the last two benchmark axes can be computed

## Why this task exists

`src/sync/forge/webhook.py` verifies a GitHub HMAC-SHA256 signature before parsing, distinguishes
a forgery from a malformed payload, and calls `GraphStore.set_merge_outcome`. It is complete and
`scripts/dead_links_baseline.txt` lists `record_merge_outcome` as reached from nothing.

The consequence is measured, not theoretical. The corpus work established that of the five
benchmark axes, routing accuracy is now computable from a verified run — but **merge rate and
cost per merged patch stay null pending a real `pr_merged` webhook.**
`docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` calls merge rate *"the direct test of
the product claim"*, and records this precondition as one that does not hold:

> **`pr_merged` and `human_edits_before_merge` are populated from a real webhook**, not inferred.
> Merge outcome arrives days after the run. A field that silently stays null for six months
> destroys the only measurement that tests the product claim.

The receiver exists. Nothing hands it a delivery.

## What this task is not

**Do not build a server.** `docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` records
a deliberate strategic refusal of ingestion infrastructure, and the spec audit confirmed it still
holds: *"there is no server, no port and no collector protocol."* No HTTP listener, no port
binding, no framework.

The precedent is already in the tree. OTLP ingestion had the same shape — a complete decode-and-
fold with no caller — and was wired as a command that takes a payload it is given, with a test
asserting no port is bound. Follow that, exactly.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` — "Gate tier B" and its
  precondition list.
- `src/sync/forge/webhook.py` in full. Its `verify_signature` docstring explains why a verifier
  raises rather than returning a boolean, and why `hmac.compare_digest` rather than `==`.
- `src/sync/cli.py`, specifically the `ingest` command that wired `ingest_payload` — that is the
  shape you are copying.
- `src/sync/graph/store.py`, `set_merge_outcome`.
- `scripts/dead_links_baseline.txt`, including its header.

## Files you own

- Modify: `src/sync/cli.py`
- Modify: `src/sync/forge/webhook.py` — only if wiring reveals a genuine defect; prefer reporting
  one to fixing it quietly
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_merge_outcome_command.py`
- Create: `tests/fixtures/webhook/` and the fixtures inside it
- Modify: existing tests in `tests/` only where your change breaks them

**Forbidden, each owned by a live task or out of scope:** `src/sync/mcp/`,
`src/sync/signals/registry.py`, `src/sync/signals/mcp_server/`, `src/sync/signals/feed/`,
`src/sync/core/`, `src/sync/graph/schema.sql`, and `docs/superpowers/specs/`.

## The secret, which is the part to get right

The webhook secret is a credential. `CLAUDE.md`: **"We never hold customer secrets. That one is
unqualified."**

So the command must take the secret from the environment or a path handed to it at run time, and
**never** from a committed file, a default, or a fallback. There is no development secret to
commit here — unlike the feed's public key, this one is a shared secret and committing any value
for it teaches the wrong pattern even if the value is fake.

Two more:

- **A missing secret is a hard failure, not a skipped verification.** If the secret is absent the
  command refuses to run. It must never fall through to processing an unverified payload, and it
  must never log the secret or any part of it.
- **Verification stays before parsing.** `handle` already orders it that way. Do not add a path
  that parses first to decide whether verification is worth doing.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement.

- **A validly signed merged-PR delivery populates `pr_merged`.** Drive it through the command,
  not by calling `record_merge_outcome` — calling it directly re-creates the situation this task
  fixes.
- **A forged signature changes nothing in the store.** Assert the row is untouched, not merely
  that an exception was raised. Prove it non-vacuous by bypassing the check and watching it fail.
- **A missing secret refuses to run** and does not process the payload.
- **No port is bound and no listener starts.** Assert it, as the OTLP wiring does.
- **A `closed` delivery that did not merge is recorded as not merged, not as absent.** These are
  different facts and the benchmark divides by one of them.
- **After the command runs, merge rate is computable and reports a real sample size.** This is
  the point of the task; assert a number and its `n`, and no threshold.

Fixtures are committed deliveries. No test calls the GitHub API. Sign your fixtures at test time
with a throwaway secret generated in the test — do not commit a secret, not even a fake one.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Process note

Terminals in this workspace are pinned to worktrees and two coordinators dispatch into the same
pool. Stage your own paths explicitly — **never `git commit -a`** — and if files you did not
create appear in `git status`, report them rather than committing them.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

Webhook payloads are bytes. The HMAC is computed over exactly the bytes received, so use
`read_bytes` and do not decode before verifying — a signature checked over a re-encoded payload
fails for a reason that looks like forgery.

The suite is currently 1413 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: where the secret comes from and what happens without it, the first merge-rate number the
benchmark reports after your command runs and its sample size, how you proved a forged delivery
changes nothing, which baseline lines you deleted, and the four gate results.

</details>

---

## M3-W52: let the registry express a protocol with many catalogues, and wire th...

`task_980888716033` · created `2026-07-29 03:35:58` · status **completed**

### Result

{"completedBy":"term_e3aac1ed-88ac-4795-9d19-10a20c4ee7f3","filesModified":["src/sync/signals/registry.py","mcp-servers.yaml","tests/test_mcp_registry_wiring.py","tests/fixtures/mcp_servers/","scripts/dead_links_baseline.txt"],"completedAt":"2026-07-29T03:49:29.989Z"}

<details><summary>Brief</summary>

M3-W52: let the registry express a protocol with many catalogues, and wire the MCP adapter

## Why this task exists

`src/sync/signals/mcp_server/adapter.py` implements `VendorAdapter` for MCP servers — watching a
server's advertised tools as a vendor signal. It is complete, tested, and constructed nowhere.
Its baseline entry states the blocker precisely, and the reasoning is the task:

> `_BUILDERS` maps one vendor id to one builder, which suits a vendor that publishes one API. MCP
> is a protocol, not a vendor: every server watched is a separate catalogue, so an entry keyed
> `mcp` would have to name one server and would be the vendor knowledge that module exists to
> keep out. Wiring it needs a decision about how a deployment declares which servers it watches —
> the configured `generated-vendors.yaml` path is the closest existing shape. It leaves when that
> decision is made.

That decision is what this task makes. The registry was built to remove vendor names from
`cli.py`, and it succeeded — but its shape assumes one vendor id resolves to one API. A protocol
under which many independent catalogues live does not fit, and forcing it in would reintroduce
exactly the vendor knowledge the registry exists to keep out.

This matters beyond MCP. `docs/superpowers/specs/2026-07-25-sync-mcp-drift-measurement.md`
measures MCP servers at breaking changes in roughly half their release transitions, which is why
MCP is a real test of the model rather than a curiosity.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full. **"Vendor-specific knowledge lives in
  adapters, never in core. The moment core knows a vendor's name, the plugin story is dead."**
- `src/sync/signals/registry.py` in full — `_BUILDERS`, how `generated-vendors.yaml` is read, and
  what the registry deliberately does and does not hand an adapter.
- `generated-vendors.yaml` and its header comment, which states the three fields and why none of
  them is knowledge about a vendor's API.
- `src/sync/signals/mcp_server/adapter.py` — what it needs to be constructed.
- `docs/superpowers/specs/2026-07-27-sync-adapter-targets.md`, and
  `2026-07-25-sync-mcp-drift-measurement.md` for why MCP is worth this.
- `scripts/dead_links_baseline.txt`, including its header.

## Files you own

- Modify: `src/sync/signals/registry.py`, `src/sync/signals/mcp_server/` (its own modules),
  `src/sync/signals/__init__.py`
- Modify or create: the configuration file that declares watched servers
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_mcp_registry_wiring.py`
- Create: `tests/fixtures/mcp_servers/` and the fixtures inside it
- Modify: existing tests in `tests/` only where your change breaks them

**Forbidden, each owned by a live task or out of scope:** `src/sync/cli.py`, `src/sync/mcp/`
(that is the server Sync *publishes*, a different thing from the servers it *watches* — do not
confuse them), `src/sync/forge/`, `src/sync/signals/feed/`, `src/sync/core/`,
`src/sync/graph/schema.sql`, and `docs/superpowers/specs/`.

`src/sync/cli.py` being forbidden shapes the task: the resolution must happen inside the registry,
which is where the existing configured path already resolves. If it cannot, report that rather
than reaching for `cli.py`.

## What to decide, and the constraint on deciding it

**How does a deployment declare which MCP servers it watches?**

The closest existing shape is `generated-vendors.yaml`, where a vendor under a supported generator
costs one configuration entry and no module. Whatever you choose, three things bind:

**No server name in shared code.** The registry must not learn any particular server's name, URL,
or tool conventions. That is the rule the baseline entry says an `mcp` key would break, and it is
the one this whole design exists to protect.

**A watched server must be addressable as a vendor downstream.** Every row in the graph is keyed
by `vendor_id`, so each watched server needs a stable identity that is not "mcp". Decide what that
identity is and say why it is stable — a server's URL changing must not silently orphan its
history, and two servers must never collide into one id.

**An unresolvable entry fails naming what is available.** The registry already establishes this
for unknown vendors: no silent default, no fallback. Match it.

**Do not confirm a target you have not checked.** `generated-vendors.yaml` records that every
entry in it was confirmed by fetching the path, and the adapter-targets spec keeps a list of
targets it could not resolve. If you configure any real server, confirm it the same way and say
how; if you configure none and ship only the mechanism plus fixtures, that is a legitimate answer
— say so plainly rather than inventing an entry to look complete.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement.

- **A configured MCP server resolves to `McpServerAdapter`** through the registry, not by
  construction in the test. Prove it fails first; today there is no path.
- **Two configured servers resolve to two distinct adapters with distinct vendor ids**, and their
  rows do not collide. This is the property the whole design turns on — a single-server test
  cannot see it.
- **Existing vendors still resolve to themselves.** The regression that matters.
- **The registry names no server.** Assert it, since this is the property a later change will
  quietly undo.
- **An unresolvable entry fails naming what is available**, rather than defaulting.

No test contacts a real MCP server. `CLAUDE.md`: fixtures are committed, and a vendor API is a
vendor API whatever protocol it speaks.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Process note

Terminals in this workspace are pinned to worktrees and two coordinators dispatch into the same
pool. Stage your own paths explicitly — **never `git commit -a`** — and if files you did not
create appear in `git status`, report them rather than committing them.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

Configuration is YAML read from disk. Pass `encoding="utf-8"` explicitly on every read; the
default here is cp1252 and a server name with one accented character would fail only in
production.

The suite is currently 1413 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: how a deployment declares a watched server, what gives each one a stable `vendor_id` and
why it survives a URL change, how you kept every server name out of the registry, whether you
configured any real server and how you confirmed it, which baseline lines you deleted, and the
four gate results.

</details>

---

## M3-W53: read the mined migrations and decide whether they can be ground truth

`task_f979c0c487eb` · created `2026-07-29 03:45:44` · status **completed**

### Result

{"completedBy":"term_26b15093-5760-4bbb-a865-38b2be53aee8","filesModified":["docs/superpowers/specs/2026-07-29-sync-ground-truth-quality.md","scripts/read_stripe_migrations.py","tests/test_read_stripe_migrations.py","tests/fixtures/github_commits/"],"completedAt":"2026-07-29T04:07:48.950Z"}

<details><summary>Brief</summary>

M3-W53: read the mined migrations and decide whether they can be ground truth

## Why this task exists

`docs/superpowers/specs/2026-07-28-sync-ground-truth-count.md` ran the count the benchmark spec
demanded before anyone built a harness, and returned a verdict in two halves:

> **The approach is viable on sample size and unproven on label quality.**

Sample size is settled: 23,926 files carry a Stripe API version pin and 1,608 commits name an
observable version boundary. The spec's own failure test — *"if the answer is a handful, the
approach fails on sample size"* — is not met, so the synthetic-mutation fallback is not
triggered.

What the count could not settle is whether those commits are worth labelling with. Sampling the
repositories behind them found:

> **23 of 29 have zero stars**, 27 of 29 were created in 2026… commit messages are formulaic and
> multilingual — `fix: update Stripe apiVersion to 2026-05-27.dahlia`, `fix: actualizar version
> Stripe API a 2026-05-27.dahlia` — uniform enough to suggest they were written by coding agents
> rather than by engineers with full context.

That matters because the entire premise is that *"the human's own migration commit is a labelled
patch — a correct answer, authored by someone with full context."* If the findable cohort is
agent-written, Sync would be scoring itself against other agents' output, and binding precision
and binding recall — the two axes the benchmark spec calls the ones that matter most — would rest
on a reference nobody has checked.

**This task checks it.** It is measurement and a verdict, not construction.

## What this task is not

**Do not build a mining harness.** No cloning, no checking out parent commits, no running Sync's
pipeline against anything. The benchmark spec's sequencing rule still binds — *"Do not build the
harness before running the count"* — and this task exists because the count raised a question the
count could not answer, not because the count is finished.

If you find yourself writing code that clones a repository, stop and finish the reading.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-28-sync-ground-truth-count.md` — all of it, especially "The
  measurement that changes the verdict", "Verdict", and "What could not be measured, and why".
- `docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` — "Ground truth without customers",
  including the three named weaknesses: survivorship, the human is not always right, and commit
  granularity.
- `scripts/mine_stripe_migrations.py` — the instrument the count used, and the split it keeps
  between fetching and counting. Reuse that shape; the pure part is what your tests drive.

## Files you own

- Modify: `scripts/mine_stripe_migrations.py`, or create a sibling under `scripts/` if the
  reading is a different job from the counting — your judgement, but say which you chose and why
- Create: `tests/fixtures/github_commits/` and the fixtures inside it
- Create or modify: the matching test file under `tests/`
- Create: `docs/superpowers/specs/2026-07-29-sync-ground-truth-quality.md`

**Forbidden — everything under `src/`.** Three other tasks own most of it and this task needs
none of it. Also forbidden: `docs/superpowers/specs/2026-07-28-sync-ground-truth-count.md` — it
is a dated record of what was measured on that day, and your findings go in a new document rather
than by editing history.

## What to establish

Read an actual sample of the migration commits and answer, with evidence:

**Are they human-authored or agent-authored?** The count inferred agent authorship from message
uniformity, which is suggestive and not proof. Look for what would settle it: co-author trailers,
committer identity patterns, whether the diff touches only the pin or also the call sites a
version bump actually breaks, whether the repository has any other human activity.

**Are the diffs the kind of labelled patch the benchmark needs?** A commit that bumps a pinned
version string and changes nothing else is not a migration — it is a version bump that either
compiled by luck or broke silently. The benchmark needs commits where the human *also changed the
call sites*, because that is the correct answer Sync's output would be scored against.

**Does a healthier cohort exist and is it reachable?** The count observed only three dated
versions, all from 2026, because those were the ones in the repository's cache. The pin cohort
looks entirely different — 7 of 30 with 100+ stars, creation dates spread 2017 to 2025. Establish
whether migrations by that cohort are findable at all, and say what would be required to find
them.

**Sample size and selection.** Say how many commits you read, how you chose them, and why that
choice does not flatter the answer. A sample drawn from the first page of a relevance-ranked
search is not random, and the count already says so about its own figures — hold to the same
standard.

## The verdict this must produce

State plainly whether mined migrations can serve as ground truth for binding precision and
recall, in one of three forms:

- **Yes**, with the cohort characterised and the exclusion rules named.
- **No**, with the reason, and a recommendation on the fallback the benchmark spec already names:
  synthetic mutation of real repositories, at the cost of realism.
- **Not yet**, with the specific thing that would settle it and roughly what it costs.

A verdict of "no" is a good outcome. It stops a harness being built on a reference that cannot
support it, which is exactly what the sequencing rule exists to prevent. Do not reach for "yes"
because it unblocks more work.

## Test discipline

`CLAUDE.md` is binding. No test calls the GitHub API — it is a vendor API. Your tests drive the
pure classification from committed fixtures under `tests/fixtures/github_commits/`, and the
fetching stays injectable, exactly as the counting instrument already separates them.

Write the failing test, run it, watch it fail for the reason you expect, then implement. At
minimum: a commit that touches only the pin is classified differently from one that touches the
pin and call sites; a rate-limited or errored response is distinguishable from a genuine zero;
and whatever authorship signal you use is asserted on a fixture that carries it and one that does
not.

Use your own `SYNC_DSN` even though this task should not touch the database.

## Process note

Terminals here are pinned to worktrees and two coordinators dispatch into the same pool. Stage
your own paths explicitly — **never `git commit -a`** — and report any files you did not create
that appear in `git status`.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

You are shelling out to `gh`. `CLAUDE.md`: a missing `encoding="utf-8"` on
`subprocess.run(..., text=True)` raises on the reader thread, never propagates, returns `stdout`
as `None`, and fails somewhere unrelated. Commit messages in this cohort are multilingual, so
this will bite rather than might.

The suite is currently 1427 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Write the document in normal prose, in the voice of the other specs. Commit with a Conventional
Commits subject and a body in normal prose explaining why. Then report: your verdict in one line,
how many commits you read and how you chose them, the authorship evidence, and the four gate
results.

</details>

---

## M3-W54: record the pull request number, so the merge webhook can find the row...

`task_863ddf3e73d2` · created `2026-07-29 03:49:47` · status **completed**

### Result

{"completedBy":"term_b64d2f71-f51d-4c54-a60b-36cc381b4fdb","filesModified":["src/sync/forge/github.py","src/sync/remediate/nodes.py","src/sync/remediate/corpus.py","src/sync/remediate/state.py","tests/test_pr_number_recorded.py","tests/test_github_forge.py","tests/test_cli.py","tests/test_migration_recording.py","tests/test_no_patch_route.py","tests/test_python_repository.py","tests/test_remediation_graph.py","tests/test_replay_stage.py"],"completedAt":"2026-07-29T04:02:45.275Z"}

<details><summary>Brief</summary>

M3-W54: record the pull request number, so the merge webhook can find the row it belongs to

## The defect, verified in the code

The merge webhook receiver landed and works. It verifies an HMAC-SHA256 signature before parsing,
distinguishes a forgery from a malformed payload, and finds the corpus row a delivery belongs to
by matching on the pull request number:

```python
candidates = [row for row in store.migration_outcomes() if row.pr_number == pr_number]
```

`MigrationOutcome.pr_number` exists at `src/sync/core/models.py:182`, defaults to `None`, and
**nothing ever writes it.** `nodes.py:552` calls `forge.open_pull_request(...)`, which returns a
URL; line 561 stores that as `pr_url` and sets the outcome to `opened`. The number is never
recorded.

So every row has `pr_number = None`, the receiver's match finds nothing, and a delivery that
verifies correctly updates no row. `docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md`
calls merge rate *"the direct test of the product claim"*; it has a receiver, a command, a
verified signature — and still no numerator, for want of one column.

The task that built the receiver found this and reported it rather than reaching across
ownership, which is why it is a task rather than a drive-by edit.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` — "Gate tier B" and its precondition
  list, which names this field explicitly.
- `docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` — the grain rule. One
  `migration_outcome` row is one attempt, and a run can make several.
- `src/sync/remediate/nodes.py`, `make_open_pr` around line 540 and the `pr_url` it returns.
- `src/sync/remediate/corpus.py`, and where it builds the `MigrationOutcome`.
- `src/sync/forge/github.py`, `open_pull_request` — what it has in hand when it returns.
- `src/sync/forge/webhook.py`, `record_merge_outcome` — the consumer, and what it matches on.

## Files you own

- Modify: `src/sync/remediate/nodes.py`, `corpus.py`, `state.py`
- Modify: `src/sync/forge/github.py` and `src/sync/core/protocols.py` — only if the number
  genuinely cannot be had without changing what the forge returns; see below
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_pr_number_recorded.py`
- Modify: existing tests in `tests/` only where your change breaks them

**Forbidden, each owned by a live task or out of scope:** `src/sync/core/conformance.py`,
`src/sync/core/models.py`, `src/sync/signals/`, `src/sync/mcp/`, `src/sync/cli.py`,
`src/sync/index/`, `src/sync/graph/schema.sql`, `scripts/mine_stripe_migrations.py`, and
`docs/superpowers/specs/`.

`src/sync/core/models.py` is forbidden and should not be needed — `pr_number` is already declared
there. If you conclude it must change, stop and report that instead.

## How to get the number, and the way not to

The obvious shortcut is a regular expression over `pr_url`. **Prefer not to.** A number parsed out
of a URL is a second implementation of the forge's own knowledge: it is correct until the URL
shape changes, and then it fails by producing a plausible wrong number rather than an error —
which would attach a merge outcome to somebody else's attempt.

The forge already knows the number; it created the pull request. If `open_pull_request` can return
it, or return something carrying it, that is the honest source. Changing the protocol's return
type touches `src/sync/core/protocols.py`, which is granted for this reason and this reason only
— and it is a contract several things depend on, so:

- Keep the change additive if you can. Something that also carries the URL is easier to land than
  something that replaces it.
- If you widen the protocol, every implementation must satisfy it, including any test double. Run
  the full suite and read what breaks rather than adjusting doubles until it passes.
- If you conclude parsing the URL is genuinely the only option, say so with the reason, and make
  the parse fail loudly on a shape it does not recognise rather than returning a best guess.

## The grain, which is where this can go quietly wrong

One row is one attempt, and a run can make several. Only the attempt that opened the pull request
has a number; earlier attempts that were retried do not, and must keep `pr_number` null rather
than inheriting it. A merge outcome written against three rows because they shared a run would
inflate the numerator of the axis this whole chain exists to compute — and it would inflate it
silently, which is worse than being wrong loudly.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement.

- **A run that opens a pull request records its number.** Prove it fails first; today the column
  is null.
- **A verified delivery finds the row and sets `pr_merged`.** Drive it through
  `record_merge_outcome`, so the whole chain is exercised rather than the write alone. This is
  the test that proves the numerator exists.
- **Retried attempts keep `pr_number` null.** Build a run with more than one attempt; a
  single-attempt test cannot see this.
- **A delivery for an unknown number changes nothing**, rather than matching the most recent row.
- **Merge rate reports a real number with its sample size** once a merged delivery has been
  recorded. Assert the number and the `n`, and no threshold — the spec forbids inventing one.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Process note

Terminals here are pinned to worktrees and two coordinators dispatch into the same pool. Stage
your own paths explicitly — **never `git commit -a`** — and report any files you did not create
that appear in `git status`.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one. It matters more than usual if you widen a `sync.core`
protocol.

The suite is currently 1442 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: where the number comes from and why that source cannot name the wrong pull request,
whether you widened the protocol and what had to change if so, how retried attempts stay null,
the first merge-rate number and its sample size, and the four gate results.

</details>

---

## M3-W55: publish the signed feed, with a private key this repository never holds

`task_2b0997089342` · created `2026-07-29 03:55:33` · status **completed**

### Result

{"completedBy":"term_e3aac1ed-88ac-4795-9d19-10a20c4ee7f3","filesModified":["src/sync/cli.py","tests/test_feed_publish.py","scripts/dead_links_baseline.txt"],"completedAt":"2026-07-29T04:08:18.750Z"}

<details><summary>Brief</summary>

M3-W55: publish the signed feed, with a private key this repository never holds

## Why this task exists

The consuming half of the public change feed is finished and reachable: `FeedCache` verifies
before parsing, and `sync://feed/{vendor}` serves it. The producing half is not.
`scripts/dead_links_baseline.txt` lists three symbols, all in
`src/sync/signals/feed/publisher.py`:

```
src/sync/signals/feed/publisher.py:render_feed
src/sync/signals/feed/publisher.py:sign_feed
src/sync/signals/feed/publisher.py:public_key_bytes
```

Their baseline comment says what retires them: *"These leave when something in this tree
publishes."*

The feed is the strategic move `docs/superpowers/specs/2026-07-25-sync-positioning-and-open-core.md`
commits to — publishing it is the attack on the vendors whose entire product is a change feed.
It is currently rendered by nothing.

## The line between this and hosting

`2026-07-26-sync-public-change-feed.md` puts hosting outside the architecture: static files behind
a CDN, no server-side logic, and the keypair and publish job are *"operational, not
architectural"*.

**You are building the command that produces the files, not the thing that serves them.** No
upload, no CDN client, no bucket, no server. It writes `{vendor_id}.json` and
`{vendor_id}.json.sig` to a directory it is given, and stops. Whoever runs it decides where those
bytes go.

This is the same shape two commands in this tree already take: OTLP ingestion and the merge
webhook were both wired as commands that act on what they are handed, with tests asserting no
port is bound.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full. **"We never hold customer secrets. That
  one is unqualified."** The publishing key is ours rather than a customer's, and the same
  discipline applies.
- `docs/superpowers/specs/2026-07-26-sync-public-change-feed.md` — "Production", "Integrity",
  "Hosting", and the Verification section in full.
- `src/sync/signals/feed/publisher.py` — the three functions and what they take.
- `src/sync/core/keys.py` — the committed development public key, and its docstring explaining
  why it is inert bytes.
- `src/sync/cli.py`, the `merge-outcome` command, for how a secret is taken from the environment
  or a named file and never from an argument.
- `scripts/dead_links_baseline.txt`, including its header.

## Files you own

- Modify: `src/sync/cli.py`
- Modify: `src/sync/signals/feed/publisher.py` — only if publishing reveals a genuine defect
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_feed_publish.py`
- Modify: existing tests in `tests/` only where your change breaks them

**Forbidden, each owned by a live task or out of scope:** `src/sync/remediate/`,
`src/sync/forge/`, `src/sync/core/`, `src/sync/mcp/`, `src/sync/signals/registry.py`,
`src/sync/signals/mcp_server/`, `src/sync/index/`, `src/sync/graph/schema.sql`,
`scripts/mine_stripe_migrations.py`, and `docs/superpowers/specs/`.

## The private key, which is the whole risk here

Signing needs the private half. **This repository must never contain one**, and a test already
scans every git-tracked file for private-key headers and for
`Ed25519PrivateKey.from_private_bytes` — do not weaken it.

So the key arrives at run time, and the rules are the ones the webhook secret already
established:

- **From an environment variable or a named file, and nothing else.** No `--key VALUE` argument:
  an argument is visible in `ps` and lands in shell history. The existing `_webhook_secret`
  helper documents this reasoning; follow it.
- **A missing key is a refusal, not an unsigned publish.** Never write a `.json` without its
  `.sig`. An unsigned feed that drives code changes is the supply-chain surface the whole design
  exists to close, and a half-published pair is worse than nothing because a consumer may fetch
  the payload before the signature exists.
- **Never log the key, any part of it, or a derived value that would narrow it.**
- Tests generate a throwaway keypair at run time. Committed fixtures are payloads and signatures,
  never keys.

`public_key_bytes` derives the public half from a private key. It is how the committed
development key was produced once, in a process that kept no private half — so if your command
offers a way to print the public key for an operator to commit, that is its legitimate caller.

## Byte-identical republication

The spec's Verification section requires it:

> **A regenerated feed for a vendor with zero new changes is byte-identical** to the previous
> publish, so a customer's cached copy is never invalidated by a no-op adapter run.

This is why `render_feed` has a canonical form. Assert the property rather than assuming it — run
the command twice over the same input and compare bytes, including the signature. Ed25519 is
deterministic, so a differing signature means the payload differed, which is the failure this
test exists to catch.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement.

- **A publish produces a payload and a signature that `verify_and_parse` accepts.** Round-trip
  through the consuming half rather than asserting on the bytes alone — that proves the two
  halves agree, which is the point of building this one.
- **Two publishes over unchanged input are byte-identical**, payload and signature both.
- **A missing key refuses, and writes nothing.** Assert the directory is empty afterwards, not
  merely that an error was raised — a partial write is the failure mode.
- **No private key is committed.** The existing scan must still pass; add nothing that would need
  excluding from it.
- **A vendor with no changes publishes an empty array, not an error.** The feed's contract is a
  bare JSON array and *"the array is the whole contract"* — a vendor that shipped nothing has a
  feed, and it is empty.

No test calls a vendor API. Use committed `VendorChange` fixtures.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Process note

Terminals here are pinned to worktrees and two coordinators dispatch into the same pool. Stage
your own paths explicitly — **never `git commit -a`** — and report any files you did not create
that appear in `git status`.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

Feed payloads and signatures are bytes. Use `write_bytes` and do not encode through a text mode —
a signature is verified over exact bytes, and a line ending translated on this platform is a
signature that fails for a reason indistinguishable from forgery. Git already warns about CRLF on
every commit here; make sure your writes are not subject to it.

The suite is currently 1458 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: where the private key comes from and what happens without it, how you proved a no-op
republication is byte-identical, what the command writes and what it deliberately does not do,
which baseline lines you deleted, and the four gate results.

</details>

---

## M3-W56: measure test coverage, record it, and gate nothing

`task_0db46e143507` · created `2026-07-29 04:07:42` · status **completed**

### Result

{"completedBy":"term_b64d2f71-f51d-4c54-a60b-36cc381b4fdb","filesModified":["pyproject.toml","uv.lock",".github/workflows/ci.yml","docs/superpowers/specs/2026-07-29-sync-coverage-baseline.md"],"completedAt":"2026-07-29T04:18:41.154Z"}

<details><summary>Brief</summary>

M3-W56: measure test coverage, record it, and gate nothing

## Why this task exists

"Harden any module whose tests are thin" has been on this build's remaining-work list for a long
time and has never been acted on, for one reason: **nobody has measured which modules are thin.**
Two attempts to identify them used a proxy — counting how often a module's name appears in the
test tree — and the proxy was wrong. `src/sync/index/dependency_edits.py` looked like 187 lines
with a single test reference and actually has eleven tests, because its test file imports symbols
directly and never names the module.

That proxy failed in the direction that matters: it would have sent someone to harden a
well-tested module while a genuinely thin one went unnoticed.

`pytest-cov` is not installed. So the first deliverable is the measurement, and this repository
already has a rule about that shape of task —
`docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md`: *"The first deliverable is
measurement, not construction."*

## What this task is not

**Do not harden anything.** Not one module, not one test. Which module to harden is the decision
this measurement exists to inform, and taking it now would mean choosing before the evidence
exists — and would collide with the three other tasks that own most of `src/`.

**Do not add a coverage threshold, and do not fail CI on coverage.** The benchmark spec's rule is
general and it binds here:

> **do not invent a threshold.** A gate at an invented number either fires constantly and gets
> disabled, or never fires and provides false assurance.

Coverage is recorded, reviewed by a human, and reported with its denominator — the same treatment
tier B axes get. A percentage that gates a build is a percentage people write tests to satisfy
rather than to test something.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full. Note the toolchain rules: `uv` only, never
  Poetry, and `python` never `python3`.
- `docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` — "Gate tier A", why the lints run
  before the suite, and all of "Gate tier C".
- `.github/workflows/ci.yml` — the four gates and their order.
- `.claude/rules/test-discipline.md` — what this repository counts as a test worth having.

## Files you own

- Modify: `pyproject.toml` — to add `pytest-cov` as a development dependency, with `uv add`
- Modify: `uv.lock` — as a consequence of the above, not by hand
- Modify: `.github/workflows/ci.yml`
- Create: `docs/superpowers/specs/2026-07-29-sync-coverage-baseline.md`

**Forbidden — everything under `src/` and everything under `tests/`.** Three other tasks own most
of the source tree, and this task needs neither. If measuring requires a source change, that is a
finding to report rather than an edit to make.

Also forbidden: other files under `docs/superpowers/specs/`.

## What to produce

**A coverage run, and its numbers.** Line coverage per module across `src/sync`, from the default
suite. The e2e test stays deselected, as it is today — say so in the report, because a coverage
figure that quietly included a deselected test would be measuring something nobody runs.

**The document is the deliverable.** `docs/superpowers/specs/2026-07-29-sync-coverage-baseline.md`,
in normal prose, in the voice of the other specs. It must contain:

- **The overall figure and its denominator**, plus the exact command that produced it and the
  commit it was measured at. A number nobody can reproduce cannot be challenged.
- **The least-covered modules, ranked**, with line counts beside percentages. A 40% figure over
  20 lines and over 400 lines are different problems and the percentage alone hides which.
- **Which of those are thin for a reason.** This is the part that takes judgement rather than
  tooling. Some modules are legitimately uncovered: a vendor adapter's network path cannot be
  exercised because no test calls a vendor API; `static_verify` for Python returns `ok=False` on
  every path and has little to cover; error branches for conditions `CLAUDE.md` says not to guard
  against should not exist at all. Separate "thin and should not be" from "thin and correctly
  so", and say which is which.
- **A recommendation naming one module** to harden first, with the reason. One, not a list — a
  list is a way of not choosing.
- **What coverage does not tell you.** This repository has shipped five components that were
  fully covered and reachable from nothing. Line coverage would have called every one of them
  healthy. Say that plainly, because a coverage number arriving without that caveat will be
  trusted more than it deserves.

**A CI step that records and does not gate.** Add it after the existing gates, printing the
figure so a human reviewing a run can see it. It must not fail the build on any number.

## Test discipline

You are adding no tests, so `verification-before-completion` is satisfied differently: your
evidence is the reproducible command and the commit it ran at, both in the document.

Run the full suite before and after your dependency change and confirm the count is unchanged —
adding `pytest-cov` should alter no test's outcome, and if it does, that is a finding worth more
than the coverage numbers.

Use your own `SYNC_DSN` pointing at a database no other task is using; coverage runs the real
suite, which touches Postgres.

## Process note

Terminals here are pinned to worktrees and two coordinators dispatch into the same pool. Stage
your own paths explicitly — **never `git commit -a`** — and report any files you did not create
that appear in `git status`. This matters more than usual for `uv.lock`, which another task's
dependency change would also touch.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

The suite is currently 1468 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: the overall figure and its denominator, the one module you recommend hardening and why,
how many low-coverage modules you judged correctly thin, and the four gate results.

</details>

---

## M3-W57: give the observed-shape baseline a feeder, so the drift detector can...

`task_3de6c1f6e9b9` · created `2026-07-29 04:13:02` · status **dispatched**

<details><summary>Brief</summary>

M3-W57: give the observed-shape baseline a feeder, so the drift detector can fire

## The gap, verified in the code

`ObservedDriftDetector` is the detector `docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md`
calls the most valuable one Sync has:

> the vendor-change detector needs the vendor to publish. The production-error detector needs a
> failure to have already happened. This detector needs neither — it fires on shape divergence
> alone, before the first exception.

The spec records it as shipping against an empty baseline: *"nothing has fed Sentry payloads in,
so the detector runs and correctly finds nothing. That is the sample floor doing its job rather
than a defect."*

That has not changed, and the reason is now precise. `SentryShapeReader` and `DatadogShapeReader`
both write `observed_shape`. `scripts/dead_links_baseline.txt` lists both classes, and
`grep -rn "SentryShapeReader\|DatadogShapeReader" src/` returns only their own modules and the
`__init__.py` that re-exports them. **Neither is ever constructed.**

The `ingest` command is not the feeder and never was: `ingest_payload` folds OTLP spans into
`observed_call`, a different table answering a different question. So `observed_shape` has no
production writer at all, and the detector correctly finds nothing — permanently.

A caution before you trust the lint here: it matches bare names without resolving them, so a
method can look reached because an unrelated local variable shares its name. Both readers'
`ingest` methods left the baseline earlier for exactly that reason. Assert reachability with a
test rather than reading a clean lint as proof.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` — "The shape store" and its
  privacy rule, "The fourth detector", and the Sequencing table.
- `src/sync/signals/sentry/shapes.py` and `src/sync/signals/datadog/shapes.py` — both in full.
  The Datadog module imports `walk` and `ARRAY_ELEMENT` from Sentry rather than copying them, and
  its docstring explains why; do not undo that.
- `src/sync/cli.py`, the `ingest` command — the shape a command takes when it acts on a payload
  somebody else fetched, with no server and no port.
- `src/sync/detect/observed_drift.py`, especially `MIN_SAMPLES`.
- `scripts/dead_links_baseline.txt`, including its header.

## Files you own

- Modify: `src/sync/cli.py`
- Modify: `src/sync/signals/sentry/shapes.py`, `src/sync/signals/datadog/shapes.py` — only if
  wiring reveals a genuine defect; prefer reporting one
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**
- Create: `tests/test_shape_ingest_command.py`
- Modify: existing tests in `tests/` only where your change breaks them

**Forbidden, each owned by a live task or out of scope:** `src/sync/benchmark/`,
`src/sync/remediate/`, `src/sync/forge/`, `src/sync/mcp/`, `src/sync/core/`,
`src/sync/graph/schema.sql`, `src/sync/index/`, `pyproject.toml`, `.github/workflows/ci.yml`,
and `docs/superpowers/specs/`.

## What to build

A command that takes error-tracker payloads it is handed and folds them into `observed_shape`
through the readers.

**No server, no polling, no vendor API call.** The refusal of ingestion infrastructure still
stands, and `CLAUDE.md` forbids a vendor API in tests regardless. The command reads payloads from
a path or from standard input, the way `ingest` already does. If a deployment wants live Sentry
data it exports it and feeds it in; that is an operational choice and not this command's problem.

**Both readers reachable, keyed by source.** `observed_shape.source` distinguishes
`error-payload` from `replay` from `interceptor`, and the two readers are different sources of
the same kind. Whatever selects between them must not become vendor knowledge in `cli.py` — the
registry already established how that is avoided for vendor adapters, and the same argument
applies.

**The privacy rule is the one thing that must not bend.** From the spec:

> **Values are never recorded. Only shape.** … Record an enum value only when that value appears
> in the vendor's **published specification** … Free-form values — amounts, names, tokens,
> identifiers — are discarded at the observation boundary and never cross a process line.

The readers already enforce this. Your command must not add a path that stores a payload, logs
one, or writes anything the readers did not return. An error-tracker payload is the most
customer-sensitive input Sync touches — it is literally a captured production response.

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement.

- **A Sentry payload lands rows in `observed_shape` through the command.** Drive it from the
  command, not by constructing the reader — constructing it re-creates the situation this fixes.
- **A Datadog payload lands rows too**, keyed to its own source, so a command that only ever
  reaches one reader fails.
- **No free-form value survives.** Use a fixture carrying PII-shaped values — a name, an email, an
  amount, a token — and assert the stored rows contain paths and types only. The spec requires
  this test by name; make it non-vacuous by checking a value that would be easy to leak.
- **Re-ingesting the same payload converges.** Every stage is idempotent, and `observed_shape` has
  a natural key; a second run must not double `sample_count` for shapes it already saw, or must
  do so in exactly the way the natural key intends. Decide which is correct, say so, and assert
  it.
- **The detector can now fire.** Feed enough samples to clear `MIN_SAMPLES` with a shape that
  diverges from a fixture specification, and assert `ObservedDriftDetector` emits a finding. This
  is the point of the task: the detector has never produced one from real ingestion.
- **Below the floor it still says nothing.** So the previous test cannot be satisfied by removing
  the sample floor.

No test calls a vendor API. Fixtures are committed payloads.

Use your own `SYNC_DSN` pointing at a database no other task is using.

## Process note

Terminals here are pinned to worktrees and two coordinators dispatch into the same pool. Stage
your own paths explicitly — **never `git commit -a`** — and report any files you did not create
that appear in `git status`.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

Payloads are JSON read from disk or standard input. Pass `encoding="utf-8"` explicitly — real
error payloads carry user-supplied strings in any language, and on this machine the default is
cp1252, so this fails first against real customer data and never against a fixture.

The suite is currently 1490 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: how the command selects a reader without naming a vendor in `cli.py`, the first finding
`ObservedDriftDetector` produces from ingested shapes, what you decided about idempotence and
`sample_count`, which baseline lines you deleted, and the four gate results.

</details>

---

## M3-W58: build the labelled pair generator, the fallback the mining verdict le...

`task_f633b58b5474` · created `2026-07-29 04:13:04` · status **dispatched**

<details><summary>Brief</summary>

M3-W58: build the labelled pair generator, the fallback the mining verdict left standing

## Why this task exists

Binding precision and recall are the two benchmark axes
`docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` calls the ones that matter most, and
both need a labelled reference. The mining approach was investigated to a conclusion and
`docs/superpowers/specs/2026-07-29-sync-ground-truth-quality.md` returned **No**, on evidence:

- 117 commits read in full; 58% carry a `Co-authored-by` trailer naming a coding agent, 63% carry
  that or a bot author.
- Filtering to plausible human migrations left five commits, all read by hand, and **none was a
  migration** — a revert, an npm republication fix, a pin added where none existed, DEVLOG prose,
  a year typo.
- The healthy cohort does not migrate at all: the pinned file is touched one to seven times over
  a repository's whole life, almost all of it the commit that introduced Stripe. *"That is a
  population problem, not a search problem — pinning is what Stripe's versioning is for."*

The verdict names the way forward, and it is the one the benchmark spec had already reserved:

> synthetic mutation of real repositories, at the cost of realism

That cost is real and must be carried openly rather than argued away. This task builds the
generator; it does not build a scorer, and it does not claim the result is as good as a human
migration.

## Read first

- `CLAUDE.md` at the repository root. Binding, in full.
- `docs/superpowers/specs/2026-07-29-sync-ground-truth-quality.md` — the whole verdict, including
  its recommendation **not** to keep a mining harness warm.
- `docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` — "Ground truth without customers",
  the three named weaknesses, and all of "Gate tier C".
- `src/sync/benchmark/binding.py` — what a labelled reference has to look like to be scored. Its
  `BindingLabel` is the shape you are producing, and its docstring explains why precision and
  recall key their splits on different things.
- `src/sync/route/templates.py` — the deterministic edit primitives. A mutation is the inverse of
  a repair, and reusing this machinery is what keeps the two consistent.

## Files you own

- Create: `src/sync/benchmark/mutate.py`
- Modify: `src/sync/benchmark/__init__.py`
- Create: `tests/test_mutation_pairs.py`
- Create: `tests/fixtures/mutation/` and the fixtures inside it
- Modify: `scripts/dead_links_baseline.txt` — **deletions only**

**Forbidden, each owned by a live task or out of scope:** `src/sync/cli.py`,
`src/sync/signals/`, `src/sync/remediate/`, `src/sync/core/`, `src/sync/graph/`,
`src/sync/index/`, `src/sync/mcp/`, `src/sync/forge/`, `pyproject.toml`,
`.github/workflows/ci.yml`, `scripts/` other than the baseline, and `docs/superpowers/specs/`.

`src/sync/benchmark/axes.py` and `binding.py` are read-only for you: you are producing what they
consume, not changing what they compute.

## What to build

A pure function that takes a real repository tree, a `VendorChange`, and the call sites in that
tree, and returns a **labelled pair**: the mutated source that the change would break, plus the
ground-truth statement of which call sites are genuinely affected.

The label is the deliverable, not the mutation. A mutated tree with no label is a broken
repository; the label is what makes it a benchmark.

Four constraints.

**The mutation must be the inverse of a real change kind.** Take the kinds from oasdiff's
catalogue rather than inventing them, and start with the ones the decision table already routes:
a request property removed, a response property removed, a parameter renamed. A mutation nobody's
vendor would ever publish scores Sync against a world that does not exist.

**The label must be derived from the mutation, not from Sync.** This is the whole reason the
approach is not circular: you know which call sites you broke because you broke them. If your
label is computed by asking Sync's own binder which sites are affected, you have built a test
that Sync always passes. Say in the module docstring how the label is derived and why that
derivation cannot consult the binder.

**Both classes, not just the positive one.** Precision needs sites Sync flagged that were not
affected; recall needs sites that were affected and not flagged. So a generated repository must
contain call sites that the change genuinely does **not** break — a fixture where every site is
affected cannot measure precision at all.

**Realism is the stated cost, and it must be stated.** A synthetic mutation is a vendor change
applied mechanically to code that was written against the old contract. Real migrations are
messier: the human may restructure, rename, or work around. Put that in the module docstring as a
known bias, the way the mining document put survivorship and commit granularity in writing. A
benchmark whose bias is undocumented is worse than none — that is this repository's own standard.

## What this task does not do

**No scoring.** `compute_binding_accuracy` already exists and already takes labels; feeding it is
the next task and not this one.

**No corpus freeze, no CI step, no threshold.** Tier C is explicit: *"do not invent a threshold."*
Nothing you write goes into `.github/workflows/ci.yml`.

**No mining harness**, per the verdict's explicit recommendation. Do not build one "for
comparison".

## Test discipline

`CLAUDE.md` is binding: write the failing test, run it, watch it fail for the reason you expect,
then implement.

- **A generated pair breaks exactly the sites the label names.** Assert both directions: every
  labelled site is genuinely broken, and every broken site is labelled. One direction alone is
  satisfied by a label that names everything.
- **Unaffected call sites survive the mutation untouched.** This is what makes precision
  measurable; without it the negative class does not exist.
- **The mutation is deterministic.** The same input yields byte-identical output, so a score is
  comparable across runs. An unfrozen benchmark measures the benchmark.
- **The label does not consult the binder.** Assert structurally if you can — the module importing
  nothing from `sync.index` is the strongest form of this — and say in the test what it protects.
- **A change kind the generator does not support is refused, naming the kind**, rather than
  silently producing an unmutated tree that would score as a perfect miss for every binder.

Use your own `SYNC_DSN` even though this module should not touch the database.

## Process note

Terminals here are pinned to worktrees and two coordinators dispatch into the same pool. Stage
your own paths explicitly — **never `git commit -a`** — and report any files you did not create
that appear in `git status`.

## Before you commit

```
uv run pytest -q
uv run python scripts/lint_encoding.py src scripts tests
PYTHONIOENCODING=utf-8 uv run lint-imports
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

`lint-imports` must be run **unredirected** with `PYTHONIOENCODING=utf-8` set. Its reporter emits
emoji and on this machine a redirected run dies on a cp1252 encode error that looks exactly like
a contract violation but is not one.

You are reading and writing source files. Pass `encoding="utf-8"` explicitly on every one — a
real repository carries identifiers and comments in any language, and cp1252 is the default here.

The suite is currently 1490 passing. A test you did not write going red is a real signal — read
it before adjusting anything.

Commit with a Conventional Commits subject and a body in normal prose explaining why. Then
report: how the label is derived and why it cannot consult the binder, which change kinds you
support and which you refused, how a fixture contains both affected and unaffected sites, the
realism bias as you stated it, and the four gate results.

</details>

---
