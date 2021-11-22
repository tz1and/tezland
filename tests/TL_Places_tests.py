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
    items_tokens = fa2_contract.FA2(config = fa2_contract.environment_config(),
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    minter = minter_contract.TL_Minter(admin.address, items_tokens.address)
    scenario += minter

    items_tokens.set_administrator(minter.address).run(sender = admin)

    # mint some items_tokens for testing
    minter.mint_Item(address = bob.address,
        amount = 4,
        royalties = 250,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    minter.mint_Item(address = alice.address,
        amount = 25,
        royalties = 250,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)

    # Test places

    scenario.h2("Test Places")

    # create places contract
    scenario.h3("Originate places contract")
    places = places_contract.TL_Places(admin.address, items_tokens.address, minter.address)
    scenario += places

    place1 = sp.utils.bytes_of_string("shouldbeahash1")
    place2 = sp.utils.bytes_of_string("shouldbeahash2")

    # create a new (market)place
    scenario.h3("Create places")
    scenario += places.new_place(place1).run(sender = bob)
    scenario += places.new_place(place1).run(sender = bob, valid = False)
    scenario += places.new_place(place2).run(sender = alice)
    scenario += places.new_place(place2).run(sender = alice, valid = False)

    scenario += items_tokens.update_operators([
        sp.variant("add_operator", items_tokens.operator_param.make(
            owner = bob.address,
            operator = places.address,
            token_id = 0
        ))
    ]).run(sender = bob, valid = True)

    scenario += items_tokens.update_operators([
        sp.variant("add_operator", items_tokens.operator_param.make(
            owner = alice.address,
            operator = places.address,
            token_id = 1
        ))
    ]).run(sender = alice, valid = True)

    position = sp.bytes("0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")

    # place some items not owned
    scenario.h3("Placing items")
    scenario += places.place_item(lot_id = place1, token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position).run(sender = bob, valid = False)
    scenario += places.place_item(lot_id = place1, token_amount = 500, token_id = 0, xtz_per_token = sp.tez(1), item_data = position).run(sender = bob, valid = False)

    # place some items in a lot not owned
    scenario += places.place_item(lot_id = place2, token_amount = 1, token_id = 0, xtz_per_token = sp.tez(1), item_data = position).run(sender = bob, valid = False)
    scenario += places.place_item(lot_id = place1, token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position).run(sender = alice, valid = False)

    # place some items
    scenario += places.place_item(lot_id = place1, token_amount = 1, token_id = 0, xtz_per_token = sp.tez(1), item_data = position).run(sender = bob)
    scenario += places.place_item(lot_id = place1, token_amount = 2, token_id = 0, xtz_per_token = sp.tez(1), item_data = position).run(sender = bob)

    scenario += places.place_item(lot_id = place2, token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position).run(sender = alice)
    scenario += places.place_item(lot_id = place2, token_amount = 2, token_id = 1, xtz_per_token = sp.tez(1), item_data = position).run(sender = alice)

    # get (buy) items.
    scenario.h3("Gettting items")
    scenario += places.get_item(lot_id = place1, item_id = 1).run(sender = alice, amount = sp.tez(1))
    scenario += places.get_item(lot_id = place1, item_id = 1).run(sender = alice, amount = sp.tez(1))
    scenario += places.get_item(lot_id = place1, item_id = 1).run(sender = alice, amount = sp.tez(1), valid = False)
    scenario += places.get_item(lot_id = place2, item_id = 1).run(sender = bob, amount = sp.tez(1))
    scenario += places.get_item(lot_id = place2, item_id = 1).run(sender = bob, amount = sp.tez(1))
    scenario += places.get_item(lot_id = place2, item_id = 1).run(sender = bob, amount = sp.tez(1), valid = False)

    # remove items in a lot not owned
    scenario.h3("Removing items")
    scenario += places.remove_item(lot_id = place1, item_id = 0).run(sender = alice, valid = False)
    scenario += places.remove_item(lot_id = place2, item_id = 0).run(sender = bob, valid = False)

    # remove items
    scenario += places.remove_item(lot_id = place1, item_id = 0).run(sender = bob)
    scenario += places.remove_item(lot_id = place2, item_id = 0).run(sender = alice)

    #place item list
    scenario += places.place_items(lot_id = place2, item_list = [
        sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position),
        sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position),
        sp.record(token_amount = 1, token_id = 1, xtz_per_token = sp.tez(1), item_data = position)
        ]).run(sender = alice)

    # TODO: test remove_items

    # set fees
    scenario.h3("Fees")
    scenario += places.set_fees(35).run(sender = bob, valid = False)
    scenario += places.set_fees(250).run(sender = admin, valid = False)
    scenario += places.set_fees(45).run(sender = admin)


    scenario.table_of_contents()