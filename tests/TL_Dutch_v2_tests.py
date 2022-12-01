import smartpy as sp

dutch_contract = sp.io.import_script_from_url("file:contracts/TL_Dutch_v2.py")
minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter_v2.py")
token_factory_contract = sp.io.import_script_from_url("file:contracts/TL_TokenFactory.py")
token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
legacy_royalties_contract = sp.io.import_script_from_url("file:contracts/TL_LegacyRoyalties.py")
royalties_adapter_contract = sp.io.import_script_from_url("file:contracts/TL_RoyaltiesAdapter.py")
world_contract = sp.io.import_script_from_url("file:contracts/TL_World_v2.py")
tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")

@sp.add_test(name = "TL_Dutch_v2_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    carol = sp.test_account("Carol")
    royalties_key = sp.test_account("Royalties")
    collections_key = sp.test_account("Collections")
    scenario = sp.test_scenario()

    scenario.h1("Dutch auction contract v2")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob, carol])

    # create a FA2 and minter contract for testing
    scenario.h2("Create test env")

    scenario.h3("Tokens")
    items_tokens = tokens.tz1andItems_v2(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    places_tokens = tokens.tz1andPlaces_v2(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += places_tokens

    interiors_tokens = tokens.tz1andInteriors(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += interiors_tokens

    scenario.h3("TokenRegistry")
    registry = token_registry_contract.TL_TokenRegistry(admin.address, collections_key.public_key,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += registry

    scenario.h3("LegacyRoyalties")
    legacy_royalties = legacy_royalties_contract.TL_LegacyRoyalties(admin.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += legacy_royalties

    scenario.h2("RoyaltiesAdapter")
    royalties_adapter = royalties_adapter_contract.TL_RoyaltiesAdapter(
        registry.address, legacy_royalties.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += royalties_adapter

    scenario.h3("Minter v2")
    minter = minter_contract.TL_Minter_v2(admin.address, registry.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    scenario.h3("TokenFactory")
    token_factory = token_factory_contract.TL_TokenFactory(admin.address, registry.address, minter.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += token_factory
    scenario.register(token_factory.collection_contract)

    scenario.h2("World v2")
    world = world_contract.TL_World_v2(admin.address, registry.address, royalties_adapter.address, False, items_tokens.address,
        metadata = sp.utils.metadata_of_url("https://example.com"), name = "Test World", description = "A world for testing",
        debug_asserts = True)
    scenario += world

    scenario.h3("registry permissions for factory, etc")
    registry.manage_permissions([sp.variant("add_permissions", sp.set([token_factory.address]))]).run(sender=admin)
    registry.manage_collections([sp.variant("add_public", {items_tokens.address: 2})]).run(sender = admin)

    items_tokens.transfer_administrator(minter.address).run(sender = admin)
    minter.accept_fa2_administrator([items_tokens.address]).run(sender = admin)

    world.set_allowed_place_token(sp.list([
        sp.variant("add", {
            places_tokens.address: sp.record(chunk_limit = 1, chunk_item_limit = 64),
            interiors_tokens.address: sp.record(chunk_limit = 1, chunk_item_limit = 64)
        })
    ])).run(sender = admin)

    # mint some item tokens for testing
    #minter.mint_public(collection = items_tokens.address,
    #    to_ = bob.address,
    #    amount = 4,
    #    royalties = [ sp.record(address=bob.address, share=sp.nat(250)) ],
    #    metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    #item_bob = sp.nat(0)

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
        ),
        sp.record(
            to_ = bob.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        )
    ]).run(sender = admin)

    place_bob   = sp.nat(0)
    place_alice = sp.nat(1)
    place_carol = sp.nat(2)
    place_admin = sp.nat(3)
    place_bob_no_operator = sp.nat(4)

    # mint some interiors for testing
    interiors_tokens.mint([
        sp.record(
            to_ = bob.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        )
    ]).run(sender = admin)

    interior_bob   = sp.nat(0)

    # Test dutch auchtion

    scenario.h2("Test Dutch")

    # create places contract
    scenario.h3("Originate dutch contract")
    dutch = dutch_contract.TL_Dutch_v2(admin.address, world.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += dutch

    # enabled secondary, it's disabled by default
    dutch.update_settings([sp.variant("secondary_enabled", True)]).run(sender=admin)
    scenario.verify(dutch.data.secondary_enabled == True)

    # some useful expressions for permitted fa2
    add_permitted_fa2_wl_enabled = sp.list([sp.variant("add_permitted",
        { places_tokens.address: sp.record(
                whitelist_enabled = True,
                whitelist_admin = admin.address) })])

    add_permitted_fa2_wl_disabled = sp.list([sp.variant("add_permitted",
        { places_tokens.address: sp.record(
                whitelist_enabled = False,
                whitelist_admin = admin.address) })])

    # permit fa2 and disable whitelist for it
    dutch.manage_whitelist(add_permitted_fa2_wl_disabled).run(sender = admin)
    scenario.verify(dutch.data.permitted_fa2.get(places_tokens.address).whitelist_enabled == False)

    # set operators
    scenario.h3("Add operators")
    #items_tokens.update_operators([
    #    sp.variant("add_operator", sp.record(
    #        owner = bob.address,
    #        operator = dutch.address,
    #        token_id = item_bob
    #    ))
    #]).run(sender = bob)

    interiors_tokens.update_operators([
        sp.variant("add_operator", sp.record(
            owner = bob.address,
            operator = dutch.address,
            token_id = interior_bob
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

    places_tokens.update_operators([
        sp.variant("add_operator", sp.record(
            owner = admin.address,
            operator = dutch.address,
            token_id = place_admin
        ))
    ]).run(sender = admin)

    #
    # create
    #
    scenario.h3("Create")

    # incorrect start/end price
    dutch.create(
        auction_key = sp.record(
            token_id = place_bob,
            fa2 = places_tokens.address,
            owner = bob.address),
        auction = sp.record(
            start_price = sp.tez(0),
            end_price = sp.tez(100),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(2)),
        ext = sp.none).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    dutch.create(
        auction_key = sp.record(
            token_id = place_bob,
            fa2 = places_tokens.address,
            owner = bob.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(120),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(2)),
        ext = sp.none).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    # incorrect start/end time
    dutch.create(
        auction_key = sp.record(
            token_id = place_bob,
            fa2 = places_tokens.address,
            owner = bob.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(120),
            start_time = sp.timestamp(0).add_minutes(2),
            end_time = sp.timestamp(0).add_minutes(2)),
        ext = sp.none).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    dutch.create(
        auction_key = sp.record(
            token_id = place_bob,
            fa2 = places_tokens.address,
            owner = bob.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(20),
            start_time = sp.timestamp(0).add_minutes(3),
            end_time = sp.timestamp(0).add_minutes(2)),
        ext = sp.none).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    # Wrong owner
    dutch.create(
        auction_key = sp.record(
            token_id = place_bob,
            fa2 = places_tokens.address,
            owner = alice.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(20),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(80)),
        ext = sp.none).run(sender = bob, valid = False, exception = "NOT_OWNER")

    dutch.create(
        auction_key = sp.record(
            token_id = place_bob,
            fa2 = places_tokens.address,
            owner = bob.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(20),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(80)),
        ext = sp.none).run(sender = alice, valid = False, exception = "NOT_OWNER")

    dutch.create(
        auction_key = sp.record(
            token_id = place_bob_no_operator,
            fa2 = places_tokens.address,
            owner = bob.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(20),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(80)),
        ext = sp.none).run(sender = bob, valid = False, exception = "NOT_OPERATOR")

    # token not permitted
    dutch.create(
        auction_key = sp.record(
            token_id = place_bob,
            fa2 = items_tokens.address,
            owner = bob.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(20),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(80)),
        ext = sp.none).run(sender = bob, valid = False, exception = "TOKEN_NOT_PERMITTED")

    balance_before = scenario.compute(places_tokens.get_balance(sp.record(owner = bob.address, token_id = place_bob)))

    # valid
    dutch.create(
        auction_key = sp.record(
            token_id = place_bob,
            fa2 = places_tokens.address,
            owner = bob.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(20),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(80)),
        ext = sp.none).run(sender = bob)

    balance_after = scenario.compute(places_tokens.get_balance(sp.record(owner = bob.address, token_id = place_bob)))
    scenario.verify(balance_after == balance_before)

    # invalid, already exists
    dutch.create(
        auction_key = sp.record(
            token_id = place_bob,
            fa2 = places_tokens.address,
            owner = bob.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(20),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(80)),
        ext = sp.none).run(sender = bob, valid = False, exception = "AUCTION_EXISTS")

    #
    # cancel
    #
    scenario.h3("Cancel")

    dutch.create(
        auction_key = sp.record(
            token_id = place_alice,
            fa2 = places_tokens.address,
            owner = alice.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(20),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(2)),
        ext = sp.none).run(sender = alice)

    current_auction_key = sp.record(fa2 = places_tokens.address, token_id = place_alice, owner = alice.address)

    balance_before = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_alice)))

    # not owner
    dutch.cancel(auction_key = current_auction_key, ext = sp.none).run(sender = bob, valid = False, exception = "NOT_OWNER")
    # valid
    dutch.cancel(auction_key = current_auction_key, ext = sp.none).run(sender = alice)
    # already cancelled, wrong state
    dutch.cancel(auction_key = current_auction_key, ext = sp.none).run(sender = alice, valid = False) # missing item in map

    balance_after = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_alice)))
    scenario.verify(balance_after == balance_before)

    #
    # bid
    #
    scenario.h3("Bid")

    current_auction_key = sp.record(fa2 = places_tokens.address, token_id = place_bob, owner = bob.address)

    # try a couple of wrong amount bids at several times
    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0), valid = False)
    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(1), valid = False)
    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(2), valid = False)
    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(20), valid = False)
    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(40), valid = False)
    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(60), valid = False)
    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(80), valid = False)
    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(81), valid = False)

    balance_before = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_bob)))

    # valid
    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.tez(22), now=sp.timestamp(0).add_minutes(80))
    # valid but wrong state
    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.tez(22), now=sp.timestamp(0).add_minutes(80), valid = False)

    balance_after = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_bob)))
    scenario.verify(balance_after == (balance_before + 1))

    #
    # test some auction edge cases
    #
    scenario.h3("create/bid edge cases")

    # alice owns bobs place now.
    # create an auction that for 2 to 1 mutez.
    # used to fail on fee/royalties transfer.
    dutch.create(
        auction_key = sp.record(
            token_id = place_alice,
            fa2 = places_tokens.address,
            owner = alice.address),
        auction = sp.record(
            start_price = sp.mutez(2),
            end_price = sp.mutez(1),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(5)),
        ext = sp.none).run(sender = alice, now=sp.timestamp(0))

    current_auction_key = sp.record(fa2 = places_tokens.address, token_id = place_alice, owner = alice.address)

    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.mutez(1), now=sp.timestamp(0).add_minutes(80))

    # create an auction that lasts 5 second.
    # duration must be > granularity
    dutch.create(
        auction_key = sp.record(
            token_id = place_alice,
            fa2 = places_tokens.address,
            owner = alice.address),
        auction = sp.record(
            start_price = sp.tez(2),
            end_price = sp.tez(1),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_seconds(5)),
        ext = sp.none).run(sender = alice, now=sp.timestamp(0), valid = False, exception = "INVALID_PARAM")

    # create an auction with end price 0.
    # duration must be > granularity
    places_tokens.update_operators([
        sp.variant("add_operator", sp.record(
            owner = alice.address,
            operator = dutch.address,
            token_id = place_alice
        ))
    ]).run(sender = alice)

    dutch.create(
        auction_key = sp.record(
            token_id = place_alice,
            fa2 = places_tokens.address,
            owner = alice.address),
        auction = sp.record(
            start_price = sp.tez(2),
            end_price = sp.tez(0),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(5)),
        ext = sp.none).run(sender = alice, now=sp.timestamp(0))

    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.mutez(0), now=sp.timestamp(0).add_minutes(80))

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

    dutch.create(
        auction_key = sp.record(
            token_id = place_bob,
            fa2 = places_tokens.address,
            owner = alice.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(20),
            start_time = auction_start_time,
            end_time = auction_start_time.add_minutes(80)),
        ext = sp.none).run(sender = alice, now=sp.timestamp(0))

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

    dutch.cancel(auction_key = current_auction_key, ext = sp.none).run(sender = alice)

    dutch.create(
        auction_key = sp.record(
            token_id = place_bob,
            fa2 = places_tokens.address,
            owner = alice.address),
        auction = sp.record(
            start_price = sp.tez(20),
            end_price = sp.tez(20),
            start_time = auction_start_time,
            end_time = auction_start_time.add_minutes(80)),
        ext = sp.none).run(sender = alice, now=sp.timestamp(0))

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
    # update world_contract
    #
    scenario.h3("update world_contract")

    # check default
    scenario.verify(dutch.data.world_contract == world.address)

    # failure cases.
    for t in [(bob, "ONLY_ADMIN"), (alice, "ONLY_ADMIN"), (admin, "NOT_CONTRACT")]:
        sender, exception = t
        dutch.update_settings([sp.variant("world_contract", bob.address)]).run(sender = sender, valid = False, exception = exception)

    dutch.update_settings([sp.variant("world_contract", minter.address)]).run(sender = admin)
    scenario.verify(dutch.data.world_contract == minter.address)
    dutch.update_settings([sp.variant("world_contract", world.address)]).run(sender = admin)
    scenario.verify(dutch.data.world_contract == world.address)

    #
    # update granularity
    #
    scenario.h3("update granularity")

    # check default
    scenario.verify(dutch.data.granularity == sp.nat(60))

    # no permission for anyone but admin
    for acc in [alice, bob, admin]:
        dutch.update_settings([sp.variant("granularity", 35)]).run(
            sender = acc,
            valid = (True if acc is admin else False),
            exception = (None if acc is admin else "ONLY_ADMIN"))

        if acc is admin: scenario.verify(dutch.data.granularity == sp.nat(35))

    scenario.table_of_contents()

    #
    # test paused
    #
    scenario.h3("pausing")
    dutch.update_settings([sp.variant("paused", True)]).run(sender = admin)

    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.mutez(20), now=sp.timestamp(0).add_minutes(80), valid = False, exception = "ONLY_UNPAUSED")

    dutch.cancel(auction_key = current_auction_key, ext = sp.none).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")

    dutch.create(
        auction_key = sp.record(
            token_id = place_bob,
            fa2 = places_tokens.address,
            owner = alice.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(20),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(80)),
        ext = sp.none).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")

    dutch.update_settings([sp.variant("paused", False)]).run(sender = admin)

    dutch.cancel(auction_key = current_auction_key, ext = sp.none).run(sender = alice)

    #
    # test secondary disabled
    #

    # disable secondary.
    dutch.update_settings([sp.variant("secondary_enabled", False)]).run(sender=bob, valid = False, exception = "ONLY_ADMIN")
    dutch.update_settings([sp.variant("secondary_enabled", False)]).run(sender=admin)
    scenario.verify(dutch.data.secondary_enabled == False)
    scenario.verify(dutch.is_secondary_enabled() == False)

    # only wl admin can create auctions if secondary is disabled
    dutch.create(
        auction_key = sp.record(
            token_id = place_bob,
            fa2 = places_tokens.address,
            owner = alice.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(20),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(80)),
        ext = sp.none).run(sender = alice, valid = False, exception = "ONLY_WHITELIST_ADMIN")

    #
    # test secondary enabled & whitelist enabled
    #

    # enabled whitelist.
    dutch.manage_whitelist(add_permitted_fa2_wl_enabled).run(sender = admin)
    scenario.verify(dutch.data.permitted_fa2.get(places_tokens.address).whitelist_enabled == True)

    # enable secondary.
    dutch.update_settings([sp.variant("secondary_enabled", True)]).run(sender=admin)
    scenario.verify(dutch.data.secondary_enabled == True)
    scenario.verify(dutch.is_secondary_enabled() == True)

    # If secondary and whitelist are enabled, anyone can create auctions,
    # and anyone can bid on them reglardless of their whitelist status.
    dutch.create(
        auction_key = sp.record(
            token_id = place_carol,
            fa2 = places_tokens.address,
            owner = carol.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(20),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(80)),
        ext = sp.none).run(sender = carol, now=sp.timestamp(0))

    current_auction_key = sp.record(fa2 = places_tokens.address, token_id = place_carol, owner = carol.address)

    # furthermore, bidding on a non-whitelist auction should not remove you from the whitelist.
    dutch.manage_whitelist([sp.variant("whitelist_add", [sp.record(fa2=places_tokens.address, user=bob.address)])]).run(sender=admin)
    scenario.verify(dutch.data.whitelist.contains(sp.record(fa2=places_tokens.address, user=bob.address)))

    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = bob, amount = sp.tez(20), now=sp.timestamp(0).add_minutes(80))

    scenario.verify(dutch.data.whitelist.contains(sp.record(fa2=places_tokens.address, user=bob.address)))

    #
    # test whitelist
    #

    # If whitelist is enabled, only whitelisted can bid on admin created auctions.
    dutch.create(
        auction_key = sp.record(
            token_id = place_admin,
            fa2 = places_tokens.address,
            owner = admin.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(20),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(80)),
        ext = sp.none).run(sender = admin, now=sp.timestamp(0))

    current_auction_key = sp.record(fa2 = places_tokens.address, token_id = place_admin, owner = admin.address)

    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.tez(20), now=sp.timestamp(0).add_minutes(80), valid = False, exception = "ONLY_WHITELISTED")

    # bidding on a whitelist auction will remove you from the whitelist.
    dutch.manage_whitelist([sp.variant("whitelist_add", [sp.record(fa2=places_tokens.address, user=alice.address)])]).run(sender=admin)
    scenario.verify(dutch.data.whitelist.contains(sp.record(fa2=places_tokens.address, user=alice.address)))

    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.tez(20), now=sp.timestamp(0).add_minutes(80))
    scenario.verify(~dutch.data.whitelist.contains(sp.record(fa2=places_tokens.address, user=alice.address)))

    # disable whitelist.
    dutch.manage_whitelist(add_permitted_fa2_wl_disabled).run(sender = admin)
    scenario.verify(dutch.data.permitted_fa2.get(places_tokens.address).whitelist_enabled == False)

    #
    # manage_whitelist
    #
    scenario.h3("manage_whitelist")

    dutch.create(
        auction_key = sp.record(
            token_id = interior_bob,
            fa2 = interiors_tokens.address,
            owner = bob.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(20),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(80)),
        ext = sp.none).run(sender = bob, now = sp.timestamp(0), valid = False, exception = "TOKEN_NOT_PERMITTED")

    add_other_permitted = sp.list([sp.variant("add_permitted",
        { interiors_tokens.address: sp.record(
                whitelist_enabled = False,
                whitelist_admin = admin.address) })])
    dutch.manage_whitelist(add_other_permitted).run(sender = admin)

    dutch.create(
        auction_key = sp.record(
            token_id = interior_bob,
            fa2 = interiors_tokens.address,
            owner = bob.address),
        auction = sp.record(
            start_price = sp.tez(100),
            end_price = sp.tez(20),
            start_time = sp.timestamp(0),
            end_time = sp.timestamp(0).add_minutes(80)),
        ext = sp.none).run(sender = bob, now = sp.timestamp(0))

    current_auction_key = sp.record(fa2 = interiors_tokens.address, token_id = interior_bob, owner = bob.address)

    dutch.bid(auction_key = current_auction_key, ext = sp.none).run(sender = alice, amount = sp.tez(20), now=sp.timestamp(0).add_minutes(80))

    # TODO: check roaylaties paid, token transferred