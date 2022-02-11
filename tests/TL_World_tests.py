import smartpy as sp

minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter.py")
places_contract = sp.io.import_script_from_url("file:contracts/TL_World.py")
fa2_contract = sp.io.import_script_from_url("file:contracts/FA2.py")

# utility contract to get token balances
class FA2_utils(sp.Contract):
    def __init__(self, fa2):
        self.init(last_sum = 0, fa2 = fa2)

    @sp.entry_point
    def reinit(self):
        self.data.last_sum = 0
        # It's also nice to make this contract have more than one entry point.

    @sp.onchain_view()
    def token_amounts(self, params):
        sp.set_type(params, sp.TList(t=places_contract.placeItemListType))
        # todo put into function
        token_amts = sp.local("token_amts", sp.map(tkey=sp.TNat, tvalue=sp.TRecord(amount=sp.TNat, fa2=sp.TAddress)))
        sp.for curr in params:
            with curr.match_cases() as arg:
                with arg.match("item") as item:
                    sp.if token_amts.value.contains(item.token_id):
                        token_amts.value[item.token_id].amount = token_amts.value[item.token_id].amount + item.token_amount
                    sp.else:
                        token_amts.value[item.token_id] = sp.record(amount = item.token_amount, fa2 = self.data.fa2)
                with arg.match("other") as other:
                    sp.if token_amts.value.contains(other.token_id):
                        token_amts.value[other.token_id].amount = token_amts.value[other.token_id].amount + other.token_amount
                    sp.else:
                        token_amts.value[other.token_id] = sp.record(amount = other.token_amount, fa2 = other.fa2)
        sp.result(token_amts.value)

    @sp.onchain_view()
    def get_balances(self, params):
        sp.set_type(params.tokens, sp.TMap(sp.TNat, sp.TRecord(amount=sp.TNat, fa2=sp.TAddress)))
        sp.set_type(params.owner, sp.TAddress)

        balances = sp.local("balances", sp.map(tkey = sp.TNat, tvalue = sp.TNat))
        sp.for curr in params.tokens.keys():
            balances.value[curr] = self.fa2_get_balance(params.tokens[curr].fa2, curr, params.owner)
        
        sp.result(balances.value)

    @sp.onchain_view()
    def cmp_balances(self, params):
        sp.set_type(params.bal_a, sp.TMap(sp.TNat, sp.TNat))
        sp.set_type(params.bal_b, sp.TMap(sp.TNat, sp.TNat))
        sp.set_type(params.amts, sp.TMap(sp.TNat, sp.TRecord(amount=sp.TNat, fa2=sp.TAddress)))

        sp.verify((sp.len(params.bal_a) == sp.len(params.bal_b)) & (sp.len(params.bal_b) == sp.len(params.amts)))

        sp.for curr in params.bal_a.keys():
            sp.verify(params.bal_a[curr] == params.bal_b[curr] + params.amts[curr].amount)
        
        sp.result(True)

    def fa2_get_balance(self, fa2, token_id, owner):
        return sp.view("get_balance", fa2,
            sp.set_type_expr(
                sp.record(owner = owner, token_id = token_id),
                sp.TRecord(
                    owner = sp.TAddress,
                    token_id = sp.TNat
                ).layout(("owner", "token_id"))),
            t = sp.TNat).open_some()



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

    items_utils = FA2_utils(items_tokens.address)
    scenario += items_utils

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
        metadata = fa2_contract.FA2.make_metadata(name = "tz1and DAO",
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

    # utility function for checking correctness of placing item using the FA2_utils contract
    # TODO: also check item id is in map now
    def place_items(lot_id: sp.TNat, token_arr: list[sp.TVariant], sender: sp.TestAccount, valid: bool = True, message: str = None, lot_owner: sp.TOption = sp.none):
        if valid == True:
            before_sequence_number = scenario.compute(world.get_place_seqnum(lot_id))
            tokens_amounts = scenario.compute(items_utils.token_amounts(token_arr))
            balances_sender_before = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = sender.address)))
            balances_world_before = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = world.address)))
    
        prev_next_id = scenario.compute(world.data.places.get(lot_id, default_value=places_contract.placeStorageDefault).next_id)
        world.place_items(lot_id = lot_id, owner = lot_owner, item_list = token_arr).run(sender = sender, valid = valid, exception = message)
    
        if valid == True:
            # check seqnum
            scenario.verify(before_sequence_number != world.get_place_seqnum(place_bob))
            # check counter
            scenario.verify(prev_next_id + len(token_arr) == world.data.places[lot_id].next_id)
            # check tokens were transferred
            balances_sender_after = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = sender.address)))
            balances_world_after = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = world.address)))
            scenario.verify(items_utils.cmp_balances(sp.record(bal_a = balances_sender_before, bal_b = balances_sender_after, amts = tokens_amounts)))
            scenario.verify(items_utils.cmp_balances(sp.record(bal_a = balances_world_after, bal_b = balances_world_before, amts = tokens_amounts)))

    # utility function for checking correctness of getting item using the FA2_utils contract
    # TODO: also check item in map changed
    def get_item(lot_id: sp.TNat, item_id: sp.TNat, issuer: sp.TAddress, sender: sp.TestAccount, amount: sp.TMutez, valid: bool = True, message: str = None, owner: sp.TOption = sp.none):
        if valid == True:
            before_sequence_number = scenario.compute(world.get_place_seqnum(lot_id))
            tokens_amounts = {scenario.compute(world.data.places[lot_id].stored_items[issuer].get(item_id).open_variant("item").token_id) : sp.record(amount=1, fa2=items_tokens.address)}
            balances_sender_before = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = sender.address)))
            balances_world_before = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = world.address)))
    
        prev_interaction_counter = scenario.compute(world.data.places.get(lot_id, default_value=places_contract.placeStorageDefault).interaction_counter)
        world.get_item(lot_id = lot_id, item_id = item_id, issuer = issuer).run(sender = sender, amount = amount, valid = valid, exception = message)
    
        if valid == True:
            # check seqnum
            scenario.verify(before_sequence_number != world.get_place_seqnum(place_bob))
            # check counter
            scenario.verify(prev_interaction_counter + 1 == world.data.places[lot_id].interaction_counter)
            # check tokens were transferred
            balances_sender_after = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = sender.address)))
            balances_world_after = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = world.address)))
            scenario.verify(items_utils.cmp_balances(sp.record(bal_a = balances_sender_after, bal_b = balances_sender_before, amts = tokens_amounts)))
            scenario.verify(items_utils.cmp_balances(sp.record(bal_a = balances_world_before, bal_b = balances_world_after, amts = tokens_amounts)))

    #
    # Test placing items
    #
    scenario.h2("Placing items")

    # place some items not owned
    place_items(place_bob, [sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position))], bob, valid = False, message='FA2_NOT_OPERATOR')
    place_items(place_bob, [sp.variant("item", sp.record(token_amount = 500, token_id = item_bob, xtz_per_token = sp.tez(1), item_data = position))], bob, valid = False, message='FA2_INSUFFICIENT_BALANCE')

    # place some items in a lot not owned (without setting owner)
    place_items(place_alice, [sp.variant("item", sp.record(token_amount = 1, token_id = item_bob, xtz_per_token = sp.tez(1), item_data = position))], bob, valid=False, message="NO_PERMISSION")
    place_items(place_bob, [sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position))], alice, valid=False, message="NO_PERMISSION")

    # place some items and make sure tokens are tranferred. TODO: remove
    place_items(place_bob, [sp.variant("item", sp.record(token_amount = 1, token_id = item_bob, xtz_per_token = sp.tez(1), item_data = position))], bob)

    # place some more items
    place_items(place_bob, [sp.variant("item", sp.record(token_amount = 2, token_id = item_bob, xtz_per_token = sp.tez(1), item_data = position))], bob)
    place_items(place_bob, [sp.variant("item", sp.record(token_amount = 1, token_id = item_bob, xtz_per_token = sp.tez(0), item_data = position))], bob)
    scenario.verify(~sp.is_failing(world.data.places[place_bob].stored_items[bob.address][0].open_variant('item')))

    place_items(place_alice, [sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position))], alice)
    place_items(place_alice, [sp.variant("item", sp.record(token_amount = 2, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position))], alice)
    scenario.verify(~sp.is_failing(world.data.places[place_alice].stored_items[alice.address][0].open_variant('item')))

    #
    # get (buy) items.
    #
    scenario.h2("Gettting items")

    # make sure sequence number changes on interaction. need to use compute here to eval immediate.
    check_before_sequence_number = scenario.compute(world.get_place_seqnum(place_bob))
    get_item(place_bob, 1, bob.address, sender = alice, amount = sp.tez(1))
    scenario.verify(check_before_sequence_number != world.get_place_seqnum(place_bob))

    # test wrong amount
    get_item(place_bob, 1, bob.address, sender=alice, amount=sp.tez(15), valid=False, message="WRONG_AMOUNT")
    get_item(place_bob, 1, bob.address, sender=alice, amount=sp.mutez(1500), valid=False, message="WRONG_AMOUNT")

    # make sure item tokens and dao tokens are transferred 
    dao_balance_alice_before = scenario.compute(dao_token.get_balance(sp.record(owner = alice.address, token_id = 0)))
    dao_balance_bob_before = scenario.compute(dao_token.get_balance(sp.record(owner = bob.address, token_id = 0)))
    dao_balance_manager_before = scenario.compute(dao_token.get_balance(sp.record(owner = admin.address, token_id = 0)))

    get_item(place_bob, 1, bob.address, sender=alice, amount=sp.tez(1))

    dao_balance_alice_after = scenario.compute(dao_token.get_balance(sp.record(owner = alice.address, token_id = 0)))
    dao_balance_bob_after = scenario.compute(dao_token.get_balance(sp.record(owner = bob.address, token_id = 0)))
    dao_balance_manager_after = scenario.compute(dao_token.get_balance(sp.record(owner = admin.address, token_id = 0)))
    scenario.verify(dao_balance_alice_after == (dao_balance_alice_before + sp.nat(500000)))
    scenario.verify(dao_balance_bob_after == (dao_balance_bob_before + sp.nat(500000)))
    scenario.verify(dao_balance_manager_after == (dao_balance_manager_before + sp.nat(250000)))

    # test not for sale
    get_item(place_bob, 2, bob.address, sender=alice, amount=sp.tez(1), valid=False, message="NOT_FOR_SALE")

    # test getting some more items
    get_item(place_bob, 1, bob.address, sender=alice, amount=sp.tez(1), valid=False) # missing item in map
    get_item(place_alice, 1, alice.address, sender=bob, amount=sp.tez(1))
    get_item(place_alice, 1, alice.address, sender=bob, amount=sp.tez(1))
    get_item(place_alice, 1, alice.address, sender=bob, amount=sp.tez(1), valid=False) # missing item in map

    #
    # remove items
    #
    scenario.h2("Removing items")
    
    # remove items in a lot not owned
    world.remove_items(lot_id = place_bob, owner=sp.none, remove_map = {bob.address: [0]} ).run(sender = alice, valid = False)
    world.remove_items(lot_id = place_alice, owner=sp.none, remove_map = {alice.address: [0]} ).run(sender = bob, valid = False)

    # remove items and make sure tokens are transferred
    balance_before = scenario.compute(items_tokens.get_balance(sp.record(owner = bob.address, token_id = item_bob)))

    world.remove_items(lot_id = place_bob, owner=sp.none, remove_map = {bob.address: [0]} ).run(sender = bob)

    balance_after = scenario.compute(items_tokens.get_balance(sp.record(owner = bob.address, token_id = item_bob)))
    scenario.verify(balance_after == (balance_before + 1))
    # todo: make sure item is not in map
    
    world.remove_items(lot_id = place_alice, owner=sp.none, remove_map = {alice.address: [0]} ).run(sender = alice)

    #place multiple items
    place_items(place_alice, [
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position))
    ], alice)

    #place items with invalid data
    place_items(place_alice, [sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = sp.bytes('0xFFFFFFFF')))], sender=alice, valid=False, message="DATA_LEN")

    #
    # test ext items
    #
    scenario.h2("Ext items")

    # place an ext item
    scenario.h3("Place ext items")
    place_items(place_bob, [
        sp.variant("ext", sp.utils.bytes_of_string("test_string data1")),
        sp.variant("ext", sp.utils.bytes_of_string("test_string data2")),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_bob, xtz_per_token = sp.tez(1), item_data = position))
    ], sender = bob)

    scenario.h3("Get ext item")
    item_counter = world.data.places.get(place_bob).next_id
    get_item(place_bob, abs(item_counter - 2), bob.address, sender=bob, amount=sp.tez(1), valid=False, message="WRONG_ITEM_TYPE")
    get_item(place_bob, abs(item_counter - 3), bob.address, sender=bob, amount=sp.tez(1), valid=False, message="WRONG_ITEM_TYPE")

    scenario.h3("Remvove ext items")
    world.remove_items(lot_id = place_bob, owner=sp.none, remove_map = {bob.address: [abs(item_counter - 3)]} ).run(sender = bob)

    #
    # set place props
    #
    scenario.h2("Set place props")
    world.set_place_props(lot_id = place_bob, owner=sp.none, props = sp.bytes('0xFFFFFF')).run(sender = bob)
    scenario.verify(world.data.places[place_bob].place_props == sp.bytes('0xFFFFFF'))
    world.set_place_props(lot_id = place_bob, owner=sp.none, props = sp.bytes('0xFFFFFFFFFF')).run(sender = bob)
    world.set_place_props(lot_id = place_bob, owner=sp.none, props = sp.bytes('0xFFFF')).run(sender = bob, valid = False, exception = "DATA_LEN")
    world.set_place_props(lot_id = place_bob, owner=sp.none, props = sp.bytes('0xFFFFFFFFFF')).run(sender = alice, valid = False, exception = "NO_PERMISSION")

    #
    # set_item_data
    #
    scenario.h2("Set item data")
    new_item_data = sp.bytes("0x01010101010101010101010101010101")
    world.set_item_data(lot_id = place_bob, owner=sp.none, update_map = {bob.address: [
        sp.record(item_id = abs(item_counter - 2), item_data = new_item_data),
        sp.record(item_id = abs(item_counter - 1), item_data = new_item_data)
    ]} ).run(sender = alice, valid = False, exception = "NO_PERMISSION")

    world.set_item_data(lot_id = place_bob, owner=sp.none, update_map = {bob.address: [
        sp.record(item_id = abs(item_counter - 2), item_data = new_item_data),
        sp.record(item_id = abs(item_counter - 1), item_data = new_item_data)
    ]} ).run(sender = bob)

    scenario.verify(world.data.places[place_bob].stored_items[bob.address][abs(item_counter - 2)].open_variant('ext') == new_item_data)
    scenario.verify(world.data.places[place_bob].stored_items[bob.address][abs(item_counter - 1)].open_variant('item').item_data == new_item_data)

    #
    # test place related views
    #
    scenario.h2("Place views")

    scenario.h3("Stored items")
    stored_items = world.get_place_data(place_alice)
    scenario.verify(stored_items.place_props == sp.bytes('0x82b881'))
    scenario.verify(stored_items.stored_items[alice.address][2].open_variant("item").item_amount == 1)
    scenario.verify(stored_items.stored_items[alice.address][3].open_variant("item").item_amount == 1)
    scenario.verify(stored_items.stored_items[alice.address][4].open_variant("item").item_amount == 1)
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
    place_items(place_alice, [
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, xtz_per_token = sp.tez(1), item_data = position))
    ], sender=alice, valid=False, message='ITEM_LIMIT')

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
    world.set_other_fa2_permitted(fa2 = other_token.address, permitted = True, swap_permitted = False).run(sender = bob, valid = False, exception = "ONLY_MANAGER")
    scenario.verify(world.data.other_permitted_fa2.contains(other_token.address) == False)

    world.set_other_fa2_permitted(fa2 = other_token.address, permitted = True, swap_permitted = False).run(sender = admin)
    scenario.verify(world.data.other_permitted_fa2.contains(other_token.address) == True)
    scenario.verify(world.data.other_permitted_fa2[other_token.address] == False)

    world.set_other_fa2_permitted(fa2 = other_token.address, permitted = True, swap_permitted = True).run(sender = admin)
    scenario.verify(world.data.other_permitted_fa2.contains(other_token.address) == True)
    scenario.verify(world.data.other_permitted_fa2[other_token.address] == True)

    world.set_other_fa2_permitted(fa2 = other_token.address, permitted = False, swap_permitted = False).run(sender = admin)
    scenario.verify(world.data.other_permitted_fa2.contains(other_token.address) == False)
    scenario.verify(sp.is_failing(world.data.other_permitted_fa2[other_token.address]))

    # test unpermitted place_item
    scenario.h3("Test placing unpermitted 'other' type items")
    place_items(place_alice, [
        sp.variant("other", sp.record(token_id = 0, token_amount=1, xtz_per_token=sp.tez(0), fa2 = other_token.address, item_data = position))
    ], sender=alice, valid=False, message="TOKEN_NOT_PERMITTED")

    # test get
    scenario.h3("get_other_permitted_fa2 view")
    scenario.show(world.is_other_fa2_permitted(other_token.address))
    scenario.verify(world.is_other_fa2_permitted(other_token.address) == False)
    world.set_other_fa2_permitted(fa2 = other_token.address, permitted = True, swap_permitted = False).run(sender = admin)
    scenario.verify(world.is_other_fa2_permitted(other_token.address) == True)

    # test place_item
    scenario.h3("Test placing/removing/getting permitted 'other' type items")

    scenario.h4("place")
    place_items(place_alice, [
        sp.variant("other", sp.record(token_id = 0, token_amount=1, xtz_per_token=sp.tez(0), fa2 = other_token.address, item_data = position)),
        sp.variant("other", sp.record(token_id = 0, token_amount=1, xtz_per_token=sp.tez(0), fa2 = other_token.address, item_data = position))
    ], sender=alice)
    # TODO: verify token was transferred

    # NOTE: make sure other type tokens can only be placed one at a time and aren't swappable, for now.
    place_items(place_alice, [
        sp.variant("other", sp.record(token_id = 0, token_amount=2, xtz_per_token=sp.tez(0), fa2 = other_token.address, item_data = position)),
    ], sender=alice, valid=False, message="PARAM_ERROR")

    place_items(place_alice, [
        sp.variant("other", sp.record(token_id = 0, token_amount=1, xtz_per_token=sp.tez(1), fa2 = other_token.address, item_data = position)),
    ], sender=alice, valid=False, message="PARAM_ERROR")

    place_items(place_alice, [
        sp.variant("other", sp.record(token_id = 0, token_amount=22, xtz_per_token=sp.tez(1), fa2 = other_token.address, item_data = position)),
    ], sender=alice, valid=False, message="PARAM_ERROR")

    scenario.h4("get")
    item_counter = world.data.places.get(place_alice).next_id
    get_item(place_alice, abs(item_counter - 1), alice.address, sender=bob, amount=sp.tez(1), valid=False, message="WRONG_ITEM_TYPE")
    get_item(place_alice, abs(item_counter - 2), alice.address, sender=bob, amount=sp.tez(1), valid=False, message="WRONG_ITEM_TYPE")

    scenario.h4("remove")
    world.remove_items(lot_id = place_alice, owner=sp.none, remove_map = {alice.address: [abs(item_counter - 1), abs(item_counter - 2)]} ).run(sender = alice)
    # TODO: verify tokens were transferred

    #
    # test set fees
    #
    scenario.h2("Fees")
    world.set_fees(35).run(sender = bob, valid = False)
    world.set_fees(250).run(sender = admin, valid = False)
    world.set_fees(45).run(sender = admin)

    #
    # test world permissions
    #
    scenario.h2("World permissions")

    scenario.h3("Change place without perms")
    # alice tries to place an item in bobs place but isn't an op
    place_items(place_bob, [
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, xtz_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(bob.address), sender=alice, valid=False, message="NO_PERMISSION")

    scenario.verify(world.get_permissions(sp.record(lot_id=place_bob, owner=sp.some(bob.address), permittee=alice.address)) == places_contract.permissionNone)

    # alice tries to set place props in bobs place but isn't an op
    world.set_place_props(lot_id=place_bob, owner=sp.some(bob.address), props=sp.bytes('0xFFFFFFFFFF')).run(sender=alice, valid=False, exception="NO_PERMISSION")

    scenario.h3("Add permission")

    scenario.h4("Valid add permission")
    # bob gives alice permission to his place
    world.update_permissions([
        sp.variant("add_permission", world.permission_param.make_add(
            owner = bob.address,
            permittee = alice.address,
            token_id = place_bob,
            perm = sp.nat(7)
        ))
    ]).run(sender=bob, valid=True)

    scenario.verify(world.get_permissions(sp.record(lot_id=place_bob, owner=sp.some(bob.address), permittee=alice.address)) == places_contract.permissionFull)

    # alice can now place/remove items in bobs place, set props, set item data
    place_items(place_bob, [
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, xtz_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(bob.address), sender=alice, valid=True)

    # verify issuer is set correctly.
    last_item = abs(world.data.places[place_bob].next_id - 1)
    scenario.verify(~sp.is_failing(world.data.places[place_bob].stored_items[alice.address][last_item].open_variant('item')))

    world.set_item_data(lot_id = place_bob, owner=sp.some(bob.address), update_map = {alice.address: [
        sp.record(item_id = last_item, item_data = new_item_data)
    ]} ).run(sender = alice, valid = True)

    scenario.verify(world.data.places[place_bob].stored_items[alice.address][last_item].open_variant('item').item_data == new_item_data)

    world.set_place_props(lot_id=place_bob, owner=sp.some(bob.address), props=sp.bytes('0xFFFFFFFFFF')).run(sender=alice, valid=True)

    scenario.h4("Invalid add permission")
    # bob gives himself permissions to alices place
    world.update_permissions([
        sp.variant("add_permission", world.permission_param.make_add(
            owner = alice.address,
            permittee = bob.address,
            token_id = place_alice,
            perm = sp.nat(7)
        ))
    ]).run(sender=bob, valid=False, exception="NOT_OWNER")

    scenario.verify(world.get_permissions(sp.record(lot_id=place_alice, owner=sp.some(alice.address), permittee=bob.address)) == places_contract.permissionNone)

    # bob is not allowed to place items in alices place.
    place_items(place_alice, [
        sp.variant("item", sp.record(token_amount=1, token_id=item_bob, xtz_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(alice.address), sender=bob, valid=False, message="NO_PERMISSION")

    scenario.h3("No permission after transfer")
    # bob transfers his place to carol
    places_tokens.transfer([places_tokens.batch_transfer.item(from_ = bob.address,
        txs = [
            sp.record(to_=carol.address,
                amount=1,
                token_id=place_bob)
        ])
    ]).run(sender=bob)

    # alice won't have permission anymore
    place_items(place_bob, [
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, xtz_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(bob.address), sender=alice, valid=False, message="NO_PERMISSION")

    scenario.verify(world.get_permissions(sp.record(lot_id=place_bob, owner=sp.some(bob.address), permittee=alice.address)) == places_contract.permissionNone)

    # and also alice will not have persmissions on carols place
    place_items(place_bob, [
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, xtz_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(carol.address), sender=alice, valid=False, message="NO_PERMISSION")

    scenario.verify(world.get_permissions(sp.record(lot_id=place_bob, owner=sp.some(carol.address), permittee=alice.address)) == places_contract.permissionNone)

    # neither will bob
    place_items(place_bob, [
        sp.variant("item", sp.record(token_amount=1, token_id=item_bob, xtz_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(carol.address), sender=bob, valid=False, message="NO_PERMISSION")

    scenario.verify(world.get_permissions(sp.record(lot_id=place_bob, owner=sp.some(carol.address), permittee=bob.address)) == places_contract.permissionNone)

    scenario.h3("Invalid remove permission")
    # alice cant remove own permission to bobs (now not owned) place
    world.update_permissions([
        sp.variant("remove_permission", world.permission_param.make_remove(
            owner = bob.address,
            permittee = alice.address,
            token_id = place_bob
        ))
    ]).run(sender=alice, valid=False, exception="NOT_OWNER")

    scenario.h3("Valid remove permission")
    # bob removes alice's permissions to his (now not owned) place
    world.update_permissions([
        sp.variant("remove_permission", world.permission_param.make_remove(
            owner = bob.address,
            permittee = alice.address,
            token_id = place_bob
        ))
    ]).run(sender=bob, valid=True)

    scenario.verify(world.get_permissions(sp.record(lot_id=place_bob, owner=sp.some(bob.address), permittee=alice.address)) == places_contract.permissionNone)

    #
    # test some swapping edge cases
    #
    scenario.h2("place/get item edge cases")

    # place item for 1 mutez
    place_items(place_alice, [
        sp.variant("item", sp.record(token_amount=1, token_id=item_alice, xtz_per_token=sp.mutez(1), item_data=position))
    ], sender=alice, valid=True)

    # try to get it
    item_counter = world.data.places.get(place_alice).next_id
    get_item(place_alice, abs(item_counter - 1), alice.address, sender=bob, amount=sp.mutez(1), valid=True)

    #
    # test paused
    #
    scenario.h2("pausing")
    scenario.verify(world.data.paused == False)
    world.set_paused(True).run(sender = bob, valid = False, exception = "ONLY_MANAGER")
    world.set_paused(True).run(sender = alice, valid = False, exception = "ONLY_MANAGER")
    world.set_paused(True).run(sender = admin)
    scenario.verify(world.data.paused == True)

    # anything that changes a place or transfers tokens is now disabled
    world.set_place_props(lot_id=place_bob, owner=sp.none, props=sp.bytes('0xFFFFFFFFFF')).run(sender=carol, valid = False, exception = "ONLY_UNPAUSED")

    place_items(place_alice, [
        sp.variant("item", sp.record(token_amount=1, token_id=item_alice, xtz_per_token=sp.tez(1), item_data=position))
    ], sender=alice, valid=False, message="ONLY_UNPAUSED")

    get_item(place_alice, 3, alice.address, sender=bob, amount=sp.mutez(1), valid=False, message="ONLY_UNPAUSED")

    world.remove_items(lot_id = place_alice, owner=sp.none, remove_map = {alice.address: [3]} ).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")

    # update permissions is still allowed
    world.update_permissions([
        sp.variant("remove_permission", world.permission_param.make_remove(
            owner = bob.address,
            permittee = alice.address,
            token_id = place_bob
        ))
    ]).run(sender=bob, valid=True)

    world.set_paused(False).run(sender = bob, valid = False, exception = "ONLY_MANAGER")
    world.set_paused(False).run(sender = alice, valid = False, exception = "ONLY_MANAGER")
    world.set_paused(False).run(sender = admin)
    scenario.verify(world.data.paused == False)

    world.set_place_props(lot_id=place_bob, owner=sp.none, props=sp.bytes('0xFFFFFFFFFF')).run(sender=carol)

    #
    # the end.
    scenario.table_of_contents()