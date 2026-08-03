from stripe import StripeClient

client = StripeClient("sk_test")


def indexed(rows):
    charge = client.charges.create(amount=100, currency="usd")

    # `inner`'s assignment makes `charge` local to `inner` and no further, so `report`'s first
    # line still closes over the outer object and `total` is a field the call genuinely returns.
    # The search for a rebinding has to stop at a nested scope for that read to survive.
    def report():
        early = charge.total

        def inner():
            charge = rows[0]
            return charge.leaked

        return early, inner()

    return report(), charge.status
