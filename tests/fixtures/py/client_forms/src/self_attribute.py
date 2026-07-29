import stripe


class Payments:
    def __init__(self, key: str):
        self.payments = stripe.StripeClient(key)

    def charge(self, amount: int):
        result = self.payments.charges.create(amount=amount)
        return result.id
