from stripe import StripeClient

client = StripeClient("sk_test")


def indexed(rows):
    charge = client.charges.create(amount=100, currency="usd")

    # `charge += 1` is what makes `charge` local to `accumulate` for the whole of its body,
    # so `charge.leaked` below raises UnboundLocalError rather than reading the outer object.
    # The file is about what the compiler decides, not about code that runs.
    def accumulate():
        charge += 1
        return charge.leaked

    return accumulate, charge.status
