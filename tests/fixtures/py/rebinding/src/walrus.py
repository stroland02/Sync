from stripe import StripeClient

client = StripeClient("sk_test")


def indexed(rows):
    charge = client.charges.create(amount=100, currency="usd")

    # A walrus binds in the scope holding the expression, not in the `if` it is written in --
    # Python has no block scope -- so `charge` is local to the whole of `pick` exactly as a
    # plain assignment on the same line would have made it.
    def pick():
        if (charge := rows[0]):
            return charge.leaked
        return None

    return pick(), charge.status
