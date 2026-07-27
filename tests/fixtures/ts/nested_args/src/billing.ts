import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function charge(amount: number) {
  const result = await stripe.charges.create({
    amount,
    currency: 'usd',
    metadata: { internal_id: 'abc', enabled: true },
  });
  return result.status;
}
