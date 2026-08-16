from stripe import StripeClient

client = StripeClient("sk_test")


def indexed(rows):
    charge = client.charges.create(amount=100, currency="usd")
    leaked = [charge.leaked for charge in rows]
    return leaked, charge.status
