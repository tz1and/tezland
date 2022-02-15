import smartpy as sp

dutch_contract = sp.io.import_script_from_url("file:contracts/TL_Dutch.py")
minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter.py")
fa2_contract = sp.io.import_script_from_url("file:contracts/FA2.py")

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
    items_tokens = fa2_contract.FA2(config = fa2_contract.items_config(),
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    places_tokens = fa2_contract.FA2(config = fa2_contract.places_config(),
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += places_tokens

    minter = minter_contract.TL_Minter(admin.address, items_tokens.address, places_tokens.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    items_tokens.set_administrator(minter.address).run(sender = admin)
    places_tokens.set_administrator(minter.address).run(sender = admin)

    # mint some item tokens for testing
    #minter.mint_Item(address = bob.address,
    #    amount = 4,
    #    royalties = 250,
    #    metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    #minter.mint_Item(address = alice.address,
    #    amount = 25,
    #    royalties = 250,
    #    metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)

    # mint some place tokens for testing
    minter.mint_Place(address = bob.address,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = admin)

    minter.mint_Place(address = alice.address,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = admin)

    place_bob = sp.nat(0)
    place_alice = sp.nat(1)

    # Test dutch auchtion

    scenario.h2("Test Dutch")

    # create places contract
    scenario.h3("Originate dutch contract")
    dutch = dutch_contract.TL_Dutch(admin.address, items_tokens.address, places_tokens.address, minter.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += dutch

    # disable whitelist, it's enabled by defualt
    dutch.manage_whitelist(sp.variant("whitelist_enabled", False)).run(sender=admin)
    scenario.verify(dutch.data.whitelist_enabled == False)

    # set operators
    scenario.h3("Add operators")
    places_tokens.update_operators([
        sp.variant("add_operator", places_tokens.operator_param.make(
            owner = bob.address,
            operator = dutch.address,
            token_id = place_bob
        ))
    ]).run(sender = bob, valid = True)

    places_tokens.update_operators([
        sp.variant("add_operator", places_tokens.operator_param.make(
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
        fa2 = places_tokens.address).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(120),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(2),
        fa2 = places_tokens.address).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    # incorrect start/end time
    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(120),
        start_time = sp.timestamp(0).add_minutes(2),
        end_time = sp.timestamp(0).add_minutes(2),
        fa2 = places_tokens.address).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0).add_minutes(3),
        end_time = sp.timestamp(0).add_minutes(2),
        fa2 = places_tokens.address).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    # Wrong owner
    dutch.create(token_id = place_alice,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address).run(sender = bob, valid = False, exception = "NOT_OWNER")

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address).run(sender = alice, valid = False, exception = "NOT_OWNER")

    # token not permitted
    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = items_tokens.address).run(sender = bob, valid = False, exception = "TOKEN_NOT_PERMITTED")

    balance_before = scenario.compute(places_tokens.get_balance(sp.record(owner = bob.address, token_id = place_bob)))

    # valid
    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address).run(sender = bob)

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
        fa2 = places_tokens.address).run(sender = alice)

    balance_before = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_alice)))

    # not owner
    dutch.cancel(1).run(sender = bob, valid = False, exception = "NOT_OWNER")
    # valid
    dutch.cancel(1).run(sender = alice)
    # already cancelled, wrong state
    dutch.cancel(1).run(sender = alice, valid = False) # missing item in map

    balance_after = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_alice)))
    scenario.verify(balance_after == (balance_before + 1))

    #
    # bid
    #
    scenario.h3("Bid")

    # try a couple of wrong amount bids at several times
    dutch.bid(0).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0), valid = False)
    dutch.bid(0).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(1), valid = False)
    dutch.bid(0).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(2), valid = False)
    dutch.bid(0).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(20), valid = False)
    dutch.bid(0).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(40), valid = False)
    dutch.bid(0).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(60), valid = False)
    dutch.bid(0).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(80), valid = False)
    dutch.bid(0).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0).add_minutes(81), valid = False)

    balance_before = scenario.compute(places_tokens.get_balance(sp.record(owner = alice.address, token_id = place_bob)))

    # valid
    dutch.bid(0).run(sender = alice, amount = sp.tez(22), now=sp.timestamp(0).add_minutes(80), valid = True)
    # valid but wrong state
    dutch.bid(0).run(sender = alice, amount = sp.tez(22), now=sp.timestamp(0).add_minutes(80), valid = False)

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
        fa2 = places_tokens.address).run(sender = alice, now=sp.timestamp(0))

    dutch.bid(2).run(sender = alice, amount = sp.mutez(1), now=sp.timestamp(0).add_minutes(80), valid = True)

    # create an auction that lasts 5 second.
    # duration must be > granularity
    dutch.create(token_id = place_alice,
        start_price = sp.tez(2),
        end_price = sp.tez(1),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_seconds(5),
        fa2 = places_tokens.address).run(sender = alice, now=sp.timestamp(0), valid = False, exception = "INVALID_PARAM")

    # create an auction with end price 0.
    # duration must be > granularity
    dutch.create(token_id = place_alice,
        start_price = sp.tez(2),
        end_price = sp.tez(0),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(5),
        fa2 = places_tokens.address).run(sender = alice, now=sp.timestamp(0))

    dutch.bid(3).run(sender = alice, amount = sp.mutez(0), now=sp.timestamp(0).add_minutes(80), valid = True)

    # TODO: more failure cases?

    #
    # views
    #
    scenario.h3("Views")

    # alice should own bobs token now
    # set operators and create a new auction
    places_tokens.update_operators([
        sp.variant("add_operator", places_tokens.operator_param.make(
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
        fa2 = places_tokens.address).run(sender = alice, now=sp.timestamp(0))

    auction_info = dutch.get_auction(4)
    #scenario.verify(item_limit == sp.nat(64))
    scenario.show(auction_info)

    scenario.verify(dutch.is_fa2_permitted(places_tokens.address) == True)
    scenario.verify(dutch.is_fa2_permitted(items_tokens.address) == False)

    # TODO: view simulation with timestamp is now possible. by setting context with scenario
    # TODO: can't simulate views with timestamp... yet. .run(now=sp.timestamp(10))
    #auction_info = dutch.get_auction_price(0)
    #scenario.show(auction_info)

    #
    # set_fees
    #
    scenario.h3("set_fees")

    dutch.set_fees(sp.variant("update_fees", 35)).run(sender = bob, valid = False)
    dutch.set_fees(sp.variant("update_fees", 250)).run(sender = admin, valid = False)
    scenario.verify(dutch.data.fees == sp.nat(25))
    dutch.set_fees(sp.variant("update_fees", 45)).run(sender = admin)
    scenario.verify(dutch.data.fees == sp.nat(45))

    dutch.set_fees(sp.variant("update_fees_to", bob.address)).run(sender = bob, valid = False)
    scenario.verify(dutch.data.fees_to == admin.address)
    dutch.set_fees(sp.variant("update_fees_to", bob.address)).run(sender = admin)
    scenario.verify(dutch.data.fees_to == bob.address)

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
    # set_permitted_fa2
    #
    scenario.h3("set_permitted_fa2")
    dutch.set_permitted_fa2(fa2 = items_tokens.address, permitted = True).run(sender = bob, valid = False, exception = "ONLY_MANAGER")
    scenario.verify(dutch.data.permitted_fa2.contains(items_tokens.address) == False)

    dutch.set_permitted_fa2(fa2 = items_tokens.address, permitted = True).run(sender = admin)
    scenario.verify(dutch.data.permitted_fa2.contains(items_tokens.address) == True)

    dutch.set_permitted_fa2(fa2 = places_tokens.address, permitted = False).run(sender = admin)
    scenario.verify(dutch.data.permitted_fa2.contains(places_tokens.address) == False)

    # Fails, but passes the TOKEN_NOT_PERMITTED test.
    dutch.create(token_id = 0,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = items_tokens.address).run(sender = bob, valid = False, exception = "FA2_TOKEN_UNDEFINED")

    #
    # test paused
    #
    scenario.h3("pausing")
    scenario.verify(dutch.data.paused == False)
    dutch.set_paused(True).run(sender = bob, valid = False, exception = "ONLY_MANAGER")
    dutch.set_paused(True).run(sender = alice, valid = False, exception = "ONLY_MANAGER")
    dutch.set_paused(True).run(sender = admin)
    scenario.verify(dutch.data.paused == True)

    dutch.bid(4).run(sender = alice, amount = sp.mutez(20), now=sp.timestamp(0).add_minutes(80), valid = False, exception = "ONLY_UNPAUSED")

    dutch.cancel(4).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")

    dutch.set_paused(False).run(sender = bob, valid = False, exception = "ONLY_MANAGER")
    dutch.set_paused(False).run(sender = alice, valid = False, exception = "ONLY_MANAGER")
    dutch.set_paused(False).run(sender = admin)
    scenario.verify(dutch.data.paused == False)

    dutch.cancel(4).run(sender = alice)

    #
    # test whitelist
    #
    dutch.manage_whitelist(sp.variant("whitelist_enabled", True)).run(sender=admin)
    scenario.verify(dutch.data.whitelist_enabled == True)
    dutch.set_permitted_fa2(fa2 = places_tokens.address, permitted = True).run(sender = admin)

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.timestamp(0),
        end_time = sp.timestamp(0).add_minutes(80),
        fa2 = places_tokens.address).run(sender = alice, valid = False, exception = "ONLY_MANAGER")

    minter.mint_Place(address = admin.address,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = admin)
    place_admin = sp.nat(2)

    places_tokens.update_operators([
        sp.variant("add_operator", places_tokens.operator_param.make(
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
        fa2 = places_tokens.address).run(sender = admin, valid = True)

    dutch.bid(abs(dutch.data.auction_id - 1)).run(sender = alice, amount = sp.tez(20), now=sp.timestamp(0).add_minutes(80), valid = False, exception = "ONLY_WHITELISTED")

    dutch.manage_whitelist(sp.variant("whitelist_add", [alice.address])).run(sender=admin)
    scenario.verify(dutch.data.whitelist.contains(alice.address))

    dutch.bid(abs(dutch.data.auction_id - 1)).run(sender = alice, amount = sp.tez(20), now=sp.timestamp(0).add_minutes(80), valid = True)
    scenario.verify(~dutch.data.whitelist.contains(alice.address))
