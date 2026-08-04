import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function outer() {
  const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });

  function inner() {
    const charge = computeLocally();
    return charge.total;
  }

  return { state: charge.status, inner };
}

function computeLocally() {
  return { total: 42 };
}
