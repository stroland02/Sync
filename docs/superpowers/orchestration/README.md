# Workflow scripts worth re-running

Scripts are otherwise written to a session directory and die with the session. These are here
because the work they do is repeatable and the prompts took real effort to get right.

Run one with `Workflow({ scriptPath: "docs/superpowers/orchestration/<file>.js" })`.

## `screen-rebuilds-wave-1.js`

Rebuilds **Findings, Overview and Runs** into locked multi-pane compositions, one agent per screen
in its own git worktree. Its contract is the important part and was tuned against a real failure:
it opens by naming the reskin-versus-rebuild distinction, carries the eighteen-of-twenty-one
measurement so the agent knows what wrong looks like, names the landed chassis primitives so they
are reused rather than reinvented, and ends with *"if your screen still renders one scrolling
column when you are done, you have not done the task."*

**Wave 2 is the same file with the screen table swapped** for Finding detail
(`self_healing_incident_inspector`), Workflow (`ai_driven_incident_resolution_workflow`) and Graph
(`code_graph_dependency_explorer`). Their rulings are in the master brief §4.

**Three per wave, never six.** Four parallel builders were dispatched on 2026-08-25 and three hit
the account's session limit mid-run and returned nothing (`CI-W639`).

The agents leave their worktrees dirty and commit nothing. The coordinator reviews each diff,
applies it, and gates: `tsc`, `vitest --maxWorkers=4`, `lint`, `build`, `pytest`. Default vitest
parallelism has produced spurious worker-start timeouts in this repository — use `--maxWorkers=4`.

## `plan-reconciliation.js`

Reads every plan and spec across four agents and reconciles what they mandate against what the
console actually is. Run it when the register and the tree might have drifted, or when a claim
that something is "done" needs testing rather than trusting.

It is told explicitly not to trust checkboxes: `CI-W607` found a plan reading 0-of-74 while 89 of
its items had shipped. It weighs commit references and status headers instead, and must say when
it cannot tell.

Its 2026-08-26 run produced the audit recorded in the master brief §6a, including the finding that
`web/CLAUDE.md` had been routing every console edit to the retired mock.
