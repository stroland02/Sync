// Shaped after app/api/setup_accounts/route.ts in stripe-connect-furever-demo, which is
// the M0 acceptance target. Two stripe.paymentIntents.create calls in one file, both
// passing receipt_email, is the arrangement a naive removal gets wrong: the finding names
// one call site, and a diff touching both claims something the reviewer was not told.
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

// receipt_email: this one is prose, and a regular expression would delete it.
export async function chargeOnboarding(customerId: string) {
  const intent = await stripe.paymentIntents.create({
    amount: 1000,
    currency: 'usd',
    customer: customerId,
    receipt_email: 'onboarding@example.com',
  });
  return intent.id;
}

export async function chargeTopUp(customerId: string) {
  const intent = await stripe.paymentIntents.create({
    amount: 2500,
    currency: 'usd',
    customer: customerId,
    receipt_email: 'topup@example.com',
  });
  return intent.status;
}
