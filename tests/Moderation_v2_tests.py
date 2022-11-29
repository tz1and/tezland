import smartpy as sp

admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")
mod_mixin = sp.io.import_script_from_url("file:contracts/Moderation_v2.py")

class ModerationTest(
    admin_mixin.Administrable,
    mod_mixin.Moderation,
    sp.Contract):
    def __init__(self, administrator):
        admin_mixin.Administrable.__init__(self, administrator = administrator)
        mod_mixin.Moderation.__init__(self)


@sp.add_test(name = "Moderation_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("Moderation contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

    scenario.h2("Test Moderation")

    scenario.h3("Contract origination")
    moderation = ModerationTest(admin.address)
    scenario += moderation

    scenario.h3("set_moderation_contract")

    moderation.set_moderation_contract(sp.some(bob.address)).run(sender = bob, valid = False)
    scenario.verify(moderation.data.moderation_contract == sp.none)
    moderation.set_moderation_contract(sp.some(bob.address)).run(sender = admin)
    scenario.verify(moderation.data.moderation_contract == sp.some(bob.address))
    moderation.set_moderation_contract(sp.none).run(sender = admin)
    scenario.verify(moderation.data.moderation_contract == sp.none)
