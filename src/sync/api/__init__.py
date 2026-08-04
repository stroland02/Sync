"""The HTTP transport for the operator console.

Thin Starlette routes over `GraphSurface`. The transport holds no logic: a request maps to a
surface call and a return value to JSON. The read-only constraint that keeps the console safe
lives in `tests/test_api_routes.py` as a grep assertion rather than in a docstring, because a
docstring cannot stop a mutation from shipping.
"""

from sync.api.app import create_app

__all__ = ["create_app"]
