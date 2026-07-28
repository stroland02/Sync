from stripe import StripeClient

client = StripeClient("sk_test")


def charge():
    return client.charges.create(
        amount=1,
        metadata={"internal_id": "abc", "nested": {"deep": 1}},
    )
