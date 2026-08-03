import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function indexed() {
  const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });

  function report() {
    var charge = computeLocally();
    return charge.leaked;
  }

  return { report, state: charge.status };
}

function computeLocally() {
  return { leaked: 42 };
}
