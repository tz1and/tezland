import smartpy as sp

from tezosbuilders_contracts_smartpy.mixins.Administrable import Administrable
from contracts.mixins import Moderation


class ModerationTest(
    Administrable,
    Moderation.Moderation,
    sp.Contract):
    def __init__(self, administrator, moderation_contract):
        sp.Contract.__init__(self)
        Administrable.__init__(self, administrator = administrator)
        Moderation.Moderation.__init__(self, moderation_contract = moderation_contract)


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
    moderation = ModerationTest(admin.address, admin.address)
    scenario += moderation

    scenario.h3("set_moderation_contract")

    moderation.set_moderation_contract(bob.address).run(sender = bob, valid = False)
    scenario.verify(moderation.data.moderation_contract == admin.address)
    moderation.set_moderation_contract(bob.address).run(sender = admin)
    scenario.verify(moderation.data.moderation_contract == bob.address)