# Committed commit payloads

Captured verbatim on 2026-07-29 from `gh api repos/{owner}/{repo}/commits/{sha}`, unedited.
Public data from public repositories, and unedited on purpose: a trimmed payload is a payload
whose classifier was tested against a shape GitHub does not send.

| fixture | source | what it carries |
|---|---|---|
| `agent_trailer_pin_only.json` | `ceterisparibus75/application-immobili-re` | A `Co-authored-by: Claude ...` trailer, and a diff that changes the pinned version and nothing else |
| `agent_trailer_non_ascii_message.json` | `kohuttomas-lab/kohut-partners` | The same trailer signal with a Slovak subject line — `pripnúť stripe napevno` |
| `no_trailer_pin_only.json` | `anternetai/anternet` | No trailer, no bot identity, and still only the pin changed |
| `no_trailer_pin_and_call_sites.json` | `sufyan-rana/rana-leathers` | No trailer, and the diff reaches source files as well as the pin |
| `rate_limited.json` | hand-written | What the API returns when the token is exhausted: a message, no commit |

The last one is hand-written because a real rate-limit response cannot be captured on demand,
and it is the fixture that matters most. A reader that answers "this commit changed nothing"
to an exhausted token has turned a measurement failure into a finding, which is the distinction
`scripts/mine_stripe_migrations.py` was built around and the one this instrument inherits.

The two `no_trailer_*` fixtures are labelled for what the *signals* say, not for what the
commits are. `2026-07-29-sync-ground-truth-quality.md` reads both by hand and concludes neither
is a migration across a breaking release — which is the finding, and is why the classifier
reports signals rather than verdicts.
