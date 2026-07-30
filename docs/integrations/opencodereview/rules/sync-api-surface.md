#### Third-Party API Surface
- For any call to a third-party SDK client, call `sync_explain_call_site` with the file and line before
  commenting on it. Do not guess whether the API is current.
- If the response reports `known_changes`, report the change and the affected field. Name the vendor version
  the change lands in.
- Read `binding_source` on the finding, not on the envelope: a response can mix rungs, and the
  envelope carries a value only where every finding behind it agrees. Say `static` is derived rather
  than observed; say `observed` was confirmed by a client span; say `unresolved` means the binding
  exists and its route was not resolvable. `unattributed` is not a rung — it means the row predates
  the column, so say the provenance is unknown rather than weak.
- Do not comment on a third-party call whose `known_changes` is empty. Silence is the correct output.
