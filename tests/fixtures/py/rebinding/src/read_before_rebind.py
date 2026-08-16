from stripe import StripeClient

client = StripeClient("sk_test")


def indexed(rows):
    charge = client.charges.create(amount=100, currency="usd")

    # Both reads in `summarise` raise UnboundLocalError: assigning `charge` anywhere in the
    # body makes it local to the whole body, including the line above the assignment.
    def summarise():
        early = charge.leaked
        charge = rows[0]
        return early, charge.also_leaked

    return summarise, charge.status
