import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function indexed(rows: any[]) {
  const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });

  let described;
  {
    const { charge } = rows[0];
    described = charge.leaked;
  }

  return { described, state: charge.status };
}
