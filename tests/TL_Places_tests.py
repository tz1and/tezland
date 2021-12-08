import smartpy as sp

minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter.py")
places_contract = sp.io.import_script_from_url("file:contracts/TL_Places.py")
fa2_contract = sp.io.import_script_from_url("file:contracts/FA2.py")

@sp.add_test(name = "TL_Places_tests", profile = True)
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

    # Test places

    scenario.h2("Test Places")

    # create places contract
    scenario.h3("Originate places contract")
    places = places_contract.TL_Places(admin.address, items_tokens.address, places_tokens.address, minter.address)
    scenario += places

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
    places.place_items(lot_id = place_bob, item_list = [sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)]).run(sender = bob, valid = False)
    places.place_items(lot_id = place_bob, item_list = [sp.record(token_amount = 500, token_id = 0, xtz_per_token = sp.tez(1), item_data = position)]).run(sender = bob, valid = False)

    # place some items in a lot not owned
    places.place_items(lot_id = place_alice, item_list = [sp.record(token_amount = 1, token_id = 0, xtz_per_token = sp.tez(1), item_data = position)]).run(sender = bob, valid = False)
    places.place_items(lot_id = place_bob, item_list = [sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)]).run(sender = alice, valid = False)

    # place some items
    places.place_items(lot_id = place_bob, item_list = [sp.record(token_amount = 1, token_id = 0, xtz_per_token = sp.tez(1), item_data = position)]).run(sender = bob)
    places.place_items(lot_id = place_bob, item_list = [sp.record(token_amount = 2, token_id = 0, xtz_per_token = sp.tez(1), item_data = position)]).run(sender = bob)

    places.place_items(lot_id = place_alice, item_list = [sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)]).run(sender = alice)
    places.place_items(lot_id = place_alice, item_list = [sp.record(token_amount = 2, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)]).run(sender = alice)

    # get (buy) items.
    scenario.h3("Gettting items")
    places.get_item(lot_id = place_bob, item_id = 1).run(sender = alice, amount = sp.tez(1))
    places.get_item(lot_id = place_bob, item_id = 1).run(sender = alice, amount = sp.tez(1))
    places.get_item(lot_id = place_bob, item_id = 1).run(sender = alice, amount = sp.tez(1), valid = False)
    places.get_item(lot_id = place_alice, item_id = 1).run(sender = bob, amount = sp.tez(1))
    places.get_item(lot_id = place_alice, item_id = 1).run(sender = bob, amount = sp.tez(1))
    places.get_item(lot_id = place_alice, item_id = 1).run(sender = bob, amount = sp.tez(1), valid = False)

    # remove items in a lot not owned
    scenario.h3("Removing items")
    places.remove_items(lot_id = place_bob, item_list = [0]).run(sender = alice, valid = False)
    places.remove_items(lot_id = place_alice, item_list = [0]).run(sender = bob, valid = False)

    # remove items
    places.remove_items(lot_id = place_bob, item_list = [0]).run(sender = bob)
    places.remove_items(lot_id = place_alice, item_list = [0]).run(sender = alice)

    #place multiple items
    places.place_items(lot_id = place_alice, item_list = [
        sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position),
        sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position),
        sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)
        ]).run(sender = alice)

    # test views
    scenario.h3("Views")
    scenario.p("It's views")

    scenario.h4("Item limit")
    item_limit = places.get_item_limit()
    scenario.verify(item_limit == sp.nat(64))
    scenario.show(item_limit)

    scenario.h4("Stored items")
    stored_items = places.get_stored_items(place_alice)
    scenario.verify(stored_items[2].item_amount == 1)
    scenario.verify(stored_items[3].item_amount == 1)
    scenario.verify(stored_items[4].item_amount == 1)
    scenario.show(stored_items)

    stored_items_empty = places.get_stored_items(sp.nat(5))
    scenario.verify(sp.len(stored_items_empty) == 0)
    scenario.show(stored_items_empty)

    scenario.h4("Sequence numbers")
    sequence_number = places.get_place_seqnum(place_alice)
    scenario.verify(sequence_number == sp.sha3(sp.pack(sp.pair(sp.nat(3), sp.nat(5)))))
    scenario.show(sequence_number)

    sequence_number_empty = places.get_place_seqnum(sp.nat(5))
    scenario.verify(sequence_number_empty == sp.sha3(sp.pack(sp.pair(sp.nat(0), sp.nat(0)))))
    scenario.show(sequence_number_empty)

    # set item limit
    scenario.h3("Item Limit")

    scenario.verify(places.data.item_limit == 64)
    places.set_item_limit(128).run(sender = bob, valid = False)
    places.set_item_limit(128).run(sender = admin)
    scenario.verify(places.data.item_limit == 128)

    # todo: test item limit on add!!!!

    # set fees
    scenario.h3("Fees")
    places.set_fees(35).run(sender = bob, valid = False)
    places.set_fees(250).run(sender = admin, valid = False)
    places.set_fees(45).run(sender = admin)


    scenario.table_of_contents()