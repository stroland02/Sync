import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function lookUpCharge(id: string) {
  const charge = await stripe.charges.retrieve(id);
  return charge.amount;
}

export async function fireAndForget(amount: number) {
  await stripe.charges.create({ amount, currency: 'gbp' });
}
