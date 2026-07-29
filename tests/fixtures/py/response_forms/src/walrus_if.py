from stripe import StripeClient

client = StripeClient("sk_test")


def walrus_if(amount: int):
    if charge := client.charges.create(amount=amount):
        return charge.id, charge.status
    return None
