import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function once(amount: number) {
  const charge = await stripe.charges.create({ amount, currency: 'eur' });
  return { id: charge.id, state: charge.status };
}
