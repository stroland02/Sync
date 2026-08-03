from stripe import StripeClient

client = StripeClient("sk_test")


def indexed(rows):
    charge = client.charges.create(amount=100, currency="usd")
    describe = lambda charge: charge.leaked
    return [describe(row) for row in rows], charge.status
