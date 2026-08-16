from stripe import StripeClient

client = StripeClient("sk_test")


def indexed(rows):
    charge = client.charges.create(amount=100, currency="usd")

    def report():
        try:
            return rows.pop()
        except IndexError as charge:
            return charge.leaked

    return report(), charge.status
