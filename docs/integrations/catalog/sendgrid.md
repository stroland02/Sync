# SendGrid

> Status: **recognized** -- Sync can name this dependency in your repository, and does not watch it yet. That is a statement of absence, not a lesser kind of coverage.

## What your lockfile declares

- **npm**: `@sendgrid/mail`
- **pypi**: `sendgrid`

## Adding it

If this vendor's SDK is built by a supported generator, watching it is one entry in [`generated-vendors.yaml`](../../../generated-vendors.yaml). Otherwise, a coded adapter depends on `sync.core` alone -- [Writing a vendor adapter](../../writing-a-vendor-adapter.md) is the guide, and Sync does not watch this vendor until one exists.

## What Sync does not watch

Everything, for this vendor, today. The entry above exists so the absence is named instead of silent.

Official documentation: [https://www.twilio.com/docs/sendgrid](https://www.twilio.com/docs/sendgrid)
