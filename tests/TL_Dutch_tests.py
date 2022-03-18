import smartpy as sp

dutch_contract = sp.io.import_script_from_url("file:contracts/TL_Dutch.py")
minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter.py")
tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")

@sp.add_test(name = "TL_Dutch_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("Dutch auction contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

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

    place_bob = sp.nat(0)
    place_alice = sp.nat(1)

    # Test dutch auchtion

    scenario.h2("Test Dutch")

    # create places contract
    scenario.h3("Originate dutch contract")
    dutch = dutch_contract.TL_Dutch(admin.address, items_tokens.address, places_tokens.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += dutch

    # disable whitelist, it's enabled by defualt
    dutch.manage_whitelist([sp.variant("whitelist_enabled", False)]).run(sender=admin)
    scenario.verify(dutch.data.whitelist_enabled == False)

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
    # create
    #
    scenario.h3("Create")

    # incorrect start/end price
    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
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
        fa2 = items_tokens.address,
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
    scenario.verify(sp.to_int(balance_after) == (balance_before - 1))

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

    balance_before = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_alice)))

    # not owner
    dutch.cancel(auction_id = 1, extension = sp.none).run(sender = bob, valid = False, exception = "NOT_OWNER")
    # valid
    dutch.cancel(auction_id = 1, extension = sp.none).run(sender = alice)
    # already cancelled, wrong state
    dutch.cancel(auction_id = 1, extension = sp.none).run(sender = alice, valid = False) # missing item in map

    balance_after = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_alice)))
    scenario.verify(balance_after == (balance_before + 1))

    #
    # bid
    #
    scenario.h3("Bid")

    # try a couple of wrong amount bids at several times
    dutch.bid(auction_id = 0, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0), valid = False)
    dutch.bid(auction_id = 0, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(1), valid = False)
    dutch.bid(auction_id = 0, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(2), valid = False)
    dutch.bid(auction_id = 0, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(20), valid = False)
    dutch.bid(auction_id = 0, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(40), valid = False)
    dutch.bid(auction_id = 0, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(60), valid = False)
    dutch.bid(auction_id = 0, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(80), valid = False)
    dutch.bid(auction_id = 0, extension = sp.none).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(81), valid = False)

    balance_before = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_bob)))

    # valid
    dutch.bid(auction_id = 0, extension = sp.none).run(sender = alice, amount = sp.tez(22), now=sp.timestamp(0).add_minutes(80), valid = True)
    # valid but wrong state
    dutch.bid(auction_id = 0, extension = sp.none).run(sender = alice, amount = sp.tez(22), now=sp.timestamp(0).add_minutes(80), valid = False)

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

    dutch.bid(auction_id = 2, extension = sp.none).run(sender = alice, amount = sp.mutez(1), now=sp.timestamp(0).add_minutes(80), valid = True)

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

    dutch.bid(auction_id = 3, extension = sp.none).run(sender = alice, amount = sp.mutez(0), now=sp.timestamp(0).add_minutes(80), valid = True)

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
    ]).run(sender = alice, valid = True)

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = alice, now=sp.timestamp(0))

    auction_info = dutch.get_auction(4)
    #scenario.verify(item_limit == sp.nat(64))
    scenario.show(auction_info)

    # TODO: view simulation with timestamp is now possible. by setting context with scenario
    # TODO: can't simulate views with timestamp... yet. .run(now=sp.timestamp(10))
    #auction_info = dutch.get_auction_price(0)
    #scenario.show(auction_info)

    #
    # set_granularity
    #
    scenario.h3("set_granularity")
    
    dutch.set_granularity(35).run(sender = bob, valid = False)
    dutch.set_granularity(250).run(sender = alice, valid = False)
    scenario.verify(dutch.data.granularity == sp.nat(60))
    dutch.set_granularity(45).run(sender = admin)
    scenario.verify(dutch.data.granularity == sp.nat(45))

    scenario.table_of_contents()

    #
    # test paused
    #
    scenario.h3("pausing")
    scenario.verify(dutch.data.paused == False)
    dutch.set_paused(True).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    dutch.set_paused(True).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    dutch.set_paused(True).run(sender = admin)
    scenario.verify(dutch.data.paused == True)

    dutch.bid(auction_id = 4, extension = sp.none).run(sender = alice, amount = sp.mutez(20), now=sp.timestamp(0).add_minutes(80), valid = False, exception = "ONLY_UNPAUSED")

    dutch.cancel(auction_id = 4, extension = sp.none).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")

    dutch.set_paused(False).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    dutch.set_paused(False).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    dutch.set_paused(False).run(sender = admin)
    scenario.verify(dutch.data.paused == False)

    dutch.cancel(auction_id = 4, extension = sp.none).run(sender = alice)

    #
    # test whitelist
    #
    dutch.manage_whitelist([sp.variant("whitelist_enabled", True)]).run(sender=admin)
    scenario.verify(dutch.data.whitelist_enabled == True)

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = alice, valid = False, exception = "ONLY_ADMIN")

    minter.mint_Place([sp.record(
        to_ = admin.address,
        metadata = {'': sp.utils.bytes_of_string("test_metadata")}
    )]).run(sender = admin)
    place_admin = sp.nat(2)

    places_tokens.update_operators([
        sp.variant("add_operator", sp.record(
            owner = admin.address,
            operator = dutch.address,
            token_id = place_admin
        ))
    ]).run(sender = admin, valid = True)

    dutch.create(token_id = place_admin,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address,
        extension = sp.none).run(sender = admin, valid = True)

    dutch.bid(auction_id = abs(dutch.data.auction_id - 1), extension = sp.none).run(sender = alice, amount = sp.tez(20), now=sp.timestamp(0).add_minutes(80), valid = False, exception = "ONLY_WHITELISTED")

    dutch.manage_whitelist([sp.variant("whitelist_add", [alice.address])]).run(sender=admin)
    scenario.verify(dutch.data.whitelist.contains(alice.address))

    dutch.bid(auction_id = abs(dutch.data.auction_id - 1), extension = sp.none).run(sender = alice, amount = sp.tez(20), now=sp.timestamp(0).add_minutes(80), valid = True)
    scenario.verify(~dutch.data.whitelist.contains(alice.address))

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
        fa2 = items_tokens.address,
        extension = sp.none).run(sender = bob, now = sp.timestamp(0), valid = False, exception = "TOKEN_NOT_PERMITTED")

    add_permitted = sp.list([sp.variant("add_permitted",
        sp.record(
            fa2 = items_tokens.address,
            props = sp.record(
                swap_allowed = True,
                royalties_kind = sp.variant("tz1and", sp.unit))))])

    dutch.set_fa2_permitted(add_permitted).run(sender = admin)

    dutch.create(token_id = item_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = items_tokens.address,
        extension = sp.none).run(sender = bob, now = sp.timestamp(0))

    dutch.bid(auction_id = abs(dutch.data.auction_id - 1), extension = sp.none).run(sender = alice, amount = sp.tez(20), now=sp.timestamp(0).add_minutes(80))

    # TODO: check roaylaties paid, token transferred