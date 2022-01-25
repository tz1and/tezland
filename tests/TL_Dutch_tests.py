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
        start_time = sp.now,
        end_time = sp.now.add_minutes(2),
        fa2 = places_tokens.address).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(120),
        start_time = sp.now,
        end_time = sp.now.add_minutes(2),
        fa2 = places_tokens.address).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    # incorrect start/end time
    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(120),
        start_time = sp.now.add_minutes(2),
        end_time = sp.now.add_minutes(2),
        fa2 = places_tokens.address).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.now.add_minutes(3),
        end_time = sp.now.add_minutes(2),
        fa2 = places_tokens.address).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    # Wrong owner
    dutch.create(token_id = place_alice,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.now,
        end_time = sp.now.add_minutes(80),
        fa2 = places_tokens.address).run(sender = bob, valid = False, exception = "NOT_OWNER")

    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.now,
        end_time = sp.now.add_minutes(80),
        fa2 = places_tokens.address).run(sender = alice, valid = False, exception = "NOT_OWNER")

    # token not permitted
    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.now,
        end_time = sp.now.add_minutes(80),
        fa2 = items_tokens.address).run(sender = bob, valid = False, exception = "TOKEN_NOT_PERMITTED")

    # valid
    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.now,
        end_time = sp.now.add_minutes(80),
        fa2 = places_tokens.address).run(sender = bob)

    # todo: verify token was transferred

    #
    # cancel
    #
    scenario.h3("Cancel")

    dutch.create(token_id = place_alice,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.now,
        end_time = sp.now.add_minutes(2),
        fa2 = places_tokens.address).run(sender = alice)

    # not owner
    dutch.cancel(1).run(sender = bob, valid = False, exception = "NOT_OWNER")
    # valid
    dutch.cancel(1).run(sender = alice)
    # already cancelled, wrong state
    dutch.cancel(1).run(sender = alice, valid = False) #, exception = "WRONG_STATE") # TODO: if auction is not deleted

    # todo: verify token was transferred
    # todo: test cancel from manager??

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

    # valid
    dutch.bid(0).run(sender = alice, amount = sp.tez(22), now=sp.timestamp(0).add_minutes(80), valid = True)
    # valid but wrong state
    dutch.bid(0).run(sender = alice, amount = sp.tez(22), now=sp.timestamp(0).add_minutes(80), valid = False)
    # todo: more failure cases

    #
    # todo: views
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
        start_time = sp.now,
        end_time = sp.now.add_minutes(80),
        fa2 = places_tokens.address).run(sender = alice)

    auction_info = dutch.get_auction(2)
    #scenario.verify(item_limit == sp.nat(64))
    scenario.show(auction_info)

    permitted_fa2 = dutch.get_permitted_fa2()
    scenario.verify(permitted_fa2.contains(places_tokens.address) == True)
    scenario.verify(permitted_fa2.contains(items_tokens.address) == False)
    scenario.show(auction_info)

    # NOTE: can't simulate views with timestamp... yet. .run(now=sp.timestamp(10))
    #auction_info = dutch.get_auction_price(0)
    #scenario.show(auction_info)

    #
    # set_fees
    #
    scenario.h3("set_fees")

    dutch.set_fees(35).run(sender = bob, valid = False)
    dutch.set_fees(250).run(sender = admin, valid = False)
    scenario.verify(dutch.data.fees == sp.nat(25))
    dutch.set_fees(45).run(sender = admin)
    scenario.verify(dutch.data.fees == sp.nat(45))

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
        start_time = sp.now,
        end_time = sp.now.add_minutes(80),
        fa2 = items_tokens.address).run(sender = bob, valid = False, exception = "FA2_TOKEN_UNDEFINED")
