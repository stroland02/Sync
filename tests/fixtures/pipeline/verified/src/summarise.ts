// A call site naming a retired model as a string literal, which is the shape the literal
// indexer finds and the tier-0 codemod repairs. No SDK is installed: the whole project has no
// `package.json`, so nothing is downloaded to typecheck it and `tsc` runs against the source
// alone -- which is the point, since what is under test is whether the pipeline composes.

const MODEL = "claude-old-1";

export async function summarise(text: string): Promise<string> {
  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ model: MODEL, max_tokens: 1024, input: text }),
  });
  const body = (await response.json()) as { text: string };
  return body.text;
}
