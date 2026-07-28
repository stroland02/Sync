import Stripe from 'stripe';

const stripe = new Stripe('sk_test');

export async function once(id: string) {
  return stripe.charges.create({ amount: 100 });
}

export async function perCustomer(ids: string[]) {
  for (const id of ids) {
    await stripe.charges.create({ amount: 100 });
  }
}

export async function perLineItem(orders: string[][]) {
  for (const order of orders) {
    for (const line of order) {
      await stripe.charges.create({ amount: 100 });
    }
  }
}

export async function viaCallback(ids: string[]) {
  await Promise.all(ids.map((id) => stripe.charges.create({ amount: 100 })));
}
