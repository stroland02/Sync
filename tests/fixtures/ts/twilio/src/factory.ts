import twilio from 'twilio';

const factoryClient = twilio(process.env.TWILIO_SID!, process.env.TWILIO_TOKEN!);

export async function recentRooms() {
  const rooms = await factoryClient.insights.v1.rooms.list({ pageSize: 5 });
  return rooms;
}
