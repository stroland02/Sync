from stripe import StripeClient

client = StripeClient("sk_test")


def walrus_while(amount: int):
    while charge := client.charges.create(amount=amount):
        if charge.status == "succeeded":
            return charge.id
    return None
