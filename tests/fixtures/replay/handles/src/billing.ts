// The same call site, patched correctly: the null the vendor now sends is handled rather
// than dereferenced. Identical to the `mishandles` fixture in every other respect, so a tier
// that passed both would be proving nothing about either.
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function charge(amount: number) {
  const result = await stripe.charges.create({ amount, currency: 'usd' });
  return { id: result.id, state: result.status ?? 'unknown' };
}
