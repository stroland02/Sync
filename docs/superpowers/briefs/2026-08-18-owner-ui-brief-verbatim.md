# The owner's UI direction, verbatim, with the image for each point

**Read this instead of a summary. Open every image named below before you build anything.**

The console lane has been working from a coordinator's prose rendering of these messages, and the
owner's verdict on the result is that *"it doesn't look much different from what was originally
developed."* That is a signal about the brief, not only about the build: **a summary of a screenshot
is not a screenshot**, and nine surfaces were described in words when the owner supplied pictures.

Every quotation below is the owner's own wording. Every image path is a file in this repository.
**Open the file. Do not work from the quotation alone.**

---

## 1. Sidebar structure — reference: the Orca sidebar

> *"I would like to reference how Orca beautifully constructs the sidebar and we should implement the
> same sort of UI components and structure that they have"*

> *"remove the scroll bar from the sidebar and then also move the button that compacts to the top next
> to the console text"*

> *"clean up the sidebar so it's more compact"*

> *"you don't need to have a header above each page as they already describe what they do"*

Structure to take: one top row carrying the wordmark, the collapse control and history controls
together; flat icon-plus-label rows; quiet section labels with their actions inline on the same line;
nested disclosure with the child count on the parent row; right-aligned metadata; a pinned bottom
utility bar; tight row rhythm.

**Refused: its status dots.** `CLAUDE.md` forbids them by name.

---

## 2. Sidebar behaviour — reference: `docs/superpowers/references/direction/supabase-*.png`

> *"I really like how Supabase's sidebar only expands when you're hovering over the sidebar and then it
> automatically minimizes once you drag off the sidebar we should implement a similar feature to that
> our sidebar as well"*

---

## 3. The Overview — reference: `direction/supabase-01-project-overview-empty.png` and `direction/supabase-02-project-overview-populated.png`

> *"here for what I like is that we have [an] area with fields that shows all the different dashboards
> of information which we should integrate[;] it shows a clean different integration pop ups that we
> can add and it shows that this is the stroland02's project workspace as we can implement to specific
> workspaces in our own platform"*

> *"I like how this picture shows a cool dashboard of all the different endpoints calls and nodes that
> are running we should implement similar dashboards and then I also like the globe dashboard[.] in
> this area we should come up with a useful dashboard for a code base that is like a very important
> visualization"*

**And the ruling that governs this screen, given separately:**

> *"The selection of the code base should be completely within settings or the sidebar[;] there should
> not be a listing of all the different code bases in the overview"*

> *"Instead the overview should be all the findings dashboards and pertained information to that
> specific code base so this changes a lot of what you'll see but this is very important because the
> overview should pertain to a specific code base"*

**Refused: the `STATUS — Healthy` tile with its green dot cluster.** That is a composite health
figure.

---

## 4. Large record sets — reference: `direction/supabase-03-table-editor.png`

> *"I love how the editor shows a table format like you're in an Excel sheet and this should be used
> for us when we're dealing with large amounts of datasets[,] for example our calls and endpoints that
> [have] hundreds of different records and IDs and information[;] we should have the page be set up to
> this format"*

---

## 5. Indexing visualisation — reference: `direction/supabase-05-schema-visualizer.png`

> *"I think this page would be a great example of our code indexing[.] So as we index a code base we
> should actually show the information or the indexing in a visual way just like this where the page
> is a really cool immersive grid that shows all the indexing information so it can be visually
> understood by a user"*

---

## 6. Triage over large sets — reference: `direction/supabase-14-security-advisor.png`

> *"I really like this because this looks like a professional way where we can implement triage
> organization when we're dealing with large data sets[.] This should be implemented in a way when
> we're dealing with a lot of information like signals and [end]points[,] traces[,] logs[,] things of
> that nature"*

---

## 7. Traces and queries — reference: `direction/supabase-17-query-performance.png`

> *"Here is an example of trace abilities and how they should be organized and formatted so we can
> actually see the data and functionality of the queries in real time"*

---

## 8. Vendors and API services — reference: the Supabase integrations screen

> *"Here is another example of how we should set up our vendors and API services integrations where we
> automatically detect what vendor or service it is so we can create a professional page that shows
> the company logo and their information and all the metrics and all the information that we research
> as a service to self maintain the APIs and figure out the most up to date information with those
> APIs"*

---

## 9. Log tables — reference: the Supabase logs screen

> *"Here is another great example of how to portray log tables when we're dealing with a lot of data"*

Left filter rail with time range, type and level each showing **counts beside them**; a timeline
histogram above the table; dense monospace rows.

---

## 10. The Solution Workflow — reference: the Superlog incident view, both states

> *"we need to make some serious improvements to the solution workflow as I'll provide a reference
> example of what it should look like[.] it's pretty similar but it looks like we need to include more
> this is where the human interaction actually takes place with the coding agents to either review or
> improve or change the final product of what they're working on"*

The two states supplied were the **Findings** tab (summary, estimated impact, root cause, code with
`file:line`, agent run status, a Restart control) and the **Activity** tab (turn-by-turn transcript,
tool calls as structured cards, and **a reply box: "Reply to the investigation — request PR changes,
explain the issue, add context…"**).

**Refused, and named by hand in `interface-originality.md`: the `confidence 9/10` scalars.** Render
the provenance rung instead.

---

## 11. Settings

> *"We also need to add actual settings within the settings page as it's just listing a bunch of
> information"*

---

## 12. Style, and the standing instruction

> *"we want to CREATE A CLEAN ORGANIZED PROFESSIONAL DASHBOARD for each code base or workspace[,] use
> the reference pictures[,] code[,] and all the pertained information to think about what's important
> to be added to these pages and thinking about grouping information in certain pages so everything is
> organized"*

> *"I think Supabase does a great job of building out the dashboard overview layout and we should try
> to implement subtle coloring in simple features so it's not too distracting but it gives the UI
> enough style to look modern and advanced"*

> *"right now UI is very bland and at a certain point we want to start implementing like themes"*

> *"Review and compare every one of these PDFs and pictures to understand what a professional layout[,]
> dashboards and organization should look like and compare it to what we have and then adjust it to be
> similar to the references"* — `docs/superpowers/references/direction/`

> *"Please go through every one of these screenshots as well and think about what's important to add to
> create professional pages"* — `docs/superpowers/references/screenshots/`

> **"all of this needs to be implemented before wednesday"**

---

## How to work from this

**Open the images.** Every one named above is in this repository. The previous pass worked from prose
about them and produced something the owner says is not visibly different from where it started.

**`interface-originality.md` still governs**, and its 2026-08-06 amendment is the relevant half: the
conventions of the form are learnable from anything — a fact tile grid, a filter rail, a typed table,
a node canvas, a tabbed triage header, a hover-expanding rail. What is refused is the rendering, the
copy, the iconography, and **any claim their screen makes that our data cannot support**. Three of
those refusals are listed above at the screens where they are tempting.
