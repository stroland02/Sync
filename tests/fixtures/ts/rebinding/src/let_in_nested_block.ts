import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function indexed(flag: boolean) {
  const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });

  function report() {
    const early = charge.total;
    if (flag) {
      let charge = { leaked: 1 };
      return charge.leaked;
    }
    return early;
  }

  return { report, state: charge.status };
}
