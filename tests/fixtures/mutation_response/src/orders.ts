import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function declared(amount: number) {
  const intent = await stripe.paymentIntents.create({ amount, currency: 'usd' });
  return intent.id;
}

export async function assigned(amount: number) {
  let intent;
  intent = await stripe.paymentIntents.create({ amount, currency: 'eur' });
  return intent.id;
}

export async function forwarded(amount: number) {
  return stripe.paymentIntents.create({ amount, currency: 'gbp' });
}

export async function ignored(amount: number) {
  await stripe.paymentIntents.create({ amount, currency: 'chf' });
}
