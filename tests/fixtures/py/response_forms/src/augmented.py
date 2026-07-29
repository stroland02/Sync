from stripe import StripeClient

client = StripeClient("sk_test")


def augmented(amount: int):
    charge = []
    charge += client.charges.create(amount=amount)
    return charge
