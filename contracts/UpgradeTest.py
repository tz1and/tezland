import smartpy as sp

admin_contract = sp.io.import_script_from_url("file:contracts/Administrable.py")

class UpgradeTest(admin_contract.Administrable):
    def __init__(self, administrator):
        self.init_storage(
            counter = sp.int(0)
        )
        admin_contract.Administrable.__init__(self, administrator = administrator)

    @sp.entry_point
    def update_entry(self, new_code):
        self.onlyAdministrator()
        sp.set_entry_point("test_entry", new_code)

    @sp.entry_point(lazify = True)
    def test_entry(self, params):
        sp.set_type(params.val, sp.TInt)
        self.data.counter += params.val

    @sp.onchain_view(pure=True)
    def test_view(self):
        # sp.result is used to return the view result (the contract storage in this case)
        sp.result(self.data.counter)

# A a compilation target (produces compiled code)
#sp.add_compilation_target("TL_Minter", TL_Minter(
    #sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV"), # Manager
#    sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV") # Token
#    ))
