import { stripe } from './client';

export async function refundable(id: string) {
  const charge = await stripe.charges.retrieve(id);
  return charge.amount;
}
