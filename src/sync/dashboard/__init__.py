"""Read-only local dashboard over the graph and the remediation checkpoints.

Task 2 adds `build_app` here. This package imports from `sync.core` and
`sync.graph` only, plus the checkpointer library -- never `sync.remediate`:
it reads checkpoint rows, not graph code.
"""
