# M13 — Dynamic Visuals, Remotion Animations & Live Workflow Telemetry

> **Governing Milestone:** `M13` (Dynamic Workflow Telemetry & Visual Animations)  
> **Reference Architecture:** [DeepSeek Harness (open-source live agent workflow & progress inspection)](https://github.com/deepseek-ai/deepseek-harness) & Remotion programmatic animations  
> **Status:** Registered & Planned

---

## 1. Goal & Motivation

Sync's core operator experience must not feel like a static report. When a remediation run is locating call sites, running tree-sitter AST codemods, executing TypeScript compiler checks, replaying synthetic test exchanges, or waiting on forge CI gates, the operator needs immediate visual clarity into:
1. **What Sync is doing right now** (live node execution, pulsing state indicators, streaming progress).
2. **What the model/graph is thinking and reasoning** (structured step-by-step telemetry, AST strategy selection, compiler error feedback loops).
3. **Animated contract migration diffs & replays** (Remotion-powered programmatic visualizations of API breaks and automated patch transformations).

---

## 2. Inspiration: DeepSeek Harness Architectural Patterns

The open-source [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) establishes state-of-the-art developer ergonomics for agentic systems:
- **Active Execution Stream**: Real-time feedback showing current step, execution phase, and tool invocations without manual page refreshes.
- **Thinking Process Inspection**: Clear disclosures displaying intermediate deductions (e.g. why `rename-param` was chosen over `replace-object`, why a compiler error TS2353 was rejected).
- **Dynamic Node State Transitions**: Nodes dynamically shift through `QUEUED` → `RUNNING` (with live pulse & elapsed timer) → `PASSED` / `REJECTED` / `PARKED` (`await_ci`).

---

## 3. Scope & Phased Deliverables

### Phase 1: Live Workflow Telemetry & Streaming States (`/findings/:id/workflow`)
- **Dynamic Pulse & Execution Indicator**: Replace static narrative badges with animated live pulse rings for active nodes (`RUNNING`, `LINTING`, `TYPECHECKING`).
- **Thinking & Decision Logs**: Expandable reasoning stream showing the node's internal deductions (routing strategy, AST replacements, compiler output).
- **Elapsed Live Timers**: Active running ticker for in-flight CI runs and verification passes.

### Phase 2: Remotion API Contract & Migration Animations
- **Programmatic Motion Diffs**: Remotion compositions rendering step-by-step transformations from old breaking vendor signatures (`max_tokens: 1024`) to verified patches (`max_completion_tokens: 1024`).
- **Graph Replay Flow**: Animated token flow diagram demonstrating live request replay against mock exchanges.

### Phase 3: Codebase-First Information Architecture Integration
- **Real-Time Codebase Status**: Codebase overview cards reflecting live remediation states and active pull request updates without page reloads.

---

## 4. Quality Invariants & Verification
- **Honesty Preservation**: Animations and live indicators represent actual DB checkpointer states; an idle run is never faked as active.
- **Test Coverage**: All state transitions covered by Vitest suites (`node-sequence.test.tsx`, `timeline.test.ts`).
- **Performance**: Zero overhead when idle; smooth CSS keyframe pulses and lightweight SVG telemetry visuals.
