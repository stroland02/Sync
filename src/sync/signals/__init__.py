"""Vendor adapters: the packages that turn a vendor's published artifacts into changes.

One subpackage per vendor, and `registry.py` is the only place that knows which id maps to
which of them. Nothing outside this package names an adapter class -- `CLAUDE.md` makes that a
non-negotiable, and the entry point named one of them in two places until a second vendor made
the cost visible.

Deliberately no re-exports here. An eager `from sync.signals.registry import ...` would make
importing any one vendor's module pull in every other vendor's, along with the whole
change-detection path underneath them, which is the coupling a per-vendor split exists to
avoid. A caller imports `sync.signals.registry` directly.
"""
