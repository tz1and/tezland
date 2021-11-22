import smartpy as sp

manager_contract = sp.io.import_script_from_url("file:contracts/Manageable.py")

class UpgradeTest(manager_contract.Manageable):
    def __init__(self, manager):
        self.init_storage(
            manager = manager,
            counter = sp.int(0)
            )

    @sp.entry_point
    def update_entry(self, new_code):
        self.onlyManager()
        sp.set_entry_point("test_entry", new_code)

    @sp.entry_point(lazify = True)
    def test_entry(self, params):
        sp.set_type(params.val, sp.TInt)
        self.data.counter += params.val

    @sp.onchain_view()
    def test_view(self):
        # sp.result is used to return the view result (the contract storage in this case)
        sp.result(self.data.counter)

# A a compilation target (produces compiled code)
#sp.add_compilation_target("TL_Minter", TL_Minter(
    #sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV"), # Manager
#    sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV") # Token
#    ))
