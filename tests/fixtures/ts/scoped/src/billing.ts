import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function chargeOnly(amount: number) {
  const result = await stripe.charges.create({ amount, currency: 'usd' });
  return result.status;
}

export function unrelated() {
  const result = computeLocally();
  return result.total;
}

function computeLocally() {
  return { total: 42 };
}
