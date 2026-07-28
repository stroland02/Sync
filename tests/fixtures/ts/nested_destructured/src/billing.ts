import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function charge(amount: number) {
  const { id, payment_method_details: { card: { brand } } } = await stripe.charges.create({
    amount,
    currency: 'usd',
  });
  return { id, brand };
}
