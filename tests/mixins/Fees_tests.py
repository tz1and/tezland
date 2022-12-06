import smartpy as sp

from contracts.mixins.Administrable import Administrable
from contracts.mixins.MetaSettings import MetaSettings
from contracts.mixins import Fees


class FeesTest(
    Administrable,
    Fees.Fees,
    sp.Contract):
    def __init__(self, administrator, fees_to):
        Administrable.__init__(self, administrator = administrator)
        Fees.Fees.__init__(self, fees_to = fees_to)


class FeesTestMetaSettings(
    FeesTest,
    MetaSettings):
    def __init__(self, administrator, fees_to):
        self.available_settings = []

        FeesTest.__init__(self, administrator = administrator, fees_to = fees_to)
        MetaSettings.__init__(self)


@sp.add_test(name = "Fees_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("Fees contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

    scenario.h2("Test Fees")

    scenario.h3("Contract origination")
    fees = FeesTest(admin.address, admin.address)
    scenario += fees

    # Check default
    scenario.verify(fees.data.fees == sp.nat(25))
    scenario.verify(fees.data.fees_to == admin.address)

    #
    # update_fees
    #
    scenario.h3("update_fees")

    # Test failiure cases
    for t in [(bob, sp.nat(35), "ONLY_ADMIN"), (admin, sp.nat(250), "FEE_ERROR")]:
        sender, fee_amount, exception = t
        fees.update_fees(fee_amount).run(sender = sender, valid = False, exception = exception)

    fees.update_fees(45).run(sender = admin)
    scenario.verify(fees.data.fees == sp.nat(45))

    scenario.h3("update_fees_to")

    # No permission for anyone but admin
    for acc in [alice, bob, admin]:
        fees.update_fees_to(bob.address).run(
            sender = acc,
            valid = (True if acc is admin else False),
            exception = (None if acc is admin else "ONLY_ADMIN"))

        if acc is admin: scenario.verify(fees.data.fees_to == bob.address)

    # Test meta settings
    scenario.h2("Test Fees - MetaSettings")

    scenario.h3("Contract origination")
    fees_meta = FeesTestMetaSettings(admin.address, admin.address)
    scenario += fees_meta

    # Check default
    scenario.verify(fees_meta.data.fees == sp.nat(25))
    scenario.verify(fees_meta.data.fees_to == admin.address)

    #
    # update_settings
    #
    scenario.h3("update_settings")

    # Test failiure cases
    for t in [(bob, sp.nat(35), "ONLY_ADMIN"), (admin, sp.nat(250), "FEE_ERROR")]:
        sender, fee_amount, exception = t
        fees_meta.update_settings([sp.variant("fees", fee_amount)]).run(sender = sender, valid = False, exception = exception)

    fees_meta.update_settings([sp.variant("fees", sp.nat(45))]).run(sender = admin)
    scenario.verify(fees_meta.data.fees == sp.nat(45))

    # No permission for anyone but admin
    for acc in [alice, bob, admin]:
        fees_meta.update_settings([sp.variant("fees_to", bob.address)]).run(
            sender = acc,
            valid = (True if acc is admin else False),
            exception = (None if acc is admin else "ONLY_ADMIN"))

        if acc is admin: scenario.verify(fees_meta.data.fees_to == bob.address)