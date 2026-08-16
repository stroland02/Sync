// The same stripe-connect-furever-demo call as `two_payment_intents`, with the property
// written as a computed key. `{ ['receipt_email']: ... }` and `{ receipt_email: ... }` are
// the same key, so a reader that compares the bracketed text sees the property as absent --
// and the pipeline reports that as the code already agreeing with the vendor.
//
// The second call computes its key from a binding. That name is not written at the call
// site, so the property set of that object is not knowable and the edit is declined.
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

const RECEIPT = 'receipt_email';

export async function chargeOnboarding(customerId: string) {
  const intent = await stripe.paymentIntents.create({
    amount: 1000,
    currency: 'usd',
    customer: customerId,
    ['receipt_email']: 'onboarding@example.com',
  });
  return intent.id;
}

export async function chargeTopUp(customerId: string) {
  const intent = await stripe.paymentIntents.create({
    amount: 2500,
    currency: 'usd',
    [RECEIPT]: 'topup@example.com',
  });
  return intent.status;
}
