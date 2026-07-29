import stripe as billing


def charge(amount: int):
    result = billing.charges.create(amount=amount, currency="eur")
    return result.status
