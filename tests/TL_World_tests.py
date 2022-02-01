import smartpy as sp

minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter.py")
places_contract = sp.io.import_script_from_url("file:contracts/TL_World.py")
fa2_contract = sp.io.import_script_from_url("file:contracts/FA2.py")

@sp.add_test(name = "TL_World_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    carol = sp.test_account("Carol")
    scenario = sp.test_scenario()

    scenario.h1("World Tests")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h1("Accounts")
    scenario.show([admin, alice, bob, carol])

    #
    # create all kinds of contracts for testing
    #
    scenario.h1("Create test env")
    scenario.h2("items")
    items_tokens = fa2_contract.FA2(config = fa2_contract.items_config(),
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    scenario.h2("places")
    places_tokens = fa2_contract.FA2(config = fa2_contract.places_config(),
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += places_tokens

    scenario.h2("minter")
    minter = minter_contract.TL_Minter(admin.address, items_tokens.address, places_tokens.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    scenario.h2("dao")
    dao_token = fa2_contract.FA2(config = fa2_contract.dao_config(),
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += dao_token

    scenario.h2("some other FA2 token")
    other_token = fa2_contract.FA2(config = fa2_contract.items_config(),
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += other_token

    scenario.h2("preparation")
    items_tokens.set_administrator(minter.address).run(sender = admin)
    places_tokens.set_administrator(minter.address).run(sender = admin)

    # mint some item tokens for testing
    scenario.h3("minting items")
    minter.mint_Item(address = bob.address,
        amount = 4,
        royalties = 250,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    minter.mint_Item(address = alice.address,
        amount = 25,
        royalties = 250,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)

    item_bob = sp.nat(0)
    item_alice = sp.nat(1)

    # mint some place tokens for testing
    scenario.h3("minting places")
    minter.mint_Place(address = bob.address,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = admin)

    minter.mint_Place(address = alice.address,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = admin)

    place_bob = sp.nat(0)
    place_alice = sp.nat(1)

    scenario.h3("minting 0 dao")
    dao_token.mint(address = admin.address,
        amount = 0,
        metadata = fa2_contract.FA2.make_metadata(name = "tz1aND DAO",
            decimals = 6,
            symbol= "tz1aDAO"),
        token_id = 0).run(sender = admin)

    #
    # Test places
    #
    scenario.h1("Test World")

    #
    # create World contract
    #
    scenario.h2("Originate World contract")
    world = places_contract.TL_World(admin.address, items_tokens.address, places_tokens.address, minter.address, dao_token.address,
        sp.now.add_days(60), metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += world

    dao_token.set_administrator(world.address).run(sender = admin)

    #
    # set operators
    #
    scenario.h2("Add world as operator for items")
    items_tokens.update_operators([
        sp.variant("add_operator", items_tokens.operator_param.make(
            owner = bob.address,
            operator = world.address,
            token_id = item_bob
        ))
    ]).run(sender = bob, valid = True)

    items_tokens.update_operators([
        sp.variant("add_operator", items_tokens.operator_param.make(
            owner = alice.address,
            operator = world.address,
            token_id = item_alice
        ))
    ]).run(sender = alice, valid = True)

    position = sp.bytes("0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")

    #
    # Test placing items
    #
    scenario.h2("Placing items")

    # place some items not owned
    world.place_items(lot_id = place_bob, owner=sp.none, item_list = [sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position))]).run(sender = bob, valid = False)
    world.place_items(lot_id = place_bob, owner=sp.none, item_list = [sp.variant("item", sp.record(token_amount = 500, token_id = item_bob, xtz_per_token = sp.tez(1), item_data = position))]).run(sender = bob, valid = False)

    # place some items in a lot not owned (without setting owner)
    world.place_items(lot_id = place_alice, owner=sp.none, item_list = [
        sp.variant("item", sp.record(token_amount = 1, token_id = item_bob, xtz_per_token = sp.tez(1), item_data = position))
    ]).run(sender = bob, valid = False, exception = "NOT_OWNER")
    world.place_items(lot_id = place_bob, owner=sp.none, item_list = [
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position))
    ]).run(sender = alice, valid = False, exception = "NOT_OWNER")

    # place some items and make sure tokens are tranferred.
    balance_before = scenario.compute(items_tokens.get_balance(sp.record(owner = bob.address, token_id = item_bob)))

    world.place_items(lot_id = place_bob, owner=sp.none, item_list = [sp.variant("item", sp.record(token_amount = 1, token_id = item_bob, xtz_per_token = sp.tez(1), item_data = position))]).run(sender = bob)

    balance_after = scenario.compute(items_tokens.get_balance(sp.record(owner = bob.address, token_id = item_bob)))
    scenario.verify(sp.to_int(balance_after) == (balance_before - 1))

    # place some more items
    world.place_items(lot_id = place_bob, owner=sp.none, item_list = [sp.variant("item", sp.record(token_amount = 2, token_id = item_bob, xtz_per_token = sp.tez(1), item_data = position))]).run(sender = bob)
    world.place_items(lot_id = place_bob, owner=sp.none, item_list = [sp.variant("item", sp.record(token_amount = 1, token_id = item_bob, xtz_per_token = sp.tez(0), item_data = position))]).run(sender = bob)

    world.place_items(lot_id = place_alice, owner=sp.none, item_list = [sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position))]).run(sender = alice)
    world.place_items(lot_id = place_alice, owner=sp.none, item_list = [sp.variant("item", sp.record(token_amount = 2, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position))]).run(sender = alice)

    #
    # get (buy) items.
    #
    scenario.h2("Gettting items")

    # make sure sequence number changes on interaction. need to use compute here to eval immediate.
    check_before_sequence_number = scenario.compute(world.get_place_seqnum(place_bob))
    world.get_item(lot_id = place_bob, item_id = 1).run(sender = alice, amount = sp.tez(1))
    scenario.verify(check_before_sequence_number != world.get_place_seqnum(place_bob))

    # test wrong amount
    world.get_item(lot_id = place_bob, item_id = 1).run(sender = alice, amount = sp.tez(15), valid = False, exception = "WRONG_AMOUNT")
    world.get_item(lot_id = place_bob, item_id = 1).run(sender = alice, amount = sp.mutez(1500), valid = False, exception = "WRONG_AMOUNT")

    # make sure item tokens and dao tokens are transferred 
    balance_before = scenario.compute(items_tokens.get_balance(sp.record(owner = alice.address, token_id = item_bob)))
    dao_balance_alice_before = scenario.compute(dao_token.get_balance(sp.record(owner = alice.address, token_id = 0)))
    dao_balance_bob_before = scenario.compute(dao_token.get_balance(sp.record(owner = bob.address, token_id = 0)))
    dao_balance_manager_before = scenario.compute(dao_token.get_balance(sp.record(owner = admin.address, token_id = 0)))

    world.get_item(lot_id = place_bob, item_id = 1).run(sender = alice, amount = sp.tez(1))

    balance_after = scenario.compute(items_tokens.get_balance(sp.record(owner = alice.address, token_id = item_bob)))
    dao_balance_alice_after = scenario.compute(dao_token.get_balance(sp.record(owner = alice.address, token_id = 0)))
    dao_balance_bob_after = scenario.compute(dao_token.get_balance(sp.record(owner = bob.address, token_id = 0)))
    dao_balance_manager_after = scenario.compute(dao_token.get_balance(sp.record(owner = admin.address, token_id = 0)))
    scenario.verify(balance_after == (balance_before + 1))
    scenario.verify(dao_balance_alice_after == (dao_balance_alice_before + sp.nat(500000)))
    scenario.verify(dao_balance_bob_after == (dao_balance_bob_before + sp.nat(500000)))
    scenario.verify(dao_balance_manager_after == (dao_balance_manager_before + sp.nat(250000)))

    # test not for sale
    world.get_item(lot_id = place_bob, item_id = 2).run(sender = alice, amount = sp.tez(1), valid = False, exception = "NOT_FOR_SALE")

    # test getting some more items
    world.get_item(lot_id = place_bob, item_id = 1).run(sender = alice, amount = sp.tez(1), valid = False) # missing item in map
    world.get_item(lot_id = place_alice, item_id = 1).run(sender = bob, amount = sp.tez(1))
    world.get_item(lot_id = place_alice, item_id = 1).run(sender = bob, amount = sp.tez(1))
    world.get_item(lot_id = place_alice, item_id = 1).run(sender = bob, amount = sp.tez(1), valid = False) # missing item in map

    #
    # remove items
    #
    scenario.h2("Removing items")
    
    # remove items in a lot not owned
    world.remove_items(lot_id = place_bob, owner=sp.none, item_list = [0]).run(sender = alice, valid = False)
    world.remove_items(lot_id = place_alice, owner=sp.none, item_list = [0]).run(sender = bob, valid = False)

    # remove items and make sure tokens are transferred
    balance_before = scenario.compute(items_tokens.get_balance(sp.record(owner = bob.address, token_id = item_bob)))

    world.remove_items(lot_id = place_bob, owner=sp.none, item_list = [0]).run(sender = bob)

    balance_after = scenario.compute(items_tokens.get_balance(sp.record(owner = bob.address, token_id = item_bob)))
    scenario.verify(balance_after == (balance_before + 1))
    
    world.remove_items(lot_id = place_alice, owner=sp.none, item_list = [0]).run(sender = alice)

    #place multiple items
    world.place_items(lot_id = place_alice, owner=sp.none, item_list = [
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position))
    ]).run(sender = alice)

    #place items with invalid data
    world.place_items(lot_id = place_alice, owner=sp.none, item_list = [
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = sp.bytes('0xFFFFFFFF'))),
    ]).run(sender = alice, valid = False, exception = "DATA_LEN")

    #
    # test ext items
    #
    scenario.h2("Ext items")

    # place an ext item
    scenario.h3("Place ext items")
    world.place_items(lot_id = place_bob, owner=sp.none, item_list = [
        sp.variant("ext", sp.utils.bytes_of_string("test_string data1")),
        sp.variant("ext", sp.utils.bytes_of_string("test_string data2")),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_bob, xtz_per_token = sp.tez(1), item_data = position))
    ]).run(sender = bob)

    scenario.h3("Get ext item")
    item_counter = world.data.places.get(place_bob).counter
    world.get_item(lot_id = place_bob, item_id = abs(item_counter - 2)).run(sender = bob, amount = sp.tez(1), valid = False, exception = "WRONG_ITEM_TYPE")
    world.get_item(lot_id = place_bob, item_id = abs(item_counter - 3)).run(sender = bob, amount = sp.tez(1), valid = False, exception = "WRONG_ITEM_TYPE")

    scenario.h3("Remvove ext items")
    world.remove_items(lot_id = place_bob, owner=sp.none, item_list = [2]).run(sender = bob)
    world.remove_items(lot_id = place_bob, owner=sp.none, item_list = [3, 4]).run(sender = bob)

    #
    # set place props
    #
    scenario.h2("Set place props")
    world.set_place_props(lot_id = place_bob, owner=sp.none, props = sp.bytes('0xFFFFFF')).run(sender = bob)
    scenario.verify(world.data.places[place_bob].place_props == sp.bytes('0xFFFFFF'))
    world.set_place_props(lot_id = place_bob, owner=sp.none, props = sp.bytes('0xFFFFFFFFFF')).run(sender = bob)
    world.set_place_props(lot_id = place_bob, owner=sp.none, props = sp.bytes('0xFFFF')).run(sender = bob, valid = False, exception = "DATA_LEN")
    world.set_place_props(lot_id = place_bob, owner=sp.none, props = sp.bytes('0xFFFFFFFFFF')).run(sender = alice, valid = False, exception = "NOT_OWNER")

    #
    # test place related views
    #
    scenario.h2("Place views")

    scenario.h3("Stored items")
    stored_items = world.get_place_data(place_alice)
    scenario.verify(stored_items.place_props == sp.bytes('0x82b881'))
    scenario.verify(stored_items.stored_items[2].open_variant("item").item_amount == 1)
    scenario.verify(stored_items.stored_items[3].open_variant("item").item_amount == 1)
    scenario.verify(stored_items.stored_items[4].open_variant("item").item_amount == 1)
    scenario.show(stored_items)

    stored_items_empty = world.get_place_data(sp.nat(5))
    scenario.verify(sp.len(stored_items_empty.stored_items) == 0)
    scenario.show(stored_items_empty)

    scenario.h3("Sequence numbers")
    sequence_number = scenario.compute(world.get_place_seqnum(place_alice))
    scenario.verify(sequence_number == sp.sha3(sp.pack(sp.pair(sp.nat(3), sp.nat(5)))))
    scenario.show(sequence_number)

    sequence_number_empty = scenario.compute(world.get_place_seqnum(sp.nat(5)))
    scenario.verify(sequence_number_empty == sp.sha3(sp.pack(sp.pair(sp.nat(0), sp.nat(0)))))
    scenario.show(sequence_number_empty)

    #
    # Test item limit
    #
    scenario.h2("Item Limit")

    scenario.h3("set_item_limit")
    scenario.verify(world.data.item_limit == 32)
    world.set_item_limit(128).run(sender = bob, valid = False)
    world.set_item_limit(128).run(sender = admin)
    scenario.verify(world.data.item_limit == 128)

    scenario.h3("get_item_limit view")
    item_limit = world.get_item_limit()
    scenario.verify(item_limit == sp.nat(128))
    scenario.show(item_limit)

    scenario.h3("item limit on place_items")
    world.set_item_limit(10).run(sender = admin)
    world.place_items(lot_id = place_alice, owner=sp.none, item_list = [
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
    ]).run(sender = alice, valid = False, exception = 'ITEM_LIMIT')

    #
    # Test other permitted FA2
    #
    scenario.h2("Other permitted FA2")

    scenario.h3("Other token mint and operator")
    other_token.mint(address = alice.address,
        amount = 50,
        metadata = sp.map(l = { "" : sp.utils.bytes_of_string("ipfs://Qtesttesttest") }),
        token_id = 0).run(sender = admin)

    other_token.update_operators([
        sp.variant("add_operator", other_token.operator_param.make(
            owner = alice.address,
            operator = world.address,
            token_id = 0
        ))
    ]).run(sender = alice, valid = True)

    # test set permitted
    scenario.h3("set_other_fa2_permitted")
    world.set_other_fa2_permitted(fa2 = other_token.address, permitted = True).run(sender = bob, valid = False, exception = "ONLY_MANAGER")
    scenario.verify(world.data.other_permitted_fa2.contains(other_token.address) == False)

    world.set_other_fa2_permitted(fa2 = other_token.address, permitted = True).run(sender = admin)
    scenario.verify(world.data.other_permitted_fa2.contains(other_token.address) == True)

    world.set_other_fa2_permitted(fa2 = other_token.address, permitted = False).run(sender = admin)
    scenario.verify(world.data.other_permitted_fa2.contains(other_token.address) == False)

    # test unpermitted place_item
    scenario.h3("Test placing unpermitted 'other' type items")
    world.place_items(lot_id = place_alice, owner=sp.none, item_list = [
        sp.variant("other", sp.record(token_id = 0, fa2 = other_token.address, item_data = position))
    ]).run(sender = alice, valid = False, exception = "TOKEN_NOT_PERMITTED")

    # test get
    scenario.h3("get_other_permitted_fa2 view")
    scenario.show(world.is_other_fa2_permitted(other_token.address))
    scenario.verify(world.is_other_fa2_permitted(other_token.address) == False)
    world.set_other_fa2_permitted(fa2 = other_token.address, permitted = True).run(sender = admin)
    scenario.verify(world.is_other_fa2_permitted(other_token.address) == True)

    # test place_item
    scenario.h3("Test placing/removing/getting permitted 'other' type items")

    scenario.h4("place")
    world.place_items(lot_id = place_alice, owner=sp.none, item_list = [
        sp.variant("other", sp.record(token_id = 0, fa2 = other_token.address, item_data = position)),
        sp.variant("other", sp.record(token_id = 0, fa2 = other_token.address, item_data = position))
    ]).run(sender = alice)
    # TODO: verify token was transferred

    scenario.h4("get")
    item_counter = world.data.places.get(place_alice).counter
    world.get_item(lot_id = place_alice, item_id = abs(item_counter - 1)).run(sender = bob, amount = sp.tez(1), valid = False, exception = "WRONG_ITEM_TYPE")
    world.get_item(lot_id = place_alice, item_id = abs(item_counter - 2)).run(sender = bob, amount = sp.tez(1), valid = False, exception = "WRONG_ITEM_TYPE")

    scenario.h4("remove")
    world.remove_items(lot_id = place_alice, owner=sp.none, item_list = [abs(item_counter - 1), abs(item_counter - 2)]).run(sender = alice)
    # TODO: verify tokens were transferred

    #
    # test set fees
    #
    scenario.h2("Fees")
    world.set_fees(35).run(sender = bob, valid = False)
    world.set_fees(250).run(sender = admin, valid = False)
    world.set_fees(45).run(sender = admin)

    #
    # test world operators
    #
    scenario.h2("World operators")

    scenario.h3("Change place without op")
    # alice tries to place an item in bobs place but isn't an op
    world.place_items(lot_id=place_bob, owner=sp.some(bob.address), item_list=[
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, xtz_per_token=sp.tez(1), item_data=position))
    ]).run(sender=alice, valid=False, exception="NOT_OPERATOR")

    # alice tries to set place props in bobs place but isn't an op
    world.set_place_props(lot_id=place_bob, owner=sp.some(bob.address), props=sp.bytes('0xFFFFFFFFFF')).run(sender=alice, valid=False, exception="NOT_OPERATOR")

    scenario.h3("Add operator")

    scenario.h4("Valid add operator")
    # bob makes alice an operator of his place
    world.update_operators([
        sp.variant("add_operator", world.operator_param.make(
            owner = bob.address,
            operator = alice.address,
            token_id = place_bob
        ))
    ]).run(sender=bob, valid=True)

    # alice can now place/remove items in bobs place, set props
    world.place_items(lot_id=place_bob, owner=sp.some(bob.address), item_list=[
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, xtz_per_token=sp.tez(1), item_data=position))
    ]).run(sender=alice, valid=True)

    world.set_place_props(lot_id=place_bob, owner=sp.some(bob.address), props=sp.bytes('0xFFFFFFFFFF')).run(sender=alice, valid=True)

    scenario.h4("Invalid add operator")
    # bob makes himself op of alices place
    world.update_operators([
        sp.variant("add_operator", world.operator_param.make(
            owner = alice.address,
            operator = bob.address,
            token_id = place_alice
        ))
    ]).run(sender=bob, valid=False, exception="NOT_OWNER")

    # bob is not allowed to place items in alices place.
    world.place_items(lot_id=place_alice, owner=sp.some(alice.address), item_list=[
        sp.variant("item", sp.record(token_amount=1, token_id=item_bob, xtz_per_token=sp.tez(1), item_data=position))
    ]).run(sender=bob, valid=False, exception="NOT_OPERATOR")

    scenario.h3("No operator after transfer")
    # bob transfers his place to carol
    places_tokens.transfer([places_tokens.batch_transfer.item(from_ = bob.address,
        txs = [
            sp.record(to_=carol.address,
                amount=1,
                token_id=place_bob)
        ])
    ]).run(sender=bob)

    # alice won't be an operator anymore
    world.place_items(lot_id=place_bob, owner=sp.some(bob.address), item_list=[
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, xtz_per_token=sp.tez(1), item_data=position))
    ]).run(sender=alice, valid=False, exception="NOT_OPERATOR")

    # and also alice will not be operator on carols place
    world.place_items(lot_id=place_bob, owner=sp.some(carol.address), item_list=[
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, xtz_per_token=sp.tez(1), item_data=position))
    ]).run(sender=alice, valid=False, exception="NOT_OPERATOR")

    # neither will bob
    world.place_items(lot_id=place_bob, owner=sp.some(carol.address), item_list=[
        sp.variant("item", sp.record(token_amount=1, token_id=item_bob, xtz_per_token=sp.tez(1), item_data=position))
    ]).run(sender=bob, valid=False, exception="NOT_OPERATOR")

    scenario.h3("Invalid remove operator")
    # alice cant remove herself from operators of bobs (now not owned) place
    world.update_operators([
        sp.variant("remove_operator", world.operator_param.make(
            owner = bob.address,
            operator = alice.address,
            token_id = place_bob
        ))
    ]).run(sender=alice, valid=False, exception="NOT_OWNER")

    scenario.h3("Valid remove operator")
    # bob removes alice from operators of his (now not owned) place
    world.update_operators([
        sp.variant("remove_operator", world.operator_param.make(
            owner = bob.address,
            operator = alice.address,
            token_id = place_bob
        ))
    ]).run(sender=bob, valid=True)

    #
    # the end.
    scenario.table_of_contents()