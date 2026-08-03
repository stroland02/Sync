from stripe import StripeClient

client = StripeClient("sk_test")


class Billing:
    charge = client.charges.create(amount=100, currency="usd")
    state = charge.status
