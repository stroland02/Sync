import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function indexed() {
  const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });

  function describe() {
    return charge.total;
  }

  return { described: describe(), state: charge.status };
}
