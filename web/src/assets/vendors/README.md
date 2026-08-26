# Vendor marks

Drop a vendor's SVG here as `<vendor_id>.svg` — the same id `generated-vendors.yaml` uses — and
`VendorMark` renders it instead of the generated monogram. Nothing else to wire: the lookup is a
build-time `import.meta.glob`, so a file that is present is used and a file that is absent falls
back. No network call, at build time or at render.

**Owner ruling, 2026-08-25**, superseding the monogram-only rule of 2026-08-19. Two of the three
objections that removed logos are answered by bundling: the Clearbit fetch told a third party which
integrations each customer watched, and it made the console's appearance depend on a network it
does not control. A committed file does neither.

The third objection stands and is the reason this directory ships empty: **a vendor's logo is their
trademark.** Using one to identify an integration you connect to is ordinary nominative use, but it
is the owner's call per vendor, not something to fill in speculatively. Add the marks you have the
right to ship.

## Requirements

- **SVG only**, named exactly `<vendor_id>.svg` — `stripe.svg`, `openai.svg`, `google-cloud.svg`.
- **Square-ish viewBox.** The mark renders into a 24px rounded slot; a wide wordmark will letterbox.
- **`currentColor` where the mark is monochrome**, so it takes the console's ink. A mark with its
  own brand colours keeps them — the slot behind it goes neutral in that case.
- **No raster inside the SVG.** An embedded PNG defeats the point and bloats the bundle.

## Attribution

Add a line to `web/NOTICE` naming the vendor and where the mark came from, the way the vendored
Supabase components are attributed. A mark in the tree with no provenance is the problem this
directory was created to avoid.
