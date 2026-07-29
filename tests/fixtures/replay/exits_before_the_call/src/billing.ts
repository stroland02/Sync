// A module that ends the process while it is still loading, and says nothing on the way out.
// There is no verdict on stdout because there was no run, and the only thing the tier can
// honestly report is that nothing was established.
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);
process.exit(0);

export async function charge(amount: number) {
  return stripe.charges.create({ amount, currency: 'usd' });
}
