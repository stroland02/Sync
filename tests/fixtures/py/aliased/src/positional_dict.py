from stripe import StripeClient

payments = StripeClient("sk_test")


def charge():
    return payments.charges.create({"amount": 1, "metadata": {"internal_id": "abc"}})
