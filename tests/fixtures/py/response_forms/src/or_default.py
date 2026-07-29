from stripe import StripeClient

client = StripeClient("sk_test")


def or_default(amount: int):
    charge = client.charges.create(amount=amount) or {}
    return charge["id"], charge["status"]
