# Lane D Handoff Report: Signals, Adapters, Intake & Arbitrary Codebase Indexing

**Date:** 2026-08-18  
**Lane:** Lane D (Signals, Adapters, Intake — M5)  
**Status:** Completed & Retired. 100% published to `origin/main`.

---

## 1. Master Ledger of Units Delivered by Commit

All units are landed, tested, and verified on `main`:

| Unit | Commit | Focus | Deliverables & Behavioral Guarantees |
|---|---|---|---|
| **`M5-W310`** | `a07cf0f` | `B157` Visual Deprecations Table | Live catalogue parser for vendor model & parameter deprecations table. |
| **`M5-W311`** | `c31f415` | TypeScript Wrapper Attribution | Tracked `unbound_import_paths` in `TypeScriptAdapter` to identify internal wrappers (e.g. `lib/stripe.ts`) rather than emitting false zero findings. |
| **`M5-W312`** | `f976a40` | Python Wrapper Attribution | Implemented `unbound_import_paths` in `PythonAdapter` for parity with TypeScript. |
| **`M5-W313`** | `ef78cbb` | Intake Reason Precision | Handled byte-order marks (`utf-8-sig`) and detailed `UnicodeDecodeError` / missing manifest reporting. |
| **`M5-W314`** | `aabaee3` | Arbitrary Codebase Indexing | Built `index_codebase` in `src/sync/index/codebase.py` supporting multi-language AST walking, TSX/JSX parsing, and vendor discovery across uncalibrated repositories. |
| **`M5-W315`** | `c10368e` | Relative Boundary & Fallback Adapter | Fixed absolute `p.parts` bug skipping `.cache/` checkouts; created `_FallbackIndexingAdapter` enabling zero-traceback runs without pre-staged cache specs. |
| **`M5-W316`** | `32a2d2d` | Monorepo Subpackages & Precision | Recursive subpackage manifest discovery (`package.json`, `pyproject.toml`, `requirements.txt`) + narrowed OpenAI prefixes to eliminate Tailwind CSS false positives. |
| **`M5-W317`** | `ac8765f` | Package Root Index Export | Exported `index_codebase`, `CodebaseIndexReport`, and `discover_codebase_vendors` at package root `sync.index`. |

---

## 2. Learnings from Indexing Untuned Codebases (The Wednesday Demo Path)

During live testing against uncalibrated wild repositories (`shadcn-ui/taxonomy`, `stripe-samples/subscription-use-cases`, `charmbracelet/bubbletea`, and all 5 corpus fixtures), several critical failure modes were uncovered and solved:

### 1. Broad Literal Prefixes Match Tailwind CSS Classes
- **Problem**: `OPENAI.prefixes` previously included bare `"text-"` (intended for legacy models like `text-davinci-003`, `text-embedding-ada-002`). When indexing React/Next.js codebases (e.g. `shadcn-ui/taxonomy`), the indexer treated generic Tailwind CSS utility classes (such as `"text-sm text-muted-foreground"`, `"text-2xl font-bold"`, `"text-gray-600"`) as OpenAI models, producing over 50 false-positive call sites.
- **Resolution**: In `src/sync/signals/deprecations/adapter.py`, narrowed `OPENAI.prefixes` to specific model family prefixes: `("text-davinci", "text-curie", "text-babbage", "text-ada", "text-embedding-", "text-search-", "text-similarity-", "text-moderation-", ...)`. This eliminates 100% of Tailwind false positives while preserving complete coverage for all real OpenAI model deprecations.

### 2. Absolute Path Segment Exclusion Skips Checkouts
- **Problem**: `_source_files` in both `TypeScriptAdapter` and `PythonAdapter` previously filtered excluded directories via `any(part in skip_dirs for part in p.parts)` with `skip_dirs = {".cache", "build", "dist", ...}`. When a target repository resided inside `.cache/corpus/...` or any path containing `build/`, the indexer skipped 100% of the repository's files and silently reported 0 call sites.
- **Resolution**: Exclusions are now strictly checked relative to the repository root: `p.relative_to(root).parts[:-1]`.

### 3. Missing Staged Specifications on Clean Clones
- **Problem**: When `index_codebase` was run without pre-staged `.cache/specs` artifacts, `StripeAdapter` raised `TypeError: StripeAdapter.__init__() missing 2 required positional arguments: 'spec_dir' and 'symbol_map_path'`.
- **Resolution**: Added `_FallbackIndexingAdapter` in `src/sync/index/codebase.py`. Even if no cached OpenAPI specification or symbol map exists on disk, the indexer falls back to structural AST extraction and maps SDK call sites mechanically without crashing.

### 4. Monorepos with Subdirectory Manifests
- **Problem**: In repositories structured as monorepos or multi-sample directories (e.g. `stripe-samples/subscription-use-cases` with `fixed-price-subscriptions/server/nextjs/package.json`), root intake saw 0 dependencies and declined language matching.
- **Resolution**: `discover_codebase_vendors`, `TypeScriptAdapter._read_manifest`, and `PythonAdapter._read_manifests` now scan nested package manifests across subdirectories when the root manifest is absent or does not declare the vendor.

---

## 3. What is Open & What is NOT Known

### What is Open:
1. **Dynamic Client Instantiations**: The indexer relies on static AST patterns (e.g. `const stripe = new Stripe(...)` or `import { stripe } from '@/lib/stripe'`). Highly dynamic patterns (e.g. `const client = makeClient('stripe')` or runtime reflection) are not resolved.
2. **Additional Language Adapters**: Unindexed languages (Go, Rust, Java, Ruby, C#) produce clean zero-finding reports (`languages=()`, `vendors=()`, `call_sites=()`, 0 tracebacks). Concrete AST indexers for these ecosystems remain future work.
3. **Python Literal Model Extraction**: AST-grep scans `.ts`/`.tsx`/`.js`/`.jsx` for AI model deprecation literals. Python literal model scanning is structured similarly but not yet enabled for `.py` files.

### What is NOT Known:
1. **Very Large Monorepos (>100k files)**: AST walking on standard projects (<1,000 files) completes in <1s. For enterprise monorepos with hundreds of thousands of files, indexing will require parallel AST worker processes or ripgrep pre-filtering.
2. **Heavily Obfuscated or Bundled Customer Code**: Minified/bundled production artifacts in source directories should be excluded via standard `dist`/`build`/`out` ignore rules; unbundled generated code may result in unindexed wrapper warnings.

---

## 4. Verification Record

- **Test Suite**: 163 tests passing across `tests/test_codebase_index.py`, `tests/test_typescript_index.py`, `tests/test_python_index.py`, `tests/test_dependency_intake.py`, `tests/test_deprecations.py`, `tests/test_literal_index.py`.
- **Linters**: `lint_encoding.py`, `lint_dead_links.py`, `test_import_boundary.py` pass 100% clean.
- **Main State**: Clean tree, 0 unmerged paths, fully synchronized with `origin/main`.
