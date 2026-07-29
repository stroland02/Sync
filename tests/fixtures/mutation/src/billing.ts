import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function chargeCustomer(amount: number) {
  const charge = await stripe.charges.create({ amount, currency: 'eur' });
  return charge.id;
}

export async function chargeSupplier(amount: number) {
  const payment = await stripe.charges.create({ amount, currency: 'usd' });
  return payment.id;
}
