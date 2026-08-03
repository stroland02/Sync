from stripe import StripeClient

client = StripeClient("sk_test")


def indexed(rows):
    charge = client.charges.create(amount=100, currency="usd")

    # The control on the same search. The walrus is inside a `lambda` inside the comprehension,
    # so it binds in the lambda and reaches no further -- `report` still closes over the outer
    # object and `total` is a field the call genuinely returns.
    def report():
        early = charge.total
        picked = [(lambda: (charge := row)) for row in rows]
        return early, picked

    return report(), charge.status
