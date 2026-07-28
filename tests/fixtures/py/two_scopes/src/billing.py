from stripe import StripeClient

client = StripeClient("sk_test")


def charge():
    result = client.charges.create(amount=1)
    return result.status


def refund():
    result = client.charges.retrieve(id=1)
    return result.amount_refunded
