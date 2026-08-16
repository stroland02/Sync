from stripe import StripeClient

client = StripeClient("sk_test")


def indexed(rows):
    charge = client.charges.create(amount=100, currency="usd")

    class Report:
        charge = rows[0]
        total = charge.leaked

    return Report, charge.status
