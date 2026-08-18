# Build-versus-buy: the codebase technical census (2026-08-18)

The owner asked for real software-engineering information about the codebase on the Overview,
and whether open source already does it. Surveyed from knowledge, licenses stated:

| Project | What it does | License | Verdict |
|---|---|---|---|
| github-linguist | language detection, the industry `languages.yml` map | MIT (Ruby) | **SKIP as a dependency** — a Ruby runtime for an extension map; the map's *idea* taken at the size we need. Its data file is adoptable later if "other" grows too large |
| tokei / scc | fast LOC counting | MIT (Rust/Go binaries) | **SKIP** — a platform-specific binary to count newlines in files the indexer already reads |
| pygount | LOC in pure Python | BSD | **SKIP** — closest fit, still a dependency for `bytes.count(b"\n")` |
| cloc | LOC | **GPL-2** | **SKIP outright** — license-incompatible with Apache-2.0 distribution |
| onefetch | the repo summary card | MIT (Rust) | **STEAL-THE-IDEA** — the composition (languages, history, toolchain in one card), not the tool |

**The verdict that decided it:** every candidate is a dependency or a binary for work this
repository already pays for — the indexer walks the tree, `read_declared_dependencies` parses
the manifests, and git answers its own history. `sync.index.facts` is the zero-dependency
implementation: `git ls-files` as the file census (the repository's own ignore rules as the
authority), newline counts over bytes (never decoded — the cp1252 lesson), manifest-declared
dependencies through the same parse `sync intake` uses so two screens cannot disagree, and
git's own commit/contributor figures. Stored per repository in `codebase_facts`, computed with
the index pass so the census describes the same tree the call sites came from.
