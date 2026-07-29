from stripe import StripeClient

client = StripeClient("sk_test")


def walrus_comprehension(amounts: list[int]):
    kept = [charge for amount in amounts if (charge := client.charges.create(amount=amount))]
    return kept, charge.id, charge.status
