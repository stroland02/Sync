from stripe import StripeClient

client = StripeClient("sk_test")


def charge():
    result = client.charges.create(amount=1)
    brand = result["payment_method_details"]["card"]
    first = result["data"][0]
    return result["status"], brand, first
