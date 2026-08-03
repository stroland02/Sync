import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function indexed(flag: boolean) {
  const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });

  // `var` is scoped to the whole of `report`, not to the block it is written in, so the read
  // above it is of the hoisted local and yields `undefined` -- never the outer object. A rule
  // that stops at the block treats `report` as not rebinding and records that read.
  function report() {
    const early = charge.leaked;
    if (flag) {
      var charge = { leaked: 1 };
    }
    return early;
  }

  return { report, state: charge.status };
}
