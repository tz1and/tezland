import smartpy as sp

upgrade_contract = sp.io.import_script_from_url("file:contracts/UpgradeTest.py")

def ep_update(self, params):
    sp.set_type(params.val, sp.TInt)
    self.data.counter -= params.val

@sp.add_test(name = "UpgradeTest_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    # create upgrade contract
    upgrade = upgrade_contract.UpgradeTest(admin.address) #admin.address, 
    scenario += upgrade

    # test entry
    upgrade.test_entry(val = sp.int(2)).run(sender = alice)

    # test view
    view_res = upgrade.test_view()
    scenario.verify(view_res == 2)

    # update
    upgrade.update_entry(sp.utils.wrap_entry_point("test_entry", ep_update)).run(sender = admin)