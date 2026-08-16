# Four directory repositories: vendor coverage and hosting

Audited 2026-08-04 against primary sources. Every claim below is labelled VERIFIED (primary source
read this session), REPORTED (secondary source), or INFERENCE (my reasoning from the evidence).

## 1. What these references actually are

Four of the most-starred curation repositories on GitHub, each a single enormous hand-maintained
Markdown file with a contribution process bolted around it: `public-apis/public-apis` lists free
public APIs, `awesome-selfhosted/awesome-selfhosted` lists self-hostable software,
`ripienaar/free-for-dev` lists SaaS free tiers, and `trimstray/the-book-of-secret-knowledge` lists
tools, manuals and shell one-liners. None of them is a library, a service, or a dataset Sync could
depend on at runtime; they are indexes intended for a human to read and then go elsewhere. Their
value to Sync is therefore entirely in what they point at, and in one case
(`awesome-selfhosted`) in the *data pipeline built beside the list* rather than the list itself.

## 2. What Sync should adopt

### 2.1 The APIs.guru OpenAPI Directory, which is what `public-apis` is not

This is the single finding worth carrying forward. `public-apis` cannot prioritise vendors for Sync
(argued in section 3), but a genuinely machine-readable API directory exists and answers a large
part of the same question.

- `https://api.apis.guru/v2/metrics.json` returns, VERIFIED this session:
  `numSpecs: 3992`, `numAPIs: 2529`, `numEndpoints: 108837`, `numProviders: 677`, plus a
  per-provider spec count (`azure.com: 1829`, `googleapis.com: 464`, `amazonaws.com: 286`,
  `twilio.com: 44`, `github.com: 21`).
- Per-provider metadata is served at `https://api.apis.guru/v2/{provider}.json`. VERIFIED: the
  Stripe entry carries `added: 2017-11-14`, `updated: 2023-03-06`, `info.version: "2022-11-15"`,
  `openapiVer: "3.0.0"`, `swaggerUrl`, `swaggerYamlUrl`, and — the field that matters most —
  `info.x-origin: [{format: openapi, url:
  https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.yaml, version: "3.0"}]`.
- VERIFIED: the Twilio entry decomposes into 51 separate API entries keyed
  `twilio.com:twilio_verify_v2`, `twilio.com:twilio_messaging_v1` and so on, each with its own
  `added` date and its own `x-origin` URL into `twilio/twilio-oai`.
- Repository: `https://github.com/APIs-guru/openapi-directory`, CC0-1.0, 4,522 stars, last push
  2026-04-20 (VERIFIED via the GitHub API).

Three things Sync should take from it, in decreasing order of confidence:

**Take `x-origin.url` as a vendor-to-canonical-spec index.** This is a machine-readable mapping from
a vendor domain to the repository or URL where that vendor publishes its own OpenAPI document. That
is precisely the input `sync.signals.<vendor>` needs before an adapter can be written, and it is the
one field here that does not decay, because it names a location rather than caching a document.
Where it lands: a one-off ingestion producing a candidate table for vendor selection, feeding the
adapter registry at `src/sync/signals/registry.py`; it is not a runtime dependency.

**Take the per-API `added` dates as a crude versioning-discipline signal.** A provider that appears
as 51 separately versioned surfaces with staggered `added` dates (Twilio) versus one that appears as
a single date-versioned surface (Stripe, `version: "2022-11-15"`) is telling you something real
about how it versions, and it is readable without opening a browser. INFERENCE: this is a weak
signal on its own and a useful tiebreaker between two otherwise equal candidate vendors.

**Do not take the cached specs as current.** VERIFIED and important: the APIs.guru Stripe spec was
last updated 2023-03-06 and pins `2022-11-15`, while `stripe/openapi` itself was pushed 2026-08-03.
Every one of the 51 Twilio entries reads `updated: 2023-04-20` against `twilio/twilio-oai` pushed
2026-07-30. The `metrics.json` blob claims `thisWeek: {added: 9, updated: 437}`, which I could not
reconcile with those per-entry dates — INFERENCE: the weekly churn is concentrated in the Azure and
Google families and the long tail is effectively frozen. Sync must fetch specs from `x-origin`, never
from `api.apis.guru/v2/specs/...`. This matters directly because `sync.signals.oasdiff` diffs spec
pairs, and diffing a three-year-stale cached spec would manufacture a wall of false vendor changes.

### 2.2 The `awesome-selfhosted-data` pattern: a curated list with a real schema behind it

`awesome-selfhosted` looks like the other three at its root — VERIFIED: `README.md`, `non-free.md`,
`_static/`, nothing else. But the list is *generated*. The source of truth is a sibling repository,
`awesome-selfhosted/awesome-selfhosted-data` (VERIFIED to exist; last push 2026-08-04), which holds
one YAML file per project under `software/` (VERIFIED: 256 files returned in the first API page,
`0-a.d..yml`, `2fauth.yml`, `gitea.yml`, …), plus `platforms/`, `tags/`, and `licenses.yml`.

VERIFIED, `software/gitea.yml` in full shape: hand-written fields `name`, `website_url`,
`description`, `licenses`, `platforms`, `tags`, `source_code_url`, `demo_url`; and machine-written
fields `stargazers_count: 57194`, `updated_at: '2026-08-03'`, `archived: false`,
`current_release: {tag: v1.27.1, published_at: '2026-07-27'}`, and a `commit_history` map of monthly
commit counts (`2026-07: 211`, `2026-08: 20`).

The tool that writes those fields is `hecat` (`https://github.com/nodiscc/hecat`). VERIFIED from its
README: importers `markdown_awesome` and `shaarli_api`; processors `software_metadata` ("Enrich
software project metadata from GitHub and GitLab APIs (stars, last commit date...)"), `awesome_lint`,
`url_check`, `download_media`, `archive_webpages`; exporters `markdown_singlepage`,
`markdown_multipage`, `html_table`.

What Sync should adopt is the *shape*, not the tool. The pattern is: a hand-maintained YAML record
per entity, an automated processor that stamps freshness metadata onto it from an upstream API, a
linter that refuses malformed records, and a rendered Markdown/HTML view generated from the data
rather than edited. That is exactly the correct structure for a vendor-adapter catalogue: the
adapter author writes the judgement fields, a scheduled job stamps `spec_last_changed`,
`releases_in_last_90_days`, `archived` onto the record, and the human-readable coverage table on the
operator console is rendered from it. Where it lands: alongside `src/sync/signals/registry.py`, and
M4's console gets a generated coverage view instead of a hand-edited one.

`commit_history` as a *monthly bucketed count* rather than a single last-commit date is the specific
detail worth stealing. INFERENCE: for Sync's purposes the analogous series is spec-changes-per-month
per vendor, which is the number that predicts whether an adapter will earn its maintenance cost. A
single "last changed" timestamp cannot distinguish a vendor that changes weekly from one that
changed once last Tuesday after two dormant years.

### 2.3 Hosting: the three configurations that actually fit

Sync is a Python 3.12 service, a Postgres 16 instance, a static Vite build, and — the part that
disqualifies most free tiers — a pipeline that clones customer repositories, runs `npm`/`pnpm`
installs and `tsc` as subprocesses, and needs persistent disk and long-running processes. All prices
below are VERIFIED from the vendor's own page on 2026-08-04 unless marked otherwise.

**Option A — Hetzner VPS running the existing `docker compose` stack, plus Cloudflare Pages for the
frontend. This is the recommendation.**

- Hetzner CX22: 2 vCPU, 4 GB RAM, 40 GB disk, 20 TB traffic, 1 IPv4, **€3.79/month**
  (`https://www.hetzner.com/pressroom/new-cx-plans/`). CX32 is 4 vCPU / 8 GB / 80 GB at €6.80.
- Caveat, VERIFIED: `https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/`
  records a price reset effective 15 June 2026 08:00 CEST that moved CAX11 from €4.49 to €5.99 and
  CX23 from €3.99 to €5.49, with the CCX series roughly doubling to tripling (CCX13 €15.99 → €42.99).
  CX22 does not appear in that table. **Could not verify** the current CX22 order price against a
  live order page; treat €3.79 as the press-release figure and re-check before committing.
- Cloudflare Pages free plan: **$0**, "unlimited bandwidth", "unlimited static requests",
  "unlimited sites" (`https://pages.cloudflare.com/`); limits are 500 builds/month, 1 concurrent
  build, 20-minute build timeout, 20,000 files per site, 25 MiB per asset, 100 custom domains per
  project (`https://developers.cloudflare.com/pages/platform/limits/`).
- What it limits: you operate Postgres yourself, including backups and the major-version upgrade. No
  managed failover. INFERENCE: for a solo self-funded project whose database is a pipeline's
  working store rather than a system of record for customer data, this is the right trade — and the
  repo already runs Postgres 16 in Docker (`CLAUDE.md`, port 5433), so the deployment is the
  development setup with a different compose file.
- All-in: roughly **€4–7/month**.

**Option B — Fly.io for the Python service, Neon for Postgres, Cloudflare Pages for the frontend.**

- Fly.io has **no free allowance for new customers** (`https://fly.io/docs/about/pricing/`); the
  legacy Hobby allowance survives only for existing accounts. Smallest `shared-cpu-1x` 256 MB is
  $0.0028/hour, about **$2.02/month**; volumes $0.15/GB-month provisioned; egress $0.02/GB in North
  America and Europe.
- Neon free plan: **$0**, 0.5 GB storage per project, 100 CU-hours per project per month, up to 100
  projects, 10 branches per project, autoscaling to 2 CU, **scale-to-zero after 5 minutes** idle, and
  compute suspends when the monthly limit is hit (`https://neon.com/pricing`). First paid tier
  (Launch) is usage-priced at $0.106/CU-hour plus $0.35/GB-month storage.
- Postgres 16 is supported: VERIFIED that Neon offers 14, 15, 16, 17 and 18 for new projects
  (`https://neon.com/docs/postgresql/postgres-version-policy`), with **no in-place major upgrade** —
  moving majors means a new project and a data migration.
- What it limits: 0.5 GB is small for a graph store that accumulates `vendor_change`,
  `binding` and `migration_outcome` rows, and scale-to-zero adds a cold start in front of every
  pipeline stage. INFERENCE: this configuration fits a preview or demo environment well and the
  production pipeline poorly.
- Fly's own managed Postgres is the honest managed floor and it is not cheap: Basic (shared-2x,
  1 GB) **$38/month**, Starter (shared-2x, 2 GB) $72, storage $0.28/GB-month
  (`https://fly.io/docs/mpg/`). VERIFIED on the same page: the default distribution is **Postgres 16**.

**Option C — Railway, for the case where one bill and one dashboard is worth paying for.**

- VERIFIED (`https://railway.com/pricing`): Free plan $0 with $1 of monthly usage credit, capped at
  1 vCPU / 0.5 GB and 1 replica; Hobby **$5/month including $5 of usage**, 48 vCPU / 48 GB ceiling,
  6 replicas; Pro $20/month including $20 usage. Rates beyond credits: CPU $0.00000772/vCPU-second,
  memory $0.00000386/GB-second, volumes $0.00000006/GB-second (≈ $0.155/GB-month), egress $0.05/GB.
- REPORTED (secondary aggregators, not Railway's own page): a small app plus managed Postgres lands
  at roughly $10–15/month all-in, and larger database instances push it to $20–40. Treat as an
  order-of-magnitude estimate only.
- What it limits: the $5 sticker is a minimum spend, not a price. A pipeline that runs `npm install`
  and `tsc` is CPU-spiky by construction, and CPU is billed per second — INFERENCE: Railway is the
  option most likely to surprise you on a month when a customer repository is large.

## 3. What to deliberately skip

**Skip `public-apis` for vendor prioritisation. It carries none of the signal Sync needs.**

This is a judgement, and here is the evidence behind it. VERIFIED from
`scripts/validate/format.py`: the table schema is exactly five columns — title, description, auth,
HTTPS, CORS. VERIFIED from the rendered README, first category:

```
API | Description | Auth | HTTPS | CORS
|:---|:---|:---|:---|:---|
| [AdoptAPet](https://www.adoptapet.com/public/apis/pet_list.html) | Resource to help get pets adopted | `apiKey` | Yes | Yes |
```

There is no OpenAPI column, no changelog column, no versioning column, no SDK column, and no
last-verified date. The validator (VERIFIED, `format.py`) checks alphabetical order, spacing, a
100-character description cap, capitalisation, an allow-list for auth and CORS values, and a minimum
of three entries per category — that is, it validates *formatting*, not *facts*. `links.py` checks
that URLs resolve. So the only automated guarantee is that an entry is well-punctuated and its link
is not dead.

The content itself is not the content Sync needs either. The categories are Animals, Anime, Cat
Facts, Games & Comics; the list's purpose is hobby projects, not commercial API dependencies. The
vendors whose breakage Sync sells against — Stripe, Twilio, Sentry, Datadog, the ones already under
`src/sync/signals/` — are largely paid APIs that a free-API list is structurally uninterested in.
Data quality is what you would expect from 454,355 stars and 1,618 open issues: one of the first
eight rows I read is malformed, carrying a trailing empty column (`| Daily cat facts | No | Yes | No | |`).

Cost of adopting it anyway: you would have to open each candidate's documentation by hand to
discover whether it publishes an OpenAPI document at all, which is the first question and the one
the list does not answer. That is the entire cost of the exercise, so the list saves nothing. Use
APIs.guru's `x-origin` index instead (section 2.1), which answers that first question directly for
677 providers.

**Skip Render's free tier for anything that holds state.** VERIFIED (`https://render.com/docs/free`):
free Postgres databases "expire 30 days after creation", one per workspace, 1 GB, no backups, with a
14-day grace period before deletion; free web services get 750 instance-hours per workspace per
month and spin down after 15 minutes of inactivity, have no persistent disk, and "Render might
restart a Free web service at any time". Cost of adopting: a guaranteed data-loss event on day 30,
and a pipeline whose first request after idle pays a cold start. Render's paid Postgres tiers may
well be fine — I **could not verify** them, as `https://render.com/pricing` and
`https://render.com/docs/postgresql-pricing` both failed to yield the table this session (the
pricing page returned navigation chrome only; the docs URL returned 404).

**Skip Supabase's free tier for the pipeline.** VERIFIED (`https://supabase.com/pricing`): 500 MB
database, 5 GB egress, 2 active projects, no backups, and "Free projects are paused after 1 week of
inactivity". Pro is $25/month with 8 GB disk and 7-day daily backups. Cost of adopting the free tier:
a pipeline that runs weekly or on demand is exactly the usage profile that trips the pause rule, and
Sync would gain nothing from Supabase's auth/storage/realtime layers, which are the reason to be
there at all.

**Skip Oracle Cloud Always Free despite it being the largest free allocation available.** VERIFIED
(`https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm`):
1,500 Ampere A1 OCPU-hours and 9,000 GB-hours per month (equivalent to 2 OCPUs and 12 GB always on),
2 AMD micro instances, 200 GB total block storage, 10 TB/month outbound transfer. And the
disqualifier, also verified there: idle instances may be reclaimed when, across a 7-day window, the
95th-percentile CPU, network *and* memory utilisation are all below 20%. INFERENCE: a batch pipeline
that idles between runs is the textbook profile for that reclamation rule, and losing the host is a
worse failure than paying €3.79. There is no Always Free managed Postgres — the free databases are
Oracle Autonomous, NoSQL and MySQL HeatWave, none of which Sync can use.

**Skip `free-for-dev` as a source of prices; use it only as an index of who exists.** VERIFIED: the
README is 246 KB with a 57-entry table of contents (PaaS, IaaS, Managed Data Services, Web Hosting,
CI and CD, Monitoring, Log Management, and so on) and no schema whatsoever — entries are prose
bullets, so nothing about a stated limit can be validated or dated. Every price in section 2.3 above
came from the vendor's own page for that reason. Two operational notes: **could not verify** the
contents of its PaaS section this session, because the file is large enough that fetches truncate at
the head and there is no per-section endpoint. And VERIFIED — the repository ships `CLAUDE.md` and
`AGENTS.md` at its root stating a policy against AI-generated contributions, with PRs closed without
discussion; do not send it agent-written patches.

**Skip `the-book-of-secret-knowledge` almost entirely.** VERIFIED: 236,687 stars, MIT, but last
pushed **2024-11-19**, so it is roughly twenty months stale as of this audit and any tool
recommendation in it needs re-checking. Its top-level chapters are CLI Tools, GUI Tools, Web Tools,
Systems/Services, Networks, Containers/Orchestration, Manuals/Howtos/Tutorials, Inspiring Lists,
Blogs/Podcasts/Videos, Hacking/Penetration Testing, Other Cheat Sheets, Shell One-liners, Shell
Tricks, Shell Functions. Only three are plausibly worth a Sync engineer's time: **Shell One-liners**
and **Shell Functions** when debugging the subprocess layer that drives `git`, `npm`/`pnpm` and
`tsc`; and **Systems/Services** when tuning the self-hosted Postgres under Option A. Everything else
— the penetration-testing, networking and GUI chapters — is off-topic for this project. It does not
belong on the M4 reading list at all.

## 4. Who should consult this, and what it answers

**Whoever picks the next vendor adapter (the `sync.signals.*` subsystem).** Question answered: "is
there a machine-readable way to rank candidate vendors?" Answer: not from `public-apis`, but yes in
part from APIs.guru — start at `https://api.apis.guru/v2/{provider}.json`, take `x-origin.url` as the
canonical spec location, and confirm freshness against that repository rather than against the
cache. Sync currently has adapters under `src/sync/signals/` for `stripe`, `twilio`, `sentry` and
`datadog`, alongside the vendor-neutral `deprecations`, `generated`, `mcp_server` and `registry_tier`
modules (VERIFIED by directory listing) — the candidate list should be built the same way those four
would have been.

**Whoever builds the adapter-coverage view in M4's console.** Question answered: "should the coverage
table be hand-written or generated?" Answer: generated, on the `awesome-selfhosted-data` + `hecat`
pattern — YAML record per adapter with human judgement fields, a scheduled processor stamping
freshness fields onto it, a linter rejecting malformed records, and the console rendering the data
rather than a maintained Markdown table.

**Whoever deploys M4 (the operator console and the read-only Starlette API at `src/sync/api/`).**
Question answered: "what does hosting this cost?" Answer: about €4–7/month for a Hetzner CX22 or
CX32 running the existing compose stack, plus $0 for the `web/` build on Cloudflare Pages. Managed
Postgres starts near $38/month on Fly and is not justified at this stage. Re-check the CX22 price
before ordering — Hetzner reset prices in June 2026 and CX22 was not in the published adjustment
table.
