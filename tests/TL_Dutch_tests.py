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

    minter = minter_contract.TL_Minter(admin.address, items_tokens.address, places_tokens.address)
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
    dutch = dutch_contract.TL_Dutch(admin.address, items_tokens.address, places_tokens.address, minter.address)
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

    # create auction
    scenario.h3("Create auction")
    dutch.create(token_id = place_bob,
        start_price = sp.tez(100),
        end_price = sp.tez(20),
        start_time = sp.now,
        end_time = sp.now.add_minutes(2)).run(sender = bob)

    # temp: views
    auction_info = dutch.get_auction(0)
    #scenario.verify(item_limit == sp.nat(64))
    scenario.show(auction_info)

    # NOTE: can't simulate views with timestamp... yet. .run(now=sp.timestamp(10))
    #auction_info = dutch.get_auction_price(0)
    #scenario.show(auction_info)

    # todo: failure cases

    # bid
    dutch.bid(0).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(0), valid = False)
    dutch.bid(0).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(1), valid = False)
    dutch.bid(0).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(60), valid = False)
    dutch.bid(0).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(80), valid = False)
    dutch.bid(0).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(119), valid = False)
    dutch.bid(0).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(120), valid = False)
    dutch.bid(0).run(sender = alice, amount = sp.tez(1), now=sp.timestamp(121), valid = False)
    # todo: more failure cases
    dutch.bid(0).run(sender = alice, amount = sp.tez(3), now=sp.timestamp(122), valid = False)
    dutch.bid(0).run(sender = alice, amount = sp.tez(22), now=sp.timestamp(122), valid = True)
    dutch.bid(0).run(sender = alice, amount = sp.tez(22), now=sp.timestamp(122), valid = False)

    # set fees
    scenario.h3("Fees")
    dutch.set_fees(35).run(sender = bob, valid = False)
    dutch.set_fees(250).run(sender = admin, valid = False)
    dutch.set_fees(45).run(sender = admin)


    scenario.table_of_contents()