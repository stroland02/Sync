import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });
console.log(charge.status);

export async function refund() {
  const charge = await stripe.charges.retrieve('ch_1');
  return charge.amount_refunded;
}
