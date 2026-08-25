---
name: Sync Console
colors:
  surface: '#131413'
  surface-dim: '#131413'
  surface-bright: '#393938'
  surface-container-lowest: '#0d0e0d'
  surface-container-low: '#1b1c1b'
  surface-container: '#1f201f'
  surface-container-high: '#292a29'
  surface-container-highest: '#343534'
  on-surface: '#e4e2e0'
  on-surface-variant: '#bccabe'
  inverse-surface: '#e4e2e0'
  inverse-on-surface: '#30312f'
  outline: '#86948a'
  outline-variant: '#3d4a41'
  surface-tint: '#59de9d'
  primary: '#65eaa8'
  on-primary: '#003822'
  primary-container: '#45cd8e'
  on-primary-container: '#005333'
  inverse-primary: '#006c45'
  secondary: '#c6c7c5'
  on-secondary: '#2f3130'
  secondary-container: '#454746'
  on-secondary-container: '#b5b5b3'
  tertiary: '#5feba7'
  on-tertiary: '#003822'
  tertiary-container: '#3dce8d'
  on-tertiary-container: '#005333'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#77fbb8'
  primary-fixed-dim: '#59de9d'
  on-primary-fixed: '#002112'
  on-primary-fixed-variant: '#005233'
  secondary-fixed: '#e2e3e0'
  secondary-fixed-dim: '#c6c7c5'
  on-secondary-fixed: '#1a1c1b'
  on-secondary-fixed-variant: '#454746'
  tertiary-fixed: '#71fcb6'
  tertiary-fixed-dim: '#51df9c'
  on-tertiary-fixed: '#002112'
  on-tertiary-fixed-variant: '#005233'
  background: '#131413'
  on-background: '#e4e2e0'
  surface-variant: '#343534'
  surface-card: '#181a19'
  surface-popover: '#1b1d1c'
  ink-primary: '#edefee'
  ink-muted: '#bcbdbc'
  ink-secondary: '#989a99'
  border-low: oklch(0.95 0.001485 159 / 7.51%)
  border-control: '#787a79'
  status-good-ink: '#85e0ba'
  status-good-bg: '#00311d'
  status-warning-ink: '#f2af48'
  status-warning-bg: '#4a2900'
  status-serious-ink: '#fd9565'
  status-serious-bg: '#391a0b'
  status-critical-ink: '#fa8880'
  status-critical-bg: '#541c15'
typography:
  display:
    fontFamily: Manrope
    fontSize: 46px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.045em
  figure:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.04em
  page-header:
    fontFamily: Manrope
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.04em
  section-header:
    fontFamily: Manrope
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.02em
  emphasis:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.02em
  body:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '450'
    lineHeight: 20px
  meta:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '450'
    lineHeight: 16px
  mono-data:
    fontFamily: ui-monospace, monospace
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  furniture:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.025em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  grid-unit: 4px
  field-gap: 4px
  row-padding: 8px
  panel-gap: 32px
  page-frame: 40px
  sidebar-expanded: 240px
  sidebar-collapsed: 48px
  topbar-height: 48px
---

## Brand & Style

The design system follows a **High-Density Utility** style, specifically optimized for developer operations and automated API remediation. It prioritizes information density and technical evidence over decorative aesthetics, drawing heavy inspiration from the Supabase "Substrate" architecture.

The interface is strictly **Dark Mode**, utilizing a "Contrast Floor" philosophy where every text element must meet or exceed a 5.05:1 contrast ratio to ensure readability in low-light, high-stress engineering environments. The personality is disciplined, deterministic, and authoritative. 

Visual depth is achieved through **Tonal Layering** and hairline "rings" rather than traditional soft shadows, creating a structured environment that feels like a physical piece of laboratory equipment. Motion is treated as a functional tool: high-frequency interactions (row hovers, sidebar toggles) utilize zero-latency transitions to maximize perceived performance.

## Colors

The palette is built on a generative OKLCH model using a brand hue of 159 (Emerald). It is designed to be purely functional, using specific "Ink" levels for typographic hierarchy and "Surface" steps for layout depth.

### Functional Roles
- **Neutral Surface Ramp:** Uses `#131413` for the base canvas and `#181a19` for primary cards. Depth is stacked using subtle lightness increments rather than shadows.
- **Status States:** Functional states (Good, Warning, Serious, Critical) must always be accompanied by an icon and text. They are never used for data identity (e.g., vendor types), only for health outcomes.
- **Interactive:** The Primary color (`#45cd8e`) is reserved for focus rings, primary CTAs, and active nodes. It maintains an 8.1:1 contrast ratio for immediate accessibility.
- **Data Series:** A strict categorical 8-slot palette is provided for charts, optimized for color vision deficiency (CVD) separation.

## Typography

The system uses a 7-step functional ramp. A global font weight of **450** is used for normal body text to ensure crisp rendering and "ink-trapping" on high-contrast dark backgrounds.

### Rules of Engagement
- **The UI Floor:** No text may be smaller than 12px.
- **Monospace Priority:** All verbatim data—including API endpoints, commit hashes, JSON paths, and Trace IDs—must use the `mono-data` role.
- **Furniture:** Category labels and table headers use the `furniture` style (uppercase with increased tracking) to distinguish UI structure from user data.
- **Tabular Numbers:** All numeric values in tables and stat tiles must use `font-variant-numeric: tabular-nums` to ensure vertical alignment.

## Layout & Spacing

This design system uses a **fixed grid architecture** anchored on a 4px baseline unit. Vertical space is treated as the primary currency; density is favored over generous whitespace to keep maximum telemetry data above the fold.

### Chassis Dimensions
- **Page Frame:** A constant 40px padding (`page-frame`) wraps the main content chassis.
- **The Sidebar:** Toggles instantly between 240px and 48px. Content must reflow horizontally without animation to support rapid context switching.
- **The Row Currency:** Standard table rows and list items utilize an 8px vertical padding (`row-padding`).

### Density Levels
- **High-Density:** Used for logs and data grids. Vertical padding is reduced to 4px.
- **Standard:** Used for settings panels and dashboard grids. Uses a 16px internal padding.

## Elevation & Depth

Elevation is conveyed through **Tonal Layers** and **Low-Contrast Outlines**. In this dark-only environment, depth is additive—surfaces get lighter as they "rise" toward the user.

- **Background (`#131413`):** The base level for the entire application.
- **Surface Step 1 (`#181a19`):** Used for cards and primary containers. Separated from the background by a 1px `border-low` outline.
- **Surface Step 2 (`#1b1d1c`):** Reserved for occluding content like dropdowns and modals. These require a `shadow-float` (hairline ring + a 72% opacity black soft shadow) to stand out against lower layers.
- **State Overlays:** Instead of borders, hover and active states use alpha-blended overlays (3% to 5% opacity) of the primary foreground color.

## Shapes

The shape language is **Soft** and disciplined. 

- **Controls:** Buttons, inputs, and chips use a 6px (`0.375rem`) radius.
- **Surfaces:** Cards and panels use an 8px (`0.5rem`) radius.
- **Selections:** Indicators for active sidebar items or scope markers use sharp or 4px rounded corners to maintain a technical, "tabbed" feel.

## Components

### Buttons & Inputs
- **Buttons:** 32px standard height. Tactile interaction: on `active` state, buttons translate 1px downward with no transition duration.
- **Inputs:** Strictly 1px border using `border-control` (`#787a79`) to ensure 3:1 contrast against the card surface.

### Data Tables
- **Headers:** Use `furniture` typography with a subtle background tint.
- **Density:** 36px default row height. Every row includes a zero-latency hover state (`bg-muted`).
- **Cells:** ID and Endpoint columns must use `mono-data`.

### Status Indicators
- **Rule:** A status can never be a color alone. It must include a Lucide icon (e.g., `CircleCheck`, `TriangleAlert`) and a text label.
- **Styling:** Use the `status-*-bg` for the background and `status-*-ink` for the text/icon to ensure 5:1 contrast.

### Cards
- **Structure:** Cards feature a `section-header` and a 1px top border or full-border ring.
- **KPI Tiles:** Display a `furniture` label above a `figure` value.

### Trace Logs
- **Container:** Uses the `neutral-color-hex` (`#131413`) background to create a "sunken" effect relative to the card surface.
- **Typography:** Strictly 12px monospace.