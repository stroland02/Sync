class Injected:
    def __init__(self, given):
        self.given = given

    def charge(self, amount: int):
        result = self.given.charges.create(amount=amount)
        return result.id
