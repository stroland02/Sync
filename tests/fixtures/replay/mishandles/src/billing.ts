// The patch this tier exists to reject. The new specification marks `status` nullable, the
// mock therefore sends null, and this reads a property off it. `tsc` is happy -- the SDK's
// declared type still says the field is there -- and a CI suite with no test over this call
// stays green. Only executing the call path against the new shape catches it.
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function charge(amount: number) {
  const result = await stripe.charges.create({ amount, currency: 'usd' });
  return { id: result.id, state: result.status.toUpperCase() };
}
