import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });
console.log(charge.status);

export function summarise() {
  const charge = computeLocally();
  return charge.total;
}

function computeLocally() {
  return { total: 42 };
}
