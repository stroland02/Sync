// The credential assertions, written as throws so no value ever crosses back into Python.
//
// A replay that passes this proves two things at once: the parent process's environment did
// not reach the child, and the one variable replay was asked to supply carried the synthetic
// value rather than anything that could authenticate. Returning the values instead and
// asserting on them in Python would put a real secret one bug away from a test report.
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function charge(amount: number) {
  if (process.env.SYNC_TEST_PARENT_SECRET !== undefined) {
    throw new Error('the parent environment reached the sandbox');
  }
  if (process.env.STRIPE_KEY !== '<sync-replay-not-a-credential>') {
    throw new Error('STRIPE_KEY was not the synthetic value');
  }
  const result = await stripe.charges.create({ amount, currency: 'usd' });
  return { id: result.id };
}
