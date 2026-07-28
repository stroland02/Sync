import stripe


def charge():
    return stripe.Charge.create(amount=1)
