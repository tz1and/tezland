import smartpy as sp

admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")


class Fees(admin_mixin.Administrable):
    def __init__(self, administrator, meta_settings = False):
        self.update_initial_storage(
            fees = sp.nat(25),
            fees_to = administrator
        )

        if meta_settings:
            self.available_settings.extend([
                ("fees", sp.TNat, lambda x: sp.verify(x <= 60, message = "FEE_ERROR")),
                ("fees_to", sp.TAddress, None)
            ])
            setattr(self, "update_fees", sp.entry_point(None, None))
            setattr(self, "update_fees_to", sp.entry_point(None, None))

        admin_mixin.Administrable.__init__(self, administrator = administrator)

    @sp.entry_point
    def update_fees(self, fees):
        """Call to set fees in permille or fee recipient.
        Fees must be <= than 60 permille.
        """
        sp.set_type(fees, sp.TNat)
        self.onlyAdministrator()
        sp.verify(fees <= 60, message = "FEE_ERROR") # let's not get greedy
        self.data.fees = fees

    @sp.entry_point
    def update_fees_to(self, fees_to):
        """Set fee recipient.
        """
        sp.set_type(fees_to, sp.TAddress)
        self.onlyAdministrator()
        self.data.fees_to = fees_to

