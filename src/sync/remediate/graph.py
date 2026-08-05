"""Assembly of the remediation graph.

`await_ci` is the reason this is a graph and not a loop: a CI run takes minutes,
and a worker restart during that wait must not lose the run. The checkpointer
persists state at every node, so a restarted run resumes where it stopped.

That same persistence is why `forge=None` removes nodes rather than disabling them.
`push_branch`, `await_ci` and `open_pr` are the only nodes that reach a remote, and every
one of them is a call on the `Forge` this function is handed. A guard inside them, or an
`interrupt_before`, would leave them in the compiled graph and therefore in the checkpoint:
a run halted at `push_branch` resumes into a push the moment any caller holding a forge
picks up its thread. A node that is not there cannot be resumed into.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from sync.remediate import nodes
from sync.remediate.corpus import make_recorder
from sync.remediate.serde import with_sync_types
from sync.remediate.state import RunState


# What a run says when it verified a patch and the assembly it was run by has nowhere to
# push it. `cli.py` renders it verbatim to an operator, so it names the cause in terms of the
# run's configuration: "not pushed" alone reads as a failure and sends an operator looking for
# one, and a node name is an internal that appears on no surface they can see.
_NO_FORGE = "this run was configured without a forge, so it cannot reach a remote"


def build_graph(store, adapter, remediator, forge, checkpointer, catalogue=None):
    # Built from the store this already receives, so no caller learns a new argument and no
    # run can be configured with the corpus recording silently switched off. Every node that
    # takes it is a place an attempt ends -- three of them with no forge, one more with one.
    record = make_recorder(store)

    remote = forge is not None

    builder = StateGraph(RunState)

    # The catalogue is passed rather than read off the remediator, which keeps it a
    # private of a module this one does not own. One object serves both: `locate`
    # decides the tier from it, and the cascade narrows its tiers with the same table.
    builder.add_node("locate", nodes.make_locate(store, catalogue))
    builder.add_node("prepare", nodes.make_prepare(adapter))
    builder.add_node("patch", nodes.make_patch(remediator, record))
    builder.add_node("static_verify", nodes.make_static_verify(adapter))
    # Between the typechecker and CI, which is where the spec puts it: it exercises runtime
    # behaviour against the new response shape, which `tsc` cannot, and it costs a sandboxed
    # process rather than a CI run. The store is passed for the observed baseline the mock
    # prefers over the specification.
    builder.add_node("replay", nodes.make_replay(store))
    if remote:
        builder.add_node("push_branch", nodes.make_push_branch(forge))
        builder.add_node("await_ci", nodes.make_await_ci(forge))
        builder.add_node("open_pr", nodes.make_open_pr(forge, record))
    builder.add_node("report", nodes.make_report(None if remote else _NO_FORGE, record))
    # `abandon` is built with whatever forge there is, which with none is none. It deletes a
    # branch only when the state carries one, and only `push_branch` writes that -- so with
    # no push node there is no branch and nothing to delete.
    builder.add_node("abandon", nodes.make_abandon(store, forge, record))

    builder.add_edge(START, "locate")

    builder.add_conditional_edges(
        "locate",
        nodes.route_after_locate,
        {"prepare": "prepare", "abandon": "abandon"},
    )

    builder.add_conditional_edges(
        "prepare",
        nodes.route_after_prepare,
        {"patch": "patch", "report": "report", "abandon": "abandon"},
    )

    builder.add_conditional_edges(
        "patch",
        nodes.route_after_patch,
        {"static_verify": "static_verify", "patch": "patch", "abandon": "abandon"},
    )

    # The one place a router's decision and its destination differ, and deliberately. A passing
    # typecheck still decides "push_branch" -- the name is the decision, the path that ends in
    # a push -- and that path now begins with replay. Renaming the decision instead would have
    # reached into `sync.mcp.propose`, which reads the same string to establish that a patch is
    # verified without ever building a node to push from.
    builder.add_conditional_edges(
        "static_verify",
        nodes.route_after_static,
        {"patch": "patch", "push_branch": "replay", "abandon": "abandon"},
    )

    # A replay failure is a patch that is wrong, so it re-enters the same retry loop a failed
    # typecheck does. A replay that could not run is not a failure and does not: it reaches
    # the push path carrying the fact that this run was not replay-verified.
    #
    # With no forge that path ends at `report`, for the same reason `static_verify` already
    # decides "push_branch" and reaches `replay`: the decision names the verdict on the patch,
    # and where the verdict goes is this file's to say.
    builder.add_conditional_edges(
        "replay",
        nodes.route_after_replay,
        {
            "patch": "patch",
            "push_branch": "push_branch" if remote else "report",
            "abandon": "abandon",
        },
    )

    if remote:
        builder.add_conditional_edges(
            "push_branch",
            nodes.route_after_push,
            {"await_ci": "await_ci", "abandon": "abandon"},
        )

        builder.add_conditional_edges(
            "await_ci",
            nodes.route_after_ci,
            {"patch": "patch", "open_pr": "open_pr", "abandon": "abandon"},
        )

        builder.add_conditional_edges(
            "open_pr",
            nodes.route_after_open_pr,
            {"end": END, "abandon": "abandon"},
        )

    builder.add_edge("report", END)
    builder.add_edge("abandon", END)

    # Callers build the saver, so this is the one place every one of them passes
    # through. A saver that reaches `compile` with langgraph's stock serialiser
    # resumes runs on a permission langgraph says it will withdraw.
    return builder.compile(checkpointer=with_sync_types(checkpointer))
