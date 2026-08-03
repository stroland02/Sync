from stripe import StripeClient

client = StripeClient("sk_test")


def indexed():
    charge = client.charges.create(amount=100, currency="usd")

    def fallback():
        def charge():
            return None

        return charge.leaked

    return fallback(), charge.status
