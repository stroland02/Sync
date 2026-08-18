"""Sync Index: AST and static analysis adapters for customer repositories."""

from sync.index.codebase import CodebaseIndexReport, discover_codebase_vendors, index_codebase
from sync.index.python_lang import PythonAdapter
from sync.index.typescript import TypeScriptAdapter

__all__ = [
    "CodebaseIndexReport",
    "PythonAdapter",
    "TypeScriptAdapter",
    "discover_codebase_vendors",
    "index_codebase",
]
