# Build the demo's layout, exactly — and take nothing else from it

**Owner ruling, 2026-08-18.** *"The demo that was created with the Claude design is the perfect
structure of what we want in terms of what each of the pages look like … let's put 100 percent effort
into the demo design, get the code from the demo design and implement the page layout."*

**And the boundary, given by the owner immediately after, which is the load-bearing half:**
*"I am just talking about the layout and the visual UI components of the demo that are really good.
Other than that we don't want to copy incorrect false information. We just want the code for the UI
itself to be implemented."*

## What this changes about the mock's authority

`2026-08-08-console-mock-to-build.md` says **"the mock is the lowest authority in the room."** That
stands for everything it *says* and is now **reversed for everything it draws.**

| Aspect of the mock | Authority | Why |
|---|---|---|
| **Layout, composition, component structure** | **Primary.** Build it exactly | The owner's ruling. This is the thing being asked for |
| Colour, spacing, radius, type | Already ours | Measured: the mock's literal OKLCH values *are* `web/src/index.css`'s. Colour work is approximately zero |
| **Prose, labels, numbers, claims** | **Lowest, unchanged** | Its facts are fixtures. `tests/test_console_honesty_sentences.py` remains the arbiter and porting a screen never shortens a protected sentence to match a drawing |
| Hierarchy | **The specification's, as amended by the owner** | See below |

**The hierarchy point the owner restated:** *"we still want to maintain that hierarchy of the
independent variable which is the code base and then it all pertains and trickles down to each other
page."* That is the same ruling as `M0-W315`/`M0-W316` — **the codebase is the independent variable,
the Overview is the codebase, and every other page is scoped beneath it.** The mock predates that
ruling and draws a Fleet root. **Take the mock's layout for each screen; do not take its root.**

## What is actually extractable, measured rather than assumed

`docs/console-mock/index.html` is **99,700 bytes of real markup**, not an image export:

- **10 `<section>` elements** — the ten screens, in one file
- **1 `<aside>`** — the sidebar
- **1 `<nav>`**, **140 `<div>`**
- **33 `grid-template` declarations** and **91 `flex` rules** — the layout, literally
- **Zero `class=` attributes.** Every style is inline, which is *better* for extraction: each
  element carries its own computed intent with nothing to resolve against a stylesheet
- `support.js` (71 KB) drives the `<x-dc>` custom element wrapper; it is tooling, not design

Twelve stills in `docs/console-mock/screens/` map to the screens: `01-fleet`, `02-codebase`,
`03-vendor`, `04-signals`, `05-binding-surface`, `06-finding`, `07-workflow`, `08-pull-request`,
`09-detectors`, `10-settings`, `11-drawer`, `12-palette`.

## The method: extract the skeleton, keep our data

For each screen, in its owning lane:

1. **Open the `<section>` for that screen in `index.html`** and the matching still in `screens/`.
2. **Extract the layout skeleton** — the grid definitions with their column tracks and gaps, the
   flex arrangements, the nesting order, which regions sit beside which. **This is the deliverable.**
3. **Port it into the React feature** as structure, with our components inside it.
4. **Fill it with our real data**, from the routes the API actually serves. Where the mock shows a
   number, ours shows what the payload holds — or the absence sentence, if it holds nothing.
5. **Delete nothing protected.** The twenty-four honesty sentences survive the port; if the mock's
   layout has no room for one, the layout gets the room.
6. **Measure, do not eyeball.** `getComputedStyle` in Chrome per `console-dev-loop.md`. The mock is
   a document that renders headless, so the built screen and the drawing can be compared directly —
   the visual eval already does exactly this.

## What must not come across

- **Its facts.** Every number in it is a fixture, and `docs/console-mock/README.md` says which.
- **Its prose**, where it paraphrases a protected sentence.
- **Its root level**, superseded by the owner's codebase-as-independent-variable ruling.
- **Any score, dot, pulse or health figure**, if one appears — refused independently of the mock.

## Per-lane assignment, against the existing UI split

| Lane | Screens to extract |
|---|---|
| **B** | `07-workflow`, `11-drawer`, and the `<aside>` sidebar |
| **C** | `06-finding`, `08-pull-request`, `05-binding-surface` |
| **F** | `01-fleet` and `02-codebase` — **merged into one Overview**, per the hierarchy ruling |
| **G** | `10-settings`, `03-vendor` |
| **A** | `04-signals`, `09-detectors`, `12-palette` |

**The mock renders in a browser.** Open it, do not only read it — `docs/console-mock/index.html`, and
`demo.mp4` for how the screens move between each other.
