import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();

export async function summarise(text: string) {
  const message = await client.messages.create({
    model: 'claude-opus-4-5',
    max_tokens: 1024,
    messages: [{ role: 'user', content: text }],
  });
  return message.id;
}
