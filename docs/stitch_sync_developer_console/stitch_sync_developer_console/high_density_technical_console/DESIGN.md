---
name: High-Density Technical Console
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#393939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1b1b1b'
  surface-container: '#20201f'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353535'
  on-surface: '#e5e2e1'
  on-surface-variant: '#bbcabe'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#313030'
  outline: '#869489'
  outline-variant: '#3d4a41'
  surface-tint: '#51df9c'
  primary: '#60eca8'
  on-primary: '#003822'
  primary-container: '#3ecf8e'
  on-primary-container: '#005434'
  inverse-primary: '#006c45'
  secondary: '#c8c6c6'
  on-secondary: '#303030'
  secondary-container: '#474747'
  on-secondary-container: '#b6b5b4'
  tertiary: '#ffc7ae'
  on-tertiary: '#561f00'
  tertiary-container: '#ffa072'
  on-tertiary-container: '#78350f'
  error: '#FA4B4B'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#71fcb6'
  primary-fixed-dim: '#51df9c'
  on-primary-fixed: '#002112'
  on-primary-fixed-variant: '#005233'
  secondary-fixed: '#e4e2e1'
  secondary-fixed-dim: '#c8c6c6'
  on-secondary-fixed: '#1b1c1c'
  on-secondary-fixed-variant: '#474747'
  tertiary-fixed: '#ffdbcc'
  tertiary-fixed-dim: '#ffb694'
  on-tertiary-fixed: '#351000'
  on-tertiary-fixed-variant: '#76330d'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353535'
  surface-main: '#1C1C1C'
  surface-card: '#171717'
  border-subtle: '#2E2E2E'
  border-muted: '#232323'
  text-primary: '#EDEDED'
  text-secondary: '#A0A0A0'
  success: '#3ECF8E'
  warning: '#F5A623'
  info: '#2081E2'
typography:
  headline-lg:
    fontFamily: Manrope
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Manrope
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
  label-xs:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  space-1: 4px
  space-2: 8px
  space-3: 12px
  space-4: 16px
  space-6: 24px
  space-8: 32px
  gutter: 16px
  sidebar-width: 240px
---

## Brand & Style

The design system follows a **High-Density Technical** aesthetic, optimized for power users and developers managing complex data infrastructures. It prioritizes information density and functional clarity over decorative elements.

The style is a blend of **Modern Corporate** and **Developer-Centric Minimalism**, characterized by:
- A "Dark Mode First" philosophy using deep zinc and charcoal surfaces.
- High-contrast emerald accents to highlight primary actions and successful states.
- A rigid adherence to a 4px baseline grid to ensure alignment and systematic spacing.
- Subdued, low-contrast borders that define structure without creating visual noise.
- Professionalism evoked through the pairing of a balanced geometric sans-serif with a functional monospace.

## Colors

The palette is anchored in a monochromatic dark range to minimize eye strain during long sessions. 

- **Primary Emerald (#3ECF8E):** Used sparingly for primary buttons, active toggles, and "success" indicators.
- **Surface & Backgrounds:** The main dashboard uses `#1C1C1C`. Sidebars and secondary containers use `#171717` to create subtle depth.
- **Borders:** `#2E2E2E` is the standard for separators and component outlines, ensuring components feel integrated into the background.
- **Status Colors:** These are muted yet vibrant—high enough in saturation to be legible against dark backgrounds but desaturated enough to maintain a professional, utility-first feel.

## Typography

The typographic hierarchy distinguishes between branding/navigation and data-heavy content.

- **Headings:** Use **Manrope** for a refined, modern feel in page titles and section headers.
- **UI & Body:** **Inter** is the workhorse for all interface labels, inputs, and general reading. It provides maximum legibility at small sizes.
- **Data & Metadata:** **JetBrains Mono** is utilized for code blocks, IDs, timestamps, and technical labels. This helps users quickly distinguish between "system data" and "interface text."
- **Scale:** Sizes are kept intentionally small (mostly 13px-14px) to support the high-density layout requirements of a technical dashboard.

## Layout & Spacing

This design system utilizes a **Fixed-Fluid Hybrid** grid based on a strict 4px atomic unit.

- **The Grid:** Use a 12-column layout for main content areas. Sidebars are fixed at 240px (or 64px when collapsed).
- **Density:** High density is achieved by using 8px (`space-2`) or 12px (`space-3`) for internal component padding and 16px (`space-4`) for container margins.
- **Responsiveness:** On desktop, use a fixed sidebar with a fluid content area. On tablets and mobile, the sidebar transitions to a drawer, and page margins reduce from 24px to 16px.

## Elevation & Depth

Depth is conveyed through **Tonal Layering** and **Low-Contrast Outlines** rather than traditional shadows.

- **Stacking:** The background is the lowest layer (`#1C1C1C`). Modals and popovers sit on a slightly lighter surface (`#232323`) to indicate elevation.
- **Borders:** Every container, card, and input uses a 1px solid border (`#2E2E2E`). This replaces shadows as the primary method of separation.
- **Active States:** Elements that are "pressed" or active are indicated by a change in border color to the Primary Emerald or a slightly lighter gray, rather than a change in depth or shadow.

## Shapes

The shape language is "Soft" yet disciplined. All standard controls (buttons, inputs, checkboxes) use a **6px (0.375rem)** corner radius to feel precise.

- **Small Components:** Buttons, chips, and inputs use `rounded-md` (6px).
- **Large Components:** Cards and main dashboard panels can use `rounded-lg` (8px).
- **Strictness:** Do not use fully rounded pill shapes unless for specific status badges where visual distinction is mandatory.

## Components

- **Buttons:** Primary buttons use a solid `#3ECF8E` background with black text for high contrast. Secondary buttons use a transparent background with a `#2E2E2E` border and white text.
- **Input Fields:** Use a dark fill (`#171717`) with a subtle border. Focus state should change the border color to Primary Emerald.
- **Chips/Badges:** Small, rectangular with 6px radius. Use the muted status colors (e.g., desaturated red background with bright red text) for errors/warnings.
- **Lists & Tables:** Use high-density rows (32px or 40px height). Use `border-b` at `#232323` to separate items.
- **Cards:** Cards should be "flat" with a 1px border. Avoid drop shadows; use a background color of `#171717` to separate from the main canvas.
- **Monospace Labels:** Any technical ID (e.g., `user_id`, `api_key`) must be wrapped in a code-style label using JetBrains Mono at 12px.