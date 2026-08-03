import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function indexed(rows: any[]) {
  const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });

  const seen = [];
  for (let charge = rows[0]; charge; charge = charge.next) {
    seen.push(charge.leaked);
  }

  return { seen, state: charge.status };
}
