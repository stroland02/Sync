"""Assembly of the remediation graph.

`await_ci` is the reason this is a graph and not a loop: a CI run takes minutes,
and a worker restart during that wait must not lose the run. The checkpointer
persists state at every node, so a restarted run resumes where it stopped.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from sync.remediate import nodes
from sync.remediate.state import RunState


def build_graph(store, adapter, remediator, forge, checkpointer):
    builder = StateGraph(RunState)

    builder.add_node("locate", nodes.make_locate(store))
    builder.add_node("prepare", nodes.make_prepare(adapter))
    builder.add_node("patch", nodes.make_patch(remediator))
    builder.add_node("static_verify", nodes.make_static_verify(adapter))
    builder.add_node("push_branch", nodes.make_push_branch(forge))
    builder.add_node("await_ci", nodes.make_await_ci(forge))
    builder.add_node("open_pr", nodes.make_open_pr(forge))
    builder.add_node("abandon", nodes.make_abandon(store, forge))

    builder.add_edge(START, "locate")

    builder.add_conditional_edges(
        "locate",
        nodes.route_after_locate,
        {"prepare": "prepare", "abandon": "abandon"},
    )

    builder.add_conditional_edges(
        "prepare",
        nodes.route_after_prepare,
        {"patch": "patch", "abandon": "abandon"},
    )

    builder.add_conditional_edges(
        "patch",
        nodes.route_after_patch,
        {"static_verify": "static_verify", "patch": "patch", "abandon": "abandon"},
    )

    builder.add_conditional_edges(
        "static_verify",
        nodes.route_after_static,
        {"patch": "patch", "push_branch": "push_branch", "abandon": "abandon"},
    )

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

    builder.add_edge("abandon", END)

    return builder.compile(checkpointer=checkpointer)
