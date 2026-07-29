// A call path that tries to reach the vendor for real. Nothing legitimate does this during a
// replay -- the mock is the only response -- so the sandbox must stop it rather than let it
// out, and the test asserts the refusal rather than trusting a paragraph.
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function charge(amount: number) {
  const live = await fetch('https://api.stripe.com/v1/charges');
  const result = await stripe.charges.create({ amount, currency: 'usd' });
  return { id: result.id, live: live.status };
}
