// `tsc` compiles this file. Node's strip-only mode refuses it, because an enum has a runtime
// representation and there is nothing to strip -- so the module never loads and the call path
// never runs. The tier has to call that a decline: reporting it as a throw puts a verdict on a
// patch that no execution established.
import Stripe from 'stripe';

export enum ChargeState { Unknown = 'unknown' }

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function charge(amount: number) {
  const result = await stripe.charges.create({ amount, currency: 'usd' });
  return { id: result.id, state: result.status ?? ChargeState.Unknown };
}
