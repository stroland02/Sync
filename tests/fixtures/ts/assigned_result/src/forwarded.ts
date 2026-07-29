import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function forward(amount: number) {
  return stripe.charges.create({ amount, currency: 'chf' });
}
