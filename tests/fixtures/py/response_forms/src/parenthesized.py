from stripe import StripeClient

client = StripeClient("sk_test")


def parenthesized(amount: int):
    charge = (client.charges.create(amount=amount))
    return charge.id, charge.status
