import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function indexed(rows: any[]) {
  const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });

  let reported;
  try {
    reported = rows.pop();
  } catch (charge) {
    reported = charge.leaked;
  }

  return { reported, state: charge.status };
}
