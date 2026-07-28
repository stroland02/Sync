import stripe


def charge(amount: int):
    result = stripe.charges.create(amount=amount, currency="usd")
    return result.status
