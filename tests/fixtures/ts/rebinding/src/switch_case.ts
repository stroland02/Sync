import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function indexed(kind: number) {
  const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });

  let picked;
  // Deliberately unbraced. A braced case body is a `statement_block` and is caught as one; a
  // declaration in a bare case clause is scoped to the switch block instead, which is the only
  // shape that makes the switch itself a scope worth knowing about.
  switch (kind) {
    case 1:
      const charge = { leaked: 1 };
      picked = charge.leaked;
      break;
    default:
      picked = null;
  }

  return { picked, state: charge.status };
}
