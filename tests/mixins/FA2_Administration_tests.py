import smartpy as sp

from tz1and_contracts_smartpy.mixins.Administrable import Administrable
from contracts.mixins import FA2_Administration
from contracts import Tokens


class FA2_AdministrationTest(
    Administrable,
    FA2_Administration.FA2_Administration,
    sp.Contract):
    def __init__(self, administrator):
        sp.Contract.__init__(self)
        Administrable.__init__(self, administrator = administrator)
        FA2_Administration.FA2_Administration.__init__(self)


@sp.add_test(name = "FA2_Administration_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("FA2_Administration contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

    scenario.h2("Test FA2_Administration")

    scenario.h3("Contract origination")
    # create token for testing
    places_tokens = Tokens.tz1andPlaces(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += places_tokens

    fa2_admin = FA2_AdministrationTest(admin.address)
    scenario += fa2_admin

    scenario.verify(fa2_admin.data.administrator == admin.address)

    scenario.h3("accept_fa2_administrator")
    fa2_admin.accept_fa2_administrator([places_tokens.address]).run(sender = admin, valid = False, exception = "NOT_PROPOSED_ADMIN")
    fa2_admin.accept_fa2_administrator([places_tokens.address]).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    fa2_admin.accept_fa2_administrator([places_tokens.address]).run(sender = bob, valid = False, exception = "ONLY_ADMIN")

    # transfer to fa2_admin
    places_tokens.transfer_administrator(fa2_admin.address).run(sender = admin)
    scenario.verify(places_tokens.data.administrator == admin.address)
    scenario.verify(places_tokens.data.proposed_administrator == sp.some(fa2_admin.address))

    fa2_admin.accept_fa2_administrator([places_tokens.address]).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    fa2_admin.accept_fa2_administrator([places_tokens.address]).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    fa2_admin.accept_fa2_administrator([places_tokens.address]).run(sender = admin)

    scenario.verify(places_tokens.data.administrator == fa2_admin.address)
    scenario.verify(places_tokens.data.proposed_administrator == sp.none)

    scenario.h3("transfer_fa2_administrator")
    fa2_admin.transfer_fa2_administrator([sp.record(fa2 = places_tokens.address, proposed_fa2_administrator = bob.address)]).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    fa2_admin.transfer_fa2_administrator([sp.record(fa2 = places_tokens.address, proposed_fa2_administrator = bob.address)]).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    fa2_admin.transfer_fa2_administrator([sp.record(fa2 = places_tokens.address, proposed_fa2_administrator = bob.address)]).run(sender = admin)

    scenario.verify(places_tokens.data.administrator == fa2_admin.address)
    scenario.verify(places_tokens.data.proposed_administrator == sp.some(bob.address))

    places_tokens.accept_administrator().run(sender = admin, valid = False, exception = "NOT_PROPOSED_ADMIN")
    places_tokens.accept_administrator().run(sender = alice, valid = False, exception = "NOT_PROPOSED_ADMIN")
    places_tokens.accept_administrator().run(sender = bob)

    scenario.verify(places_tokens.data.administrator == bob.address)
    scenario.verify(places_tokens.data.proposed_administrator == sp.none)
