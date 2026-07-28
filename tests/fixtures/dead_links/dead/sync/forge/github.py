"""The caller that keeps `GraphStore` and `record` alive, and reaches nothing else."""

from sync.graph import GraphStore


def open_pr(store: GraphStore) -> None:
    store.record({"opened": True})
