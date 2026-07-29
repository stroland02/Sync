"""Vendor adapters: the packages that turn a vendor's published artifacts into changes.

One subpackage per vendor, and `registry.py` is the only place that knows which id maps to
which of them. Nothing outside this package names an adapter class -- `CLAUDE.md` makes that a
non-negotiable, and the entry point named one of them in two places until a second vendor made
the cost visible.

Not every vendor needs a subpackage. `generated/` serves any vendor whose SDK was produced by a
generator that commits a manifest naming the specification it worked from, so those vendors are
entries in `generated-vendors.yaml` rather than modules here. That is the shape coverage is
meant to take: a hand-written subpackage is for a vendor whose SDK symbol scheme has to be
resolved, and everything else is configuration. `registry.py` resolves a coded adapter before a
configured one, so a configuration entry can widen the set and never replace a subpackage.

Two modules here serve no vendor at all. `intake.py` reads a customer's manifest and asks which
declared dependencies a tier could serve, which is a question about the registry rather than
about any one vendor -- so it names none, and reaches the two things it needs (which package a
vendor declares, and which repository a configured vendor is registered against) through
`registry.py`, the only module allowed to know.

`reachability.py` orders that answer by the call sites the indexer actually found, because a
dependency no line of code calls is not exposure and a coverage list is not a priority list. It
names no vendor either, and it reaches nothing at all: both counts arrive as arguments, which is
what keeps a report about what is on disk from quietly requiring a database.

Deliberately no re-exports here. An eager `from sync.signals.registry import ...` would make
importing any one vendor's module pull in every other vendor's, along with the whole
change-detection path underneath them, which is the coupling a per-vendor split exists to
avoid. A caller imports `sync.signals.registry` directly.
"""
