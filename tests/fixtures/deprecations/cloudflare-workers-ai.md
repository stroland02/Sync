---
description: We are refreshing the Workers AI model catalog. Eighteen older models will be deprecated on May 30, 2026.
title: Planned model deprecations on Workers AI
image: https://developers.cloudflare.com/og-changelog.png
---

[Skip to content](#main-content)

[View RSS feeds](https://developers.cloudflare.com/fundamentals/new-features/available-rss-feeds/)[Subscribe to RSS](https://developers.cloudflare.com/changelog/rss/index.xml)

[Back to all posts](https://developers.cloudflare.com/changelog)

May 8, 2026

## Planned model deprecations on Workers AI

[Workers AI](https://developers.cloudflare.com/workers-ai/)

We are refreshing the Workers AI model catalog to make room for newer releases. Please update your apps to remove references to the models listed below before the deprecation date.

#### Recommended replacements

* [@cf/zai-org/glm-4.7-flash](https://developers.cloudflare.com/workers-ai/models/glm-4.7-flash/) — fast multilingual model with multi-turn tool calling and coding capabilities.
* [@cf/google/gemma-4-26b-a4b-it](https://developers.cloudflare.com/workers-ai/models/gemma-4-26b-a4b-it/) — efficient open model with vision and tool calling.
* [@cf/moonshotai/kimi-k2.6](https://developers.cloudflare.com/workers-ai/models/kimi-k2.6/) — capable tool-calling and vision model for agentic workloads and coding.

For pricing, refer to the [Workers AI pricing page](https://developers.cloudflare.com/workers-ai/platform/pricing/).

#### Kimi K2.5

We originally stated Kimi K2.5 would be deprecated on May 10, 2026, however we have extended the deprecation date to May 30, 2026\. Requests will be automatically aliased to Kimi K2.6 on May 30, 2026, which has a higher price. Please review the [@cf/moonshotai/kimi-k2.6](https://developers.cloudflare.com/workers-ai/models/kimi-k2.6/) pricing and model capabilities prior to May 30, 2026 to ensure that the model suits your needs.

#### Models deprecated on May 30, 2026

* `@cf/moonshotai/kimi-k2.5` \--> `@cf/moonshotai/kimi-k2.6`
* `@hf/meta-llama/meta-llama-3-8b-instruct`
* `@cf/meta/llama-3-8b-instruct`
* `@cf/meta/llama-3-8b-instruct-awq`
* `@cf/meta/llama-3.1-8b-instruct`
* `@cf/meta/llama-3.1-8b-instruct-awq`
* `@cf/meta/llama-3.1-70b-instruct`
* `@cf/meta/llama-2-7b-chat-int8`
* `@cf/meta/llama-2-7b-chat-fp16`
* `@cf/mistral/mistral-7b-instruct-v0.1`
* `@hf/mistral/mistral-7b-instruct-v0.2`
* `@hf/google/gemma-7b-it`
* `@cf/google/gemma-3-12b-it`
* `@hf/nousresearch/hermes-2-pro-mistral-7b`
* `@cf/microsoft/phi-2`
* `@cf/defog/sqlcoder-7b-2`
* `@cf/unum/uform-gen2-qwen-500m`
* `@cf/facebook/bart-large-cnn`

#### Variants that remain active

The `-fast` and `-lora` variants of models will remain active, including:

* `@cf/meta/llama-3.3-70b-instruct-fp8-fast`
* `@cf/meta/llama-3.1-8b-instruct-fast`
* `@cf/google/gemma-7b-it-lora`
* `@cf/google/gemma-2b-it-lora`
* `@cf/mistral/mistral-7b-instruct-v0.2-lora`
* `@cf/meta-llama/llama-2-7b-chat-hf-lora`

LoRA models may be deprecated in the future. We will be adding more LoRA capabilities to the catalog, and will communicate when new LoRA models come online to give users time to train new LoRAs before we deprecate old ones.

For the full list of available models, refer to the [Workers AI model catalog](https://developers.cloudflare.com/workers-ai/models/).

```json
{"@context":"https://schema.org","@type":"BlogPosting","@id":"https://developers.cloudflare.com/changelog/post/2026-05-08-planned-model-deprecations/#page","headline":"Planned model deprecations on Workers AI · Changelog","description":"We are refreshing the Workers AI model catalog. Eighteen older models will be deprecated on May 30, 2026.","url":"https://developers.cloudflare.com/changelog/post/2026-05-08-planned-model-deprecations/","inLanguage":"en","image":"https://developers.cloudflare.com/og-changelog.png","dateModified":"2026-05-08","datePublished":"2026-05-08","publisher":{"@type":"Organization","name":"Cloudflare","url":"https://www.cloudflare.com/"},"isPartOf":{"@type":"WebSite","@id":"https://developers.cloudflare.com/#website","name":"Cloudflare Docs","url":"https://developers.cloudflare.com/"}}
```
