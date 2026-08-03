from stripe import StripeClient

client = StripeClient("sk_test")

charge = client.charges.create(amount=100, currency="usd")
print(charge.status)


def summarise():
    charge = compute_locally()
    return charge.total


def compute_locally():
    return {"total": 42}
