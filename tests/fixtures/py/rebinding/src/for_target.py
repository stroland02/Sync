from stripe import StripeClient

client = StripeClient("sk_test")


def indexed(rows):
    charge = client.charges.create(amount=100, currency="usd")

    def total():
        seen = []
        for charge in rows:
            seen.append(charge.leaked)
        return seen

    return total(), charge.status
