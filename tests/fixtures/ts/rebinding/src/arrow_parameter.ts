import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function indexed(rows: any[]) {
  const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });
  const describe = (charge: any) => charge.leaked;
  return { described: rows.map(describe), state: charge.status };
}
