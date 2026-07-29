#### Third-Party API Surface
- For any call to a third-party SDK client, call `sync_explain_call_site` with the file and line before
  commenting on it. Do not guess whether the API is current.
- If the response reports `known_changes`, report the change and the affected field. Name the vendor version
  the change lands in.
- If `binding_source` is `static`, say that the mapping is derived rather than observed.
- Do not comment on a third-party call whose `known_changes` is empty. Silence is the correct output.
