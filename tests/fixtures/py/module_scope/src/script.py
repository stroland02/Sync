from stripe import StripeClient

client = StripeClient("sk_test")

charge = client.charges.create(amount=100, currency="usd")
print(charge.id, charge.status)
