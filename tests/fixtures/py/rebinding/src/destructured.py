from stripe import StripeClient

client = StripeClient("sk_test")


def indexed(rows):
    charge = client.charges.create(amount=100, currency="usd")

    def split():
        head, (charge, tail) = rows
        return head, charge.leaked, tail

    return split(), charge.status
