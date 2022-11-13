import smartpy as sp

dutch_contract = sp.io.import_script_from_url("file:contracts/upgrades/TL_Dutch_v1_1.py")
minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter.py")
tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")

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
    items_tokens = tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    places_tokens = tokens.tz1andPlaces(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += places_tokens

    minter = minter_contract.TL_Minter(admin.address, items_tokens.address, places_tokens.address,
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
    dutch = dutch_contract.TL_Dutch_v1_1(admin.address, items_tokens.address, places_tokens.address,
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
