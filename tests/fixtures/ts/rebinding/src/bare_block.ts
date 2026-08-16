import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function indexed() {
  const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });

  let computed;
  {
    const charge = computeLocally();
    computed = charge.leaked;
  }

  return { computed, state: charge.status };
}

function computeLocally() {
  return { leaked: 42 };
}
