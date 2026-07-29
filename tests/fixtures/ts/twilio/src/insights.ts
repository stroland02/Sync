import { Twilio } from 'twilio';

const client = new Twilio(process.env.TWILIO_SID!, process.env.TWILIO_TOKEN!);

export async function recentConferences() {
  const conferences = await client.insights.v1.conferences.list({ pageSize: 20 });
  return conferences;
}

export async function recentSummaries() {
  const summaries = await client.insights.v1.callSummaries.list({ pageSize: 20 });
  return summaries;
}
