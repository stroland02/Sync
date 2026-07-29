import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

function wrap<T>(value: T): { id: string; status: string } {
  return value as never;
}

export async function indirect(amount: number) {
  const charge = wrap(await stripe.charges.create({ amount, currency: 'jpy' }));
  return { id: charge.id, state: charge.status };
}
