# Integration catalog

Generated from the vendor registry by `scripts/build_integration_docs.py` -- the same call the command line resolves vendors with, so this table cannot claim an integration the product does not serve. *Supported* means a registered adapter watches the vendor today; *recognized* means Sync can name the dependency and says so, and watching it is described on its page.

Missing a vendor entirely? [Writing a vendor adapter](../../writing-a-vendor-adapter.md) is the path, and an adapter depends on `sync.core` alone.

## Supported

| Vendor | Adapter kind | Categories |
|---|---|---|
| [Anthropic](anthropic.md) | generated | ai |
| [Browserbase](browserbase.md) | generated | dev-tools |
| [Cloudflare](cloudflare.md) | generated | infrastructure |
| [Finch](finch.md) | generated | hr |
| [Groq](groq.md) | generated | ai |
| [Increase](increase.md) | generated | banking |
| [Lithic](lithic.md) | generated | payment |
| [Mistral AI](mistral.md) | generated | ai |
| [Modern Treasury](modern-treasury.md) | generated | banking |
| [OpenAI](openai.md) | generated | ai |
| [Openlayer](openlayer.md) | generated | ai |
| [Orb](orb.md) | generated | invoicing |
| [Stripe](stripe.md) | coded | payment |
| [Twilio](twilio.md) | coded | communication |
| [Vercel](vercel.md) | generated | infrastructure |

## Recognized

| Vendor | Categories |
|---|---|
| [Airtable](airtable.md) | productivity |
| [Algolia](algolia.md) | dev-tools, search |
| [Bitbucket](bitbucket.md) | dev-tools |
| [Clerk](clerk.md) | dev-tools, iam |
| [Datadog](datadog.md) | dev-tools, analytics |
| [Dub](dub.md) | dev-tools, marketing |
| [Firebase](firebase.md) | dev-tools, infrastructure |
| [GitHub](github.md) | dev-tools |
| [GitLab](gitlab.md) | dev-tools |
| [HubSpot](hubspot.md) | crm |
| [Intercom](intercom.md) | support |
| [Jira](jira.md) | dev-tools, ticketing |
| [LaunchDarkly](launchdarkly.md) | dev-tools |
| [Linear](linear.md) | ticketing |
| [Netlify](netlify.md) | dev-tools, infrastructure |
| [Notion](notion.md) | productivity |
| [PagerDuty](pagerduty.md) | dev-tools |
| [Resend](resend.md) | dev-tools, communication |
| [Salesforce](salesforce.md) | crm |
| [SendGrid](sendgrid.md) | communication |
| [Sentry](sentry.md) | dev-tools, analytics |
| [Shopify](shopify.md) | e-commerce |
| [Slack](slack.md) | communication |
| [Supabase](supabase.md) | dev-tools, infrastructure |
