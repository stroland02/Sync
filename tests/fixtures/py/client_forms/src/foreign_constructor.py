import notstripe

vault = notstripe.StripeClient("sk_test")


def charge(amount: int):
    result = vault.charges.create(amount=amount)
    return result.id
