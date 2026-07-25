import StripeClient from 'stripe';

const billing = new StripeClient(process.env.STRIPE_KEY!);

export async function pay(amount: number) {
  const charge = await billing.charges.create({ amount, currency: 'eur' });
  return charge.status;
}
