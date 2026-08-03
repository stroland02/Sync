from stripe import StripeClient

client = StripeClient("sk_test")


def indexed(path):
    charge = client.charges.create(amount=100, currency="usd")

    def archive():
        with open(path, encoding="utf-8") as charge:
            return charge.leaked

    return archive(), charge.status
