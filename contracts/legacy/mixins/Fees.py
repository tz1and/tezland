import smartpy as sp


# Required mixins: Administrable
class Fees:
    def __init__(self, fees_to):
        self.update_initial_storage(
            fees = sp.nat(25),
            fees_to = sp.set_type_expr(fees_to, sp.TAddress)
        )

    @sp.entry_point(parameter_type=sp.TNat)
    def update_fees(self, fees):
        """Call to set fees in permille or fee recipient.
        Fees must be <= than 60 permille.
        """
        sp.set_type(fees, sp.TNat)
        self.onlyAdministrator()
        sp.verify(fees <= 60, message = "FEE_ERROR") # let's not get greedy
        self.data.fees = fees

    @sp.entry_point(parameter_type=sp.TAddress)
    def update_fees_to(self, fees_to):
        """Set fee recipient.
        """
        sp.set_type(fees_to, sp.TAddress)
        self.onlyAdministrator()
        self.data.fees_to = fees_to

