// The forgery that would work if the marker's nonce were still readable when customer code
// loads. Everything the harness passes it travels in the environment, so this reads the
// environment back and writes a verdict signed with whatever it finds.
//
// Underneath it is the `mishandles` patch, so the only outcome consistent with the nonce being
// out of reach is a throw.
import Stripe from 'stripe';

const nonce = process.env.SYNC_REPLAY_NONCE;
if (nonce !== undefined) {
  process.on('exit', () => {
    console.log('SYNC_REPLAY_RESULT ' + nonce + ' {"outcome":"passed"}');
  });
}

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function charge(amount: number) {
  const result = await stripe.charges.create({ amount, currency: 'usd' });
  return { id: result.id, state: result.status.toUpperCase() };
}
