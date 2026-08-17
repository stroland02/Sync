"""Durable run resumption and review-loop turn progression.

M10: When a pull request is out for review and a human or CI event arrives (review comment,
changes_requested, or check_run failure), `resume_durable_run` loads the persisted
LangGraph checkpoint, structures model feedback, increments turn tracking, and executes
the next remediation cycle to push follow-up commits to the existing PR branch.
"""

from __future__ import annotations

from typing import Any

from sync.forge.webhook import (
    CheckRunEvent,
    PullRequestReviewCommentEvent,
    PullRequestReviewEvent,
    format_review_feedback,
)
from sync.remediate.state import RunState


def resume_durable_run(
    graph,
    checkpointer,
    thread_id: str,
    event: PullRequestReviewEvent | PullRequestReviewCommentEvent | CheckRunEvent | Any,
    store=None,
) -> RunState:
    """Resume a parked remediation run with incoming review or CI feedback.

    1. Loads the latest checkpoint for `thread_id` from `checkpointer`.
    2. Formats actionable feedback instructions for the patch model.
    3. Increments turn counter, resets attempt loop flags, and re-invokes the graph.
    4. Graph generates follow-up patch, runs verification, and pushes to the PR branch.
    """
    config = {"configurable": {"thread_id": thread_id}}
    current_state: RunState = {}
    if hasattr(graph, "get_state"):
        state_snapshot = graph.get_state(config)
        if state_snapshot and state_snapshot.values:
            current_state = dict(state_snapshot.values)

    if not current_state:
        tuple_state = checkpointer.get_tuple(config)
        if tuple_state is not None:
            checkpoint_dict = getattr(tuple_state, "checkpoint", {})
            current_state = dict(getattr(tuple_state, "values", None) or checkpoint_dict.get("channel_values", {}))

    if not current_state:
        raise ValueError(f"no checkpoint found for thread {thread_id}")


    # Format feedback from the incoming event
    if hasattr(event, "body") or isinstance(event, (PullRequestReviewEvent, PullRequestReviewCommentEvent, CheckRunEvent)):
        feedback_text = format_review_feedback(event)
    elif isinstance(event, str):
        feedback_text = event
    else:
        feedback_text = str(event)

    turn = current_state.get("turn", 1) + 1

    # Prepare updated state for the new turn
    resumed_input: RunState = {
        **current_state,
        "turn": turn,
        "feedback": feedback_text,
        "review_feedback": feedback_text,
        "patch": None,
        "verify_ok": False,
        "static_fatal": False,
        "outcome": "running",
        "parked_reason": "awaiting_review",
        "static_attempts": 0,
        "ci_attempts": 0,
    }

    # Re-invoke graph with updated state on the same thread
    final_state: RunState = graph.invoke(resumed_input, config=config)
    return final_state
