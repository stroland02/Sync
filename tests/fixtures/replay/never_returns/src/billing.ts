// A call path that awaits something nothing will settle. The timer is what keeps the event
// loop alive: without it Node would drain and exit, and the run would look like a module that
// produced no verdict rather than like one that never came back.
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function charge(amount: number) {
  await stripe.charges.create({ amount, currency: 'usd' });
  await new Promise((resolve) => setTimeout(resolve, 600000));
}
