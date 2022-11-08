import smartpy as sp

dutch_contract = sp.io.import_script_from_url("file:contracts/TL_Dutch_v2.py")
minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter_v2.py")
token_factory_contract = sp.io.import_script_from_url("file:contracts/TL_TokenFactory.py")
token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")

@sp.add_test(name = "TL_Dutch_v2_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    carol = sp.test_account("Carol")
    scenario = sp.test_scenario()

    scenario.h1("Dutch auction contract v2")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob, carol])

    # create a FA2 and minter contract for testing
    scenario.h2("Create test env")

    scenario.h3("Tokens")
    items_tokens_legacy = tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens_legacy

    items_tokens = tokens.tz1andItems_v2(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    places_tokens = tokens.tz1andPlaces_v2(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += places_tokens

    scenario.h3("TokenRegistry")
    token_registry = token_registry_contract.TL_TokenRegistry(admin.address,
        sp.bytes("0x00"), sp.bytes("0x00"),
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += token_registry

    scenario.h3("Minter v2")
    minter = minter_contract.TL_Minter(admin.address, token_registry.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    scenario.h3("TokenFactory")
    token_factory = token_factory_contract.TL_TokenFactory(admin.address, token_registry.address, minter.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += token_factory
    scenario.register(token_factory.collection_contract)

    scenario.h3("registry permissions for factory, etc")
    token_registry.manage_permissions([sp.variant("add_permissions", [token_factory.address])]).run(sender=admin)
    token_registry.manage_public_collections([sp.variant("add_collections", [
        sp.record(contract = items_tokens_legacy.address, royalties_version = 1),
        sp.record(contract = items_tokens.address, royalties_version = 2),
    ])]).run(sender = admin)

    items_tokens_legacy.transfer_administrator(minter.address).run(sender = admin)
    minter.accept_fa2_administrator([items_tokens_legacy.address]).run(sender = admin)

    # mint some item tokens for testing
    minter.mint_public_v1(collection = items_tokens_legacy.address,
        to_ = bob.address,
        amount = 4,
        royalties = 250,
        contributors = [ sp.record(address=bob.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    item_bob = sp.nat(0)

    # mint some place tokens for testing
    places_tokens.mint([
        sp.record(
            to_ = bob.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        ),
        sp.record(
            to_ = alice.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        ),
        sp.record(
            to_ = carol.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        ),
        sp.record(
            to_ = admin.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        )
    ]).run(sender = admin)

    place_bob   = sp.nat(0)
    place_alice = sp.nat(1)
    place_carol = sp.nat(2)
    place_admin = sp.nat(3)

    # Test dutch auchtion

    scenario.h2("Test Dutch")

    # create places contract
    scenario.h3("Originate dutch contract")
    dutch = dutch_contract.TL_Dutch(admin.address, places_tokens.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += dutch

    # disable whitelist, it's enabled by defualt
    dutch.manage_whitelist([sp.variant("whitelist_enabled", False)]).run(sender=admin)
    scenario.verify(dutch.data.whitelist_enabled == False)

    # enabled secondary, it's disabled by default
    dutch.update_settings([sp.variant("secondary_enabled", True)]).run(sender=admin)
    scenario.verify(dutch.data.secondary_enabled == True)

    # set operators
    scenario.h3("Add operators")
    items_tokens_legacy.update_operators([
        sp.variant("add_operator", sp.record(
            owner = bob.address,
            operator = dutch.address,
            token_id = item_bob
        ))
    ]).run(sender = bob)

    places_tokens.update_operators([
        sp.variant("add_operator", sp.record(
            owner = bob.address,
            operator = dutch.address,
            token_id = place_bob
        ))
    ]).run(sender = bob)

    places_tokens.update_operators([
        sp.variant("add_operator", sp.record(
            owner = alice.address,
            operator = dutch.address,
            token_id = place_alice
        ))
    ]).run(sender = alice)

    places_tokens.update_operators([
        sp.variant("add_operator", sp.record(
            owner = carol.address,
            operator = dutch.address,
            token_id = place_carol
        ))
    ]).run(sender = carol)

    #
    # create
    #
    scenario.h3("Create")

    # incorrect start/end price
    dutch.create(token_id = place_bob,
        start_price = sp.tez(0),
        end_price = sp.tez(100),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(2),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(120),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(2),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    # incorrect start/end time
    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(120),
        start_time = sp.timestamp(0).add_minutes(2),
        end_time = sp.timestamp(0).add_minutes(2),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0).add_minutes(3),
        end_time = sp.timestamp(0).add_minutes(2),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    # Wrong owner
    dutch.create(token_id = place_alice,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = bob, valid = False, exception = "NOT_OWNER")

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = alice, valid = False, exception = "NOT_OWNER")

    # token not permitted
    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = items_tokens_legacy.address,
        extension = sp.none).run(sender = bob, valid = False, exception = "TOKEN_NOT_PERMITTED")

    balance_before = scenario.compute(places_tokens.get_balance(sp.record(owner = bob.address, token_id = place_bob)))

    # valid
    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = bob)

    balance_after = scenario.compute(places_tokens.get_balance(sp.record(owner = bob.address, token_id = place_bob)))
    scenario.verify(balance_after == balance_before)

    # invalid, already exists
    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = bob, valid = False, exception = "AUCTION_EXISTS")

    #
    # cancel
    #
    scenario.h3("Cancel")

    dutch.create(token_id = place_alice,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(2),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = alice)

    current_auction_key = sp.record(fa2 = places_tokens.address, token_id = place_alice, owner = alice.address)

    balance_before = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_alice)))

    # not owner
    dutch.cancel(auction_key = current_auction_key, extension = sp.none).run(sender = bob, valid = False, exception = "NOT_OWNER")
    # valid
    dutch.cancel(auction_key = current_auction_key, extension = sp.none).run(sender = alice)
    # already cancelled, wrong state
    dutch.cancel(auction_key = current_auction_key, extension = sp.none).run(sender = alice, valid = False) # missing item in map

    balance_after = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_alice)))
    scenario.verify(balance_after == balance_before)

    #
    # bid
    #
    scenario.h3("Bid")

    current_auction_key = sp.record(fa2 = places_tokens.address, token_id = place_bob, owner = bob.address)

    # try a couple of wrong amount bids at several times
    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0), valid = False)
    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(1), valid = False)
    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(2), valid = False)
    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(20), valid = False)
    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(40), valid = False)
    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(60), valid = False)
    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(80), valid = False)
    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(81), valid = False)

    balance_before = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_bob)))

    # valid
    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.tez(22), now=sp.timestamp(0).add_minutes(80))
    # valid but wrong state
    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.tez(22), now=sp.timestamp(0).add_minutes(80), valid = False)

    balance_after = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_bob)))
    scenario.verify(balance_after == (balance_before + 1))

    #
    # test some auction edge cases
    #
    scenario.h3("create/bid edge cases")

    # alice owns bobs place now.
    # create an auction that for 2 to 1 mutez.
    # used to fail on fee/royalties transfer.
    dutch.create(token_id = place_alice,
        start_price = sp.mutez(2),
        end_price = sp.mutez(1),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(5),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = alice, now=sp.timestamp(0))

    current_auction_key = sp.record(fa2 = places_tokens.address, token_id = place_alice, owner = alice.address)

    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.mutez(1), now=sp.timestamp(0).add_minutes(80))

    # create an auction that lasts 5 second.
    # duration must be > granularity
    dutch.create(token_id = place_alice,
        start_price = sp.tez(2),
        end_price = sp.tez(1),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_seconds(5),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = alice, now=sp.timestamp(0), valid = False, exception = "INVALID_PARAM")

    # create an auction with end price 0.
    # duration must be > granularity
    dutch.create(token_id = place_alice,
        start_price = sp.tez(2),
        end_price = sp.tez(0),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(5),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = alice, now=sp.timestamp(0))

    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.mutez(0), now=sp.timestamp(0).add_minutes(80))

    # TODO: more failure cases?

    #
    # views
    #
    scenario.h3("Views")

    # alice should own bobs token now
    # set operators and create a new auction
    places_tokens.update_operators([
        sp.variant("add_operator", sp.record(
            owner = alice.address,
            operator = dutch.address,
            token_id = place_bob
        ))
    ]).run(sender = alice)

    auction_start_time = sp.timestamp(0).add_days(2)

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = auction_start_time,
        end_time = auction_start_time.add_minutes(80),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = alice, now=sp.timestamp(0))

    current_auction_key = sp.record(fa2 = places_tokens.address, token_id = place_bob, owner = alice.address)

    auction_info = dutch.get_auction(current_auction_key)
    scenario.show(auction_info)

    # get_auction_price
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=sp.timestamp(0)) == sp.tez(100))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time) == sp.tez(100))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(10)) == sp.tez(90))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(20)) == sp.tez(80))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(30)) == sp.tez(70))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(40)) == sp.tez(60))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(50)) == sp.tez(50))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(60)) == sp.tez(40))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(70)) == sp.tez(30))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(80)) == sp.tez(20))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(90)) == sp.tez(20))

    dutch.cancel(auction_key = current_auction_key, extension = sp.none).run(sender = alice)

    dutch.create(token_id = place_bob,
        start_price = sp.tez(20),
        end_price = sp.tez(20),
        start_time = auction_start_time,
        end_time = auction_start_time.add_minutes(80),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = alice, now=sp.timestamp(0))

    auction_info = dutch.get_auction(current_auction_key)
    scenario.show(auction_info)

    # get_auction_price
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=sp.timestamp(0)) == sp.tez(20))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time) == sp.tez(20))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(10)) == sp.tez(20))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(20)) == sp.tez(20))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(30)) == sp.tez(20))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(40)) == sp.tez(20))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(50)) == sp.tez(20))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(60)) == sp.tez(20))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(70)) == sp.tez(20))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(80)) == sp.tez(20))
    scenario.verify(scenario.compute(dutch.get_auction_price(current_auction_key), now=auction_start_time.add_minutes(90)) == sp.tez(20))

    #
    # update granularity
    #
    scenario.h3("update granularity")
    
    dutch.update_settings([sp.variant("granularity", 35)]).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    dutch.update_settings([sp.variant("granularity", 250)]).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    scenario.verify(dutch.data.granularity == sp.nat(60))
    dutch.update_settings([sp.variant("granularity", 45)]).run(sender = admin)
    scenario.verify(dutch.data.granularity == sp.nat(45))

    scenario.table_of_contents()

    #
    # test paused
    #
    scenario.h3("pausing")
    scenario.verify(dutch.data.paused == False)
    dutch.update_settings([sp.variant("paused", True)]).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    dutch.update_settings([sp.variant("paused", True)]).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    dutch.update_settings([sp.variant("paused", True)]).run(sender = admin)
    scenario.verify(dutch.data.paused == True)

    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.mutez(20), now=sp.timestamp(0).add_minutes(80), valid = False, exception = "ONLY_UNPAUSED")

    dutch.cancel(auction_key = current_auction_key, extension = sp.none).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")

    dutch.update_settings([sp.variant("paused", False)]).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    dutch.update_settings([sp.variant("paused", False)]).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    dutch.update_settings([sp.variant("paused", False)]).run(sender = admin)
    scenario.verify(dutch.data.paused == False)

    dutch.cancel(auction_key = current_auction_key, extension = sp.none).run(sender = alice)

    #
    # test secondary disabled
    #

    # disable secondary.
    dutch.update_settings([sp.variant("secondary_enabled", False)]).run(sender=bob, valid = False, exception = "ONLY_ADMIN")
    dutch.update_settings([sp.variant("secondary_enabled", False)]).run(sender=admin)
    scenario.verify(dutch.data.secondary_enabled == False)
    scenario.verify(dutch.is_secondary_enabled() == False)

    # only admin can create auctions is secondary is disabled
    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = alice, valid = False, exception = "ONLY_ADMIN")

    places_tokens.update_operators([
        sp.variant("add_operator", sp.record(
            owner = admin.address,
            operator = dutch.address,
            token_id = place_admin
        ))
    ]).run(sender = admin)

    #
    # test secondary enabled & whitelist enabled
    #

    # enabled whitelist.
    dutch.manage_whitelist([sp.variant("whitelist_enabled", True)]).run(sender=admin)
    scenario.verify(dutch.data.whitelist_enabled == True)

    # enable secondary.
    dutch.update_settings([sp.variant("secondary_enabled", True)]).run(sender=admin)
    scenario.verify(dutch.data.secondary_enabled == True)
    scenario.verify(dutch.is_secondary_enabled() == True)

    # If secondary and whitelist are enabled, anyone can create auctions,
    # and anyone can bid on them reglardless of their whitelist status.
    dutch.create(token_id = place_carol,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = carol, now=sp.timestamp(0))

    current_auction_key = sp.record(fa2 = places_tokens.address, token_id = place_carol, owner = carol.address)

    # furthermore, bidding on a non-whitelist auction should not remove you from the whitelist.
    dutch.manage_whitelist([sp.variant("whitelist_add", [carol.address])]).run(sender=admin)
    scenario.verify(dutch.data.whitelist.contains(carol.address))

    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = bob, amount = sp.tez(20), now=sp.timestamp(0).add_minutes(80))

    scenario.verify(dutch.data.whitelist.contains(carol.address))

    #
    # test whitelist
    #

    # If whitelist is enabled, only whitelisted can bid on admin created auctions.
    dutch.create(token_id = place_admin,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = admin, now=sp.timestamp(0))

    current_auction_key = sp.record(fa2 = places_tokens.address, token_id = place_admin, owner = admin.address)

    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.tez(20), now=sp.timestamp(0).add_minutes(80), valid = False, exception = "ONLY_WHITELISTED")

    # bidding on a whitelist auction will remove you from the whitelist.
    dutch.manage_whitelist([sp.variant("whitelist_add", [alice.address])]).run(sender=admin)
    scenario.verify(dutch.data.whitelist.contains(alice.address))

    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.tez(20), now=sp.timestamp(0).add_minutes(80))
    scenario.verify(~dutch.data.whitelist.contains(alice.address))

    # disable whitelist.
    dutch.manage_whitelist([sp.variant("whitelist_enabled", False)]).run(sender=admin)
    scenario.verify(dutch.data.whitelist_enabled == False)

    #
    # set_permitted_fa2
    #
    scenario.h3("set_fa2_permitted")

    dutch.create(token_id = item_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = items_tokens_legacy.address,
        extension = sp.none).run(sender = bob, now = sp.timestamp(0), valid = False, exception = "TOKEN_NOT_PERMITTED")

    add_permitted = sp.list([sp.variant("add_permitted",
        sp.record(
            fa2 = items_tokens_legacy.address,
            props = sp.record(
                whitelist_enabled = True,
                whitelist_admin = admin.address)))])

    dutch.set_fa2_permitted(add_permitted).run(sender = admin)

    dutch.create(token_id = item_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = items_tokens_legacy.address,
        extension = sp.none).run(sender = bob, now = sp.timestamp(0))

    current_auction_key = sp.record(fa2 = items_tokens_legacy.address, token_id = item_bob, owner = bob.address)

    dutch.bid(auction_key = current_auction_key, extension = sp.none).run(sender = alice, amount = sp.tez(20), now=sp.timestamp(0).add_minutes(80))

    # TODO: check roaylaties paid, token transferred