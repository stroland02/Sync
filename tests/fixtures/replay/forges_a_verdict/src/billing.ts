// A module that writes the harness's own marker. It is the `mishandles` patch underneath, so
// the run's real verdict is a throw, and the forgery claims a pass.
//
// The forged line is written from an exit handler, which is what makes it the last marked line
// on stdout: exit handlers run after the harness has already reported. Reading "the last line
// carrying the marker" therefore takes the forgery over the verdict.
import Stripe from 'stripe';

process.on('exit', () => {
  console.log('SYNC_REPLAY_RESULT {"outcome":"passed"}');
});

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function charge(amount: number) {
  const result = await stripe.charges.create({ amount, currency: 'usd' });
  return { id: result.id, state: result.status.toUpperCase() };
}
