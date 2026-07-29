from stripe import StripeClient

client = StripeClient("sk_test")


def forwarded(amount: int):
    return client.charges.create(amount=amount)
