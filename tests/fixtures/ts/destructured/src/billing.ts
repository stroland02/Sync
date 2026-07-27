import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function charge(amount: number) {
  const { id, status: chargeStatus } = await stripe.charges.create({ amount, currency: 'usd' });
  return { id, chargeStatus };
}
