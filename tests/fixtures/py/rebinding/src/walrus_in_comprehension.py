from stripe import StripeClient

client = StripeClient("sk_test")


def indexed(rows):
    charge = client.charges.create(amount=100, currency="usd")

    # The one Python binding that does not belong to the scope it is written in. PEP 572 binds a
    # walrus in the scope *containing* the comprehension, so `charge` is local to the whole of
    # `report` and the line above raises UnboundLocalError -- the comprehension is a scope for
    # its `for` target and not for this.
    def report():
        early = charge.leaked
        picked = [(charge := row) for row in rows]
        return early, picked

    return report(), charge.status
