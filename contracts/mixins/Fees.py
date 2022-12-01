import smartpy as sp


# Required mixins: Administrable
class Fees:
    def __init__(self, fees_to):
        self.update_initial_storage(
            fees = sp.nat(25),
            fees_to = fees_to
        )

        if hasattr(self, 'available_settings'):
            self.available_settings.extend([
                ("fees", sp.TNat, lambda x: sp.verify(x <= 60, message = "FEE_ERROR")),
                ("fees_to", sp.TAddress, None)
            ])
        else:
            def update_fees(self, fees):
                """Call to set fees in permille or fee recipient.
                Fees must be <= than 60 permille.
                """
                sp.set_type(fees, sp.TNat)
                self.onlyAdministrator()
                sp.verify(fees <= 60, message = "FEE_ERROR") # let's not get greedy
                self.data.fees = fees

            def update_fees_to(self, fees_to):
                """Set fee recipient.
                """
                sp.set_type(fees_to, sp.TAddress)
                self.onlyAdministrator()
                self.data.fees_to = fees_to

            self.update_fees = sp.entry_point(update_fees)
            self.update_fees_to = sp.entry_point(update_fees_to)

