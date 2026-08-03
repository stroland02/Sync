from stripe import StripeClient

client = StripeClient("sk_test")

charge = client.charges.create(amount=100, currency="usd")
print(charge.status)


def refund():
    charge = client.charges.retrieve(id="ch_1")
    return charge.amount_refunded
