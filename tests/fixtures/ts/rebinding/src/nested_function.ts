import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function indexed() {
  const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });

  function fallback() {
    function charge() {
      return null;
    }

    return charge.leaked;
  }

  return { fallback, state: charge.status };
}
