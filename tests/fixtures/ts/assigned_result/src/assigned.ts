import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function retry(amount: number) {
  let charge;
  charge = await stripe.charges.create({ amount, currency: 'usd' });
  return { id: charge.id, state: charge.status };
}
