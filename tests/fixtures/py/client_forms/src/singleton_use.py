from .singleton_define import shared


def charge(amount: int):
    result = shared.charges.create(amount=amount)
    return result.id
