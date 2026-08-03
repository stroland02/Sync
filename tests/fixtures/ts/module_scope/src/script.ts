import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

const charge = await stripe.charges.create({ amount: 100, currency: 'usd' });
console.log(charge.id, charge.status);
