from stripe import StripeClient

client = StripeClient("sk_test")


def outer():
    charge = client.charges.create(amount=100, currency="usd")

    def inner():
        charge = compute_locally()
        return charge.total

    return charge.status, inner


def compute_locally():
    return {"total": 42}
