from stripe import StripeClient

client = StripeClient("sk_test")


def walrus_wrapped(amount: int):
    if charge := dict(client.charges.create(amount=amount)):
        return charge["id"], charge["status"]
    return None
