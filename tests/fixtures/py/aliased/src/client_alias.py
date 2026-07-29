from stripe import StripeClient as Client

gateway = Client("sk_test")


def retrieve(charge_id: str):
    result = gateway.charges.retrieve(id=charge_id)
    return result.amount
