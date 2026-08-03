from stripe import StripeClient

client = StripeClient("sk_test")


def indexed():
    charge = client.charges.create(amount=100, currency="usd")

    def describe():
        return charge.total

    return describe(), charge.status
