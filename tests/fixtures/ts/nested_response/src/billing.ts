import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function charge(amount: number) {
  const result = await stripe.charges.create({ amount, currency: 'usd' });
  // A list element reached through a subscript: the chain stops at the array,
  // which is as deep as syntax alone can follow it.
  const first = result.data[0].customer;
  return {
    brand: result.payment_method_details.card.brand,
    reason: result.error.payment_method,
    first,
  };
}
