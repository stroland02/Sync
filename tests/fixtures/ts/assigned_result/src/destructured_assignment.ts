import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function pick(amount: number) {
  let id: string;
  let status: string;
  ({ id, status } = await stripe.charges.create({ amount, currency: 'gbp' }));
  return [id, status];
}
