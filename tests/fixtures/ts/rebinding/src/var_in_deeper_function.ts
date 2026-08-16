import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function indexed() {
  const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });

  // `inner`'s `var` hoists to `inner` and no further, so `report`'s first line still reads the
  // outer object and `total` is a field the call genuinely returns. The search for a hoisted
  // `var` has to stop at a function for that read to survive.
  function report() {
    const early = charge.total;

    function inner() {
      var charge = { leaked: 1 };
      return charge.leaked;
    }

    return [early, inner()];
  }

  return { report, state: charge.status };
}
