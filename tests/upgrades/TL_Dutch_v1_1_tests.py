import smartpy as sp

from contracts.upgrades import TL_Dutch_v1_1
from contracts import TL_Minter, Tokens


@sp.add_test(name = "TL_Dutch_v1_1_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    carol = sp.test_account("Carol")
    scenario = sp.test_scenario()

    scenario.h1("Dutch auction contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob, carol])

    # create a FA2 and minter contract for testing
    scenario.h2("Create test env")
    items_tokens = Tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    places_tokens = Tokens.tz1andPlaces(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += places_tokens

    minter = TL_Minter.TL_Minter(admin.address, items_tokens.address, places_tokens.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    items_tokens.transfer_administrator(minter.address).run(sender = admin)
    places_tokens.transfer_administrator(minter.address).run(sender = admin)
    minter.accept_fa2_administrator([items_tokens.address, places_tokens.address]).run(sender = admin)

    # mint some item tokens for testing
    minter.mint_Item(to_ = bob.address,
        amount = 4,
        royalties = 250,
        contributors = [ sp.record(address=bob.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    item_bob = sp.nat(0)

    # mint some place tokens for testing
    minter.mint_Place([
        sp.record(
            to_ = bob.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        ),
        sp.record(
            to_ = alice.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        )
    ]).run(sender = admin)

    place_bob   = sp.nat(0)
    place_alice = sp.nat(1)

    # Test dutch auchtion

    scenario.h2("Test Dutch v1.1")

    # create places contract
    scenario.h3("Originate dutch contract")
    dutch = TL_Dutch_v1_1.TL_Dutch_v1_1(admin.address, items_tokens.address, places_tokens.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += dutch

    # disable whitelist, it's enabled by defualt
    dutch.manage_whitelist([sp.variant("whitelist_enabled", False)]).run(sender=admin)
    scenario.verify(dutch.data.whitelist_enabled == False)

    # enabled secondary, it's disabled by default
    dutch.set_secondary_enabled(True).run(sender=admin)
    scenario.verify(dutch.data.secondary_enabled == True)

    # set operators
    scenario.h3("Add operators")
    items_tokens.update_operators([
        sp.variant("add_operator", sp.record(
            owner = bob.address,
            operator = dutch.address,
            token_id = item_bob
        ))
    ]).run(sender = bob, valid = True)

    places_tokens.update_operators([
        sp.variant("add_operator", sp.record(
            owner = bob.address,
            operator = dutch.address,
            token_id = place_bob
        ))
    ]).run(sender = bob, valid = True)

    places_tokens.update_operators([
        sp.variant("add_operator", sp.record(
            owner = alice.address,
            operator = dutch.address,
            token_id = place_alice
        ))
    ]).run(sender = alice, valid = True)

    #
    # upgraded cancel ep
    #
    scenario.h3("Cancel")

    # valid
    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = bob)

    auction_bob = sp.nat(0)

    dutch.create(token_id = place_alice,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(2),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = alice)

    auction_alice = sp.nat(1)

    balance_bob_before = scenario.compute(places_tokens.get_balance(sp.record(owner = bob.address, token_id = place_bob)))
    balance_alice_before = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_alice)))

    # not owner
    dutch.cancel(auction_id = auction_bob, extension = sp.none).run(sender = alice, valid = False, exception = "NOT_OWNER")
    # valid - admin
    dutch.cancel(auction_id = auction_bob, extension = sp.none).run(sender = admin)
    # already cancelled, wrong state
    dutch.cancel(auction_id = auction_bob, extension = sp.none).run(sender = admin, valid = False) # missing item in map

    balance_bob_after = scenario.compute(places_tokens.get_balance(sp.record(owner = bob.address, token_id = place_bob)))
    scenario.verify(balance_bob_after == (balance_bob_before + 1))

    # not owner
    dutch.cancel(auction_id = auction_alice, extension = sp.none).run(sender = bob, valid = False, exception = "NOT_OWNER")
    # valid - owner
    dutch.cancel(auction_id = auction_alice, extension = sp.none).run(sender = alice)
    # already cancelled, wrong state
    dutch.cancel(auction_id = auction_alice, extension = sp.none).run(sender = alice, valid = False) # missing item in map

    balance_alice_after = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_alice)))
    scenario.verify(balance_alice_after == (balance_alice_before + 1))


    scenario.h3("Update metadata (bid)")

    # no access
    dutch.bid(auction_id = 0, extension = sp.some({"metadata_uri": sp.utils.bytes_of_string("https://newexample.com")})).run(sender = bob, valid = False, exception = "ONLY_ADMIN")

    # wrong format
    dutch.bid(auction_id = 0, extension = sp.none).run(sender = admin, valid = False, exception = "NO_EXT_PARAMS")
    dutch.bid(auction_id = 0, extension = sp.some({"metadata_bla": sp.utils.bytes_of_string("https://newexample.com")})).run(sender = admin, valid = False, exception = "NO_METADATA_URI")

    # valid
    dutch.bid(auction_id = 0, extension = sp.some({"metadata_uri": sp.utils.bytes_of_string("https://newexample.com")})).run(sender = admin)
    scenario.verify(dutch.data.metadata.get("") == sp.utils.bytes_of_string("https://newexample.com"))