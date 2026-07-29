from stripe import StripeClient

client = StripeClient("sk_test")


async def awaited(amount: int):
    charge = await client.charges.create(amount=amount)
    return charge.id, charge.status
