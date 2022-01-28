import smartpy as sp

minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter.py")
places_contract = sp.io.import_script_from_url("file:contracts/TL_World.py")
fa2_contract = sp.io.import_script_from_url("file:contracts/FA2.py")

@sp.add_test(name = "TL_World_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("Places Contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

    # create a FA2 and minter contract for testing
    scenario.h2("Create test env")
    scenario.h3("items")
    items_tokens = fa2_contract.FA2(config = fa2_contract.items_config(),
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    scenario.h3("places")
    places_tokens = fa2_contract.FA2(config = fa2_contract.places_config(),
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += places_tokens

    scenario.h3("minter")
    minter = minter_contract.TL_Minter(admin.address, items_tokens.address, places_tokens.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    scenario.h3("dao")
    dao_token = fa2_contract.FA2(config = fa2_contract.dao_config(),
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += dao_token

    scenario.h3("preparation")
    items_tokens.set_administrator(minter.address).run(sender = admin)
    places_tokens.set_administrator(minter.address).run(sender = admin)

    # mint some item tokens for testing
    minter.mint_Item(address = bob.address,
        amount = 4,
        royalties = 250,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    minter.mint_Item(address = alice.address,
        amount = 25,
        royalties = 250,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)

    # mint some place tokens for testing
    minter.mint_Place(address = bob.address,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = admin)

    minter.mint_Place(address = alice.address,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = admin)

    place_bob = sp.nat(0)
    place_alice = sp.nat(1)

    dao_token.mint(address = admin.address,
        amount = 0,
        metadata = fa2_contract.FA2.make_metadata(name = "tz1aND DAO",
            decimals = 6,
            symbol= "tz1aDAO"),
        token_id = 0).run(sender = admin)

    # Test places

    scenario.h2("Test Places")

    # create places contract
    scenario.h3("Originate places contract")
    places = places_contract.TL_World(admin.address, items_tokens.address, places_tokens.address, minter.address, dao_token.address,
        sp.now.add_days(60), metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += places

    dao_token.set_administrator(places.address).run(sender = admin)

    # set operators
    scenario.h3("Add operators")
    items_tokens.update_operators([
        sp.variant("add_operator", items_tokens.operator_param.make(
            owner = bob.address,
            operator = places.address,
            token_id = 0
        ))
    ]).run(sender = bob, valid = True)

    items_tokens.update_operators([
        sp.variant("add_operator", items_tokens.operator_param.make(
            owner = alice.address,
            operator = places.address,
            token_id = 1
        ))
    ]).run(sender = alice, valid = True)

    position = sp.bytes("0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")

    # place some items not owned
    scenario.h3("Placing items")
    places.place_items(lot_id = place_bob, owner=sp.none, item_list = [sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position))]).run(sender = bob, valid = False)
    places.place_items(lot_id = place_bob, owner=sp.none, item_list = [sp.variant("item", sp.record(token_amount = 500, token_id = 0, xtz_per_token = sp.tez(1), item_data = position))]).run(sender = bob, valid = False)

    # place some items in a lot not owned
    places.place_items(lot_id = place_alice, owner=sp.some(alice.address), item_list = [
        sp.variant("item", sp.record(token_amount = 1, token_id = 0, xtz_per_token = sp.tez(1), item_data = position))
    ]).run(sender = bob, valid = False, exception = "NOT_OPERATOR")
    places.place_items(lot_id = place_bob, owner=sp.some(bob.address), item_list = [
        sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position))
    ]).run(sender = alice, valid = False, exception = "NOT_OPERATOR")

    # place some items
    places.place_items(lot_id = place_bob, owner=sp.none, item_list = [sp.variant("item", sp.record(token_amount = 1, token_id = 0, xtz_per_token = sp.tez(1), item_data = position))]).run(sender = bob)
    places.place_items(lot_id = place_bob, owner=sp.none, item_list = [sp.variant("item", sp.record(token_amount = 2, token_id = 0, xtz_per_token = sp.tez(1), item_data = position))]).run(sender = bob)

    places.place_items(lot_id = place_alice, owner=sp.none, item_list = [sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position))]).run(sender = alice)
    places.place_items(lot_id = place_alice, owner=sp.none, item_list = [sp.variant("item", sp.record(token_amount = 2, token_id = 1, xtz_per_token = sp.tez(1), item_data = position))]).run(sender = alice)

    # get (buy) items.
    scenario.h3("Gettting items")

    # make sure sequence number changes on interaction. need to use compute here to eval immediate.
    check_before_sequence_number = scenario.compute(places.get_place_seqnum(place_bob))
    places.get_item(lot_id = place_bob, item_id = 1).run(sender = alice, amount = sp.tez(1))
    scenario.verify(check_before_sequence_number != places.get_place_seqnum(place_bob))

    places.get_item(lot_id = place_bob, item_id = 1).run(sender = alice, amount = sp.tez(1))
    places.get_item(lot_id = place_bob, item_id = 1).run(sender = alice, amount = sp.tez(1), valid = False)
    places.get_item(lot_id = place_alice, item_id = 1).run(sender = bob, amount = sp.tez(1))
    places.get_item(lot_id = place_alice, item_id = 1).run(sender = bob, amount = sp.tez(1))
    places.get_item(lot_id = place_alice, item_id = 1).run(sender = bob, amount = sp.tez(1), valid = False)

    # remove items in a lot not owned
    scenario.h3("Removing items")
    places.remove_items(lot_id = place_bob, owner=sp.none, item_list = [0]).run(sender = alice, valid = False)
    places.remove_items(lot_id = place_alice, owner=sp.none, item_list = [0]).run(sender = bob, valid = False)

    # remove items
    places.remove_items(lot_id = place_bob, owner=sp.none, item_list = [0]).run(sender = bob)
    places.remove_items(lot_id = place_alice, owner=sp.none, item_list = [0]).run(sender = alice)

    #place multiple items
    places.place_items(lot_id = place_alice, owner=sp.none, item_list = [
        sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position))
    ]).run(sender = alice)

    #place items with invalid data
    places.place_items(lot_id = place_alice, owner=sp.none, item_list = [
        sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = sp.bytes('0xFFFFFFFF'))),
    ]).run(sender = alice, valid = False, exception = "DATA_LEN")

    # test ext items
    scenario.h3("Ext items")

    # place an ext item
    scenario.h4("Place ext items")
    places.place_items(lot_id = place_bob, owner=sp.none, item_list = [
        sp.variant("ext", sp.utils.bytes_of_string("test_string data1")),
        sp.variant("ext", sp.utils.bytes_of_string("test_string data2")),
        sp.variant("item", sp.record(token_amount = 1, token_id = 0, xtz_per_token = sp.tez(1), item_data = position))
    ]).run(sender = bob)

    scenario.h4("Remvove ext items")
    places.remove_items(lot_id = place_bob, owner=sp.none, item_list = [2]).run(sender = bob)
    places.remove_items(lot_id = place_bob, owner=sp.none, item_list = [3, 4]).run(sender = bob)

    scenario.h3("Set place props")
    places.set_place_props(lot_id = place_bob, owner=sp.none, props = sp.bytes('0xFFFFFF')).run(sender = bob)
    scenario.verify(places.data.places[place_bob].place_props == sp.bytes('0xFFFFFF'))
    places.set_place_props(lot_id = place_bob, owner=sp.none, props = sp.bytes('0xFFFFFFFFFF')).run(sender = bob)
    places.set_place_props(lot_id = place_bob, owner=sp.none, props = sp.bytes('0xFFFF')).run(sender = bob, valid = False, exception = "DATA_LEN")
    places.set_place_props(lot_id = place_bob, owner=sp.some(bob.address), props = sp.bytes('0xFFFFFFFFFF')).run(sender = alice, valid = False, exception = "NOT_OPERATOR")

    # test views
    scenario.h3("Views")
    scenario.p("It's views")

    scenario.h4("Item limit")
    item_limit = places.get_item_limit()
    scenario.verify(item_limit == sp.nat(32))
    scenario.show(item_limit)

    scenario.h4("Stored items")
    stored_items = places.get_stored_items(place_alice)
    scenario.verify(stored_items.place_props == sp.bytes('0x82b881'))
    scenario.verify(stored_items.stored_items[2].open_variant("item").item_amount == 1)
    scenario.verify(stored_items.stored_items[3].open_variant("item").item_amount == 1)
    scenario.verify(stored_items.stored_items[4].open_variant("item").item_amount == 1)
    scenario.show(stored_items)

    stored_items_empty = places.get_stored_items(sp.nat(5))
    scenario.verify(sp.len(stored_items_empty.stored_items) == 0)
    scenario.show(stored_items_empty)

    scenario.h4("Sequence numbers")
    sequence_number = scenario.compute(places.get_place_seqnum(place_alice))
    scenario.verify(sequence_number == sp.sha3(sp.pack(sp.pair(sp.nat(3), sp.nat(5)))))
    scenario.show(sequence_number)

    sequence_number_empty = scenario.compute(places.get_place_seqnum(sp.nat(5)))
    scenario.verify(sequence_number_empty == sp.sha3(sp.pack(sp.pair(sp.nat(0), sp.nat(0)))))
    scenario.show(sequence_number_empty)

    # set item limit
    scenario.h3("Item Limit")

    scenario.h4("set_item_limit")
    scenario.verify(places.data.item_limit == 32)
    places.set_item_limit(128).run(sender = bob, valid = False)
    places.set_item_limit(128).run(sender = admin)
    scenario.verify(places.data.item_limit == 128)

    scenario.h4("item limit on place_items")
    places.set_item_limit(10).run(sender = admin)
    places.place_items(lot_id = place_alice, owner=sp.none, item_list = [
        sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)),
    ]).run(sender = alice, valid = False, exception = 'ITEM_LIMIT')

    # set fees
    scenario.h3("Fees")
    places.set_fees(35).run(sender = bob, valid = False)
    places.set_fees(250).run(sender = admin, valid = False)
    places.set_fees(45).run(sender = admin)


    scenario.table_of_contents()