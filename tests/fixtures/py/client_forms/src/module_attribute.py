import stripe

billing = stripe.StripeClient("sk_test")


def charge(amount: int):
    result = billing.charges.create(amount=amount)
    return result.id
