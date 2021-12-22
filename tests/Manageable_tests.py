import smartpy as sp

manager_contract = sp.io.import_script_from_url("file:contracts/Manageable.py")

# TODO: make pausable?
class ManageableTest(manager_contract.Manageable):
    def __init__(self, manager):
        self.init_storage(manager = manager)

    @sp.entry_point
    def testOnlyManager(self):
        self.onlyManager()

    @sp.entry_point
    def testIsManager(self, address):
        sp.set_type(address, sp.TAddress)
        sp.if ~self.isManager(address):
            sp.verify(False, "error")


@sp.add_test(name = "Manageable_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("Manageable contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

    scenario.h2("Test Manageable")

    scenario.h3("Contract origination")
    manageable = ManageableTest(admin.address)
    scenario += manageable

    scenario.verify(manageable.data.manager == admin.address)

    scenario.h3("onlyManager")
    manageable.testOnlyManager().run(sender = bob, valid = False)
    manageable.testOnlyManager().run(sender = alice, valid = False)
    manageable.testOnlyManager().run(sender = admin)

    scenario.h3("isManager")
    manageable.testIsManager(bob.address).run(sender = bob, valid = False)
    manageable.testIsManager(bob.address).run(sender = alice, valid = False)
    manageable.testIsManager(bob.address).run(sender = admin, valid = False)
    manageable.testIsManager(admin.address).run(sender = alice)
    manageable.testIsManager(admin.address).run(sender = bob)
    manageable.testIsManager(admin.address).run(sender = admin)

    scenario.h3("set_manager")
    manageable.set_manager(bob.address).run(sender = bob, valid = False)
    manageable.set_manager(bob.address).run(sender = alice, valid = False)
    manageable.set_manager(bob.address).run(sender = admin)

    scenario.verify(manageable.data.manager == bob.address)

    manageable.set_manager(admin.address).run(sender = admin, valid = False)