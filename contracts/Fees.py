import smartpy as sp

manager_contract = sp.io.import_script_from_url("file:contracts/Manageable.py")


class Fees(manager_contract.Manageable):
    #def __init__(self, manager):
    #    self.init_storage(
    #        managers = sp.set([manager], t = sp.TAddress)
    #        )

    @sp.entry_point
    def update_fees(self, fees):
        """Call to set fees in permille or fee recipient.
        Fees must be <= than 60 permille.
        """
        sp.set_type(fees, sp.TNat)
        self.onlyManager()
        sp.verify(fees <= 60, message = "FEE_ERROR") # let's not get greedy
        self.data.fees = fees

    @sp.entry_point
    def update_fees_to(self, fees_to):
        """Set fee recipient.
        """
        sp.set_type(fees_to, sp.TAddress)
        self.onlyManager()
        self.data.fees_to = fees_to

