import smartpy as sp

manager_contract = sp.io.import_script_from_url("file:contracts/Manageable.py")


class Fees(manager_contract.Manageable):
    #def __init__(self, manager):
    #    self.init_storage(
    #        managers = sp.set([manager], t = sp.TAddress)
    #        )

    @sp.entry_point
    def set_fees(self, update):
        """Call to set fees in permille or fee recipient.
        Fees must be <= than 60 permille.
        """
        sp.set_type(update, sp.TVariant(
            update_fees = sp.TNat,
            update_fees_to = sp.TAddress
        ))
        self.onlyManager()
        with update.match_cases() as arg:
            with arg.match("update_fees") as upd:
                sp.verify(upd <= 60, message = "FEE_ERROR") # let's not get greedy
                self.data.fees = upd
            with arg.match("update_fees_to") as upd:
                self.data.fees_to = upd
