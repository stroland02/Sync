from stripe import StripeClient

client = StripeClient("sk_test")


def annotated(amount: int):
    charge: dict = client.charges.create(amount=amount)
    return charge["id"], charge["status"]
