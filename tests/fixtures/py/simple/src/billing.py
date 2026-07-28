from stripe import StripeClient

client = StripeClient("sk_test")


def charge(amount: int):
    result = client.charges.create(amount=amount, currency="usd")
    return {"id": result.id, "state": result.status}
