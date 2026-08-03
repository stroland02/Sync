from stripe import StripeClient


class Ledger:
    def __init__(self, **kwargs):
        self.charges = kwargs


def stripe(**kwargs):
    return Ledger(**kwargs)


ledger = stripe(amount=1)
ledger.charges.create(amount=1)


def billing(key: str) -> StripeClient:
    return StripeClient(key)
