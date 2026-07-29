// The call path is fine and the module still never loads: it imports a package this clone does
// not carry. Replay installs nothing -- the vendor package is intercepted rather than resolved
// -- so whatever else a module imports has to be there already, and when it is not, the failure
// is a fact about the checkout rather than about the patch.
import Stripe from 'stripe';
import { formatAmount } from 'a-package-this-clone-does-not-have';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function charge(amount: number) {
  const result = await stripe.charges.create({ amount, currency: 'usd' });
  return { id: result.id, state: result.status ?? formatAmount(amount) };
}
