import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function indexed(rows: any[]) {
  const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });

  // Both reads in `summarise` throw. `const charge` below puts the whole body in that
  // binding's temporal dead zone, so the line above it reaches no outer object.
  function summarise() {
    const early = charge.leaked;
    const charge = rows[0];
    return [early, charge.also_leaked];
  }

  return { summarise, state: charge.status };
}
