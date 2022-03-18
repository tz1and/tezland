import smartpy as sp

minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter.py")
places_contract = sp.io.import_script_from_url("file:contracts/TL_World.py")
tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")
fa2_test_lib = sp.io.import_script_from_url("file:tests/lib/FA2_test_lib.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")


# TODO: test royalties, fees, issuer being paid, lol


# utility contract to get token balances
class FA2_utils(sp.Contract):
    def __init__(self, fa2):
        self.init(last_sum = 0, fa2 = fa2)

    @sp.entry_point
    def reinit(self):
        self.data.last_sum = 0
        # It's also nice to make this contract have more than one entry point.

    @sp.onchain_view(pure=True)
    def token_amounts(self, params):
        sp.set_type(params, sp.TList(t=places_contract.placeItemListType))
        token_amts = sp.local("token_amts", sp.map(tkey=sp.TNat, tvalue=sp.TRecord(amount=sp.TNat, fa2=sp.TAddress)))
        with sp.for_("curr", params) as curr:
            with curr.match_cases() as arg:
                with arg.match("item") as item:
                    with sp.if_(token_amts.value.contains(item.token_id)):
                        token_amts.value[item.token_id].amount = token_amts.value[item.token_id].amount + item.token_amount
                    with sp.else_():
                        token_amts.value[item.token_id] = sp.record(amount = item.token_amount, fa2 = self.data.fa2)
                with arg.match("other") as other:
                    with sp.if_(token_amts.value.contains(other.token_id)):
                        token_amts.value[other.token_id].amount = token_amts.value[other.token_id].amount + other.token_amount
                    with sp.else_():
                        token_amts.value[other.token_id] = sp.record(amount = other.token_amount, fa2 = other.fa2)
        
        #sp.trace(token_amts.value)
        sp.result(token_amts.value)

    @sp.onchain_view(pure=True)
    def token_amounts_in_storage(self, params):
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.world, sp.TAddress)
        sp.set_type(params.remove_map, sp.TMap(sp.TAddress, sp.TList(sp.TNat)))

        world_data = sp.compute(self.world_get_place_data(params.world, params.lot_id))
        token_amts = sp.local("token_amts", sp.map(tkey=sp.TNat, tvalue=sp.TRecord(amount=sp.TNat, fa2=sp.TAddress)))
        with sp.for_("issuer", params.remove_map.keys()) as issuer:
            issuer_store = world_data.stored_items[issuer]
            with sp.for_("item_id", params.remove_map[issuer]) as item_id:
                with issuer_store[item_id].match_cases() as arg:
                    with arg.match("item") as item:
                        with sp.if_(token_amts.value.contains(item.token_id)):
                            token_amts.value[item.token_id].amount = token_amts.value[item.token_id].amount + item.item_amount
                        with sp.else_():
                            token_amts.value[item.token_id] = sp.record(amount = item.item_amount, fa2 = self.data.fa2)
                    with arg.match("other") as other:
                        with sp.if_(token_amts.value.contains(other.token_id)):
                            token_amts.value[other.token_id].amount = token_amts.value[other.token_id].amount + other.item_amount
                        with sp.else_():
                            token_amts.value[other.token_id] = sp.record(amount = other.item_amount, fa2 = other.fa2)

        #sp.trace(token_amts.value)
        sp.result(token_amts.value)

    @sp.onchain_view(pure=True)
    def get_balances(self, params):
        sp.set_type(params.tokens, sp.TMap(sp.TNat, sp.TRecord(amount=sp.TNat, fa2=sp.TAddress)))
        sp.set_type(params.owner, sp.TAddress)

        balances = sp.local("balances", sp.map(tkey = sp.TNat, tvalue = sp.TNat))
        with sp.for_("curr", params.tokens.keys()) as curr:
            balances.value[curr] = utils.fa2_get_balance(params.tokens[curr].fa2, curr, params.owner)
        
        #sp.trace(balances.value)
        sp.result(balances.value)

    @sp.onchain_view(pure=True)
    def cmp_balances(self, params):
        sp.set_type(params.bal_a, sp.TMap(sp.TNat, sp.TNat))
        sp.set_type(params.bal_b, sp.TMap(sp.TNat, sp.TNat))
        sp.set_type(params.amts, sp.TMap(sp.TNat, sp.TRecord(amount=sp.TNat, fa2=sp.TAddress)))

        #sp.trace("cmp_balances")
        #sp.trace(params.bal_a)
        #sp.trace(params.bal_b)
        #sp.trace(params.amts)

        sp.verify((sp.len(params.bal_a) == sp.len(params.bal_b)) & (sp.len(params.bal_b) == sp.len(params.amts)))

        with sp.for_("curr", params.bal_a.keys()) as curr:
            sp.verify(params.bal_a[curr] == params.bal_b[curr] + params.amts[curr].amount)
        
        sp.result(True)

    def world_get_place_data(self, world, lot_id):
        return sp.view("get_place_data", world,
            sp.set_type_expr(
                lot_id,
                sp.TNat),
            t = places_contract.placeStorageType).open_some()



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
    items_tokens = tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    items_utils = FA2_utils(items_tokens.address)
    scenario += items_utils

    scenario.h2("places")
    places_tokens = tokens.tz1andPlaces(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += places_tokens

    scenario.h2("minter")
    minter = minter_contract.TL_Minter(admin.address, items_tokens.address, places_tokens.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    scenario.h2("dao")
    dao_token = tokens.tz1andDAO(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += dao_token

    scenario.h2("some other FA2 token")
    other_token = tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += other_token

    scenario.h2("preparation")
    items_tokens.transfer_administrator(minter.address).run(sender = admin)
    places_tokens.transfer_administrator(minter.address).run(sender = admin)
    minter.accept_fa2_administrator([items_tokens.address, places_tokens.address]).run(sender = admin)

    # mint some item tokens for testing
    scenario.h3("minting items")
    minter.mint_Item(to_ = bob.address,
        amount = 4,
        royalties = 250,
        contributors = [ sp.record(address=bob.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    minter.mint_Item(to_ = alice.address,
        amount = 25,
        royalties = 250,
        contributors = [ sp.record(address=alice.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)

    item_bob = sp.nat(0)
    item_alice = sp.nat(1)

    # mint some place tokens for testing
    scenario.h3("minting places")
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

    #
    # Test places
    #
    scenario.h1("Test World")

    #
    # create World contract
    #
    scenario.h2("Originate World contract")
    world = places_contract.TL_World(admin.address, items_tokens.address, places_tokens.address, dao_token.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += world

    #
    # set operators
    #
    scenario.h2("Add world as operator for items")
    items_tokens.update_operators([
        sp.variant("add_operator", sp.record(
            owner = bob.address,
            operator = world.address,
            token_id = item_bob
        ))
    ]).run(sender = bob, valid = True)

    items_tokens.update_operators([
        sp.variant("add_operator", sp.record(
            owner = alice.address,
            operator = world.address,
            token_id = item_alice
        ))
    ]).run(sender = alice, valid = True)

    position = sp.bytes("0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")

    # utility function for checking correctness of placing item using the FA2_utils contract
    # TODO: also check item id is in map now
    def place_items(lot_id: sp.TNat, token_arr: list[sp.TVariant], sender: sp.TestAccount, valid: bool = True, message: str = None, lot_owner: sp.TOption = sp.none):
        if valid == True:
            before_sequence_number = scenario.compute(world.get_place_seqnum(lot_id))
            tokens_amounts = scenario.compute(items_utils.token_amounts(token_arr))
            balances_sender_before = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = sender.address)))
            balances_world_before = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = world.address)))
    
        prev_next_id = scenario.compute(world.data.places.get(lot_id, default_value=places_contract.placeStorageDefault).next_id)
        world.place_items(lot_id = lot_id, owner = lot_owner, item_list = token_arr, extension = sp.none).run(sender = sender, valid = valid, exception = message)
    
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
    def get_item(lot_id: sp.TNat, item_id: sp.TNat, issuer: sp.TAddress, sender: sp.TestAccount, amount: sp.TMutez, valid: bool = True, message: str = None, now = None):
        if valid == True:
            before_sequence_number = scenario.compute(world.get_place_seqnum(lot_id))
            tokens_amounts = {scenario.compute(world.data.places[lot_id].stored_items[issuer].get(item_id).open_variant("item").token_id) : sp.record(amount=1, fa2=items_tokens.address)}
            balances_sender_before = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = sender.address)))
            balances_world_before = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = world.address)))
    
        prev_interaction_counter = scenario.compute(world.data.places.get(lot_id, default_value=places_contract.placeStorageDefault).interaction_counter)
        world.get_item(lot_id = lot_id, item_id = item_id, issuer = issuer, extension = sp.none).run(sender = sender, amount = amount, valid = valid, exception = message, now = now)
    
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

    # utility function for checking correctness of removing items using the FA2_utils contract
    # TODO: make sure item is not in map
    def remove_items(lot_id: sp.TNat, remove_map, sender: sp.TestAccount, valid: bool = True, message: str = None, lot_owner: sp.TOption = sp.none):
        if valid == True:
            before_sequence_number = scenario.compute(world.get_place_seqnum(lot_id))
            tokens_amounts = scenario.compute(items_utils.token_amounts_in_storage(sp.record(world = world.address, lot_id = lot_id, remove_map = remove_map)))
            balances_sender_before = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = sender.address)))
            balances_world_before = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = world.address)))
        
        prev_interaction_counter = scenario.compute(world.data.places.get(lot_id, default_value=places_contract.placeStorageDefault).interaction_counter)
        world.remove_items(lot_id = lot_id, owner = lot_owner, remove_map = remove_map, extension = sp.none).run(sender = sender, valid = valid, exception = message)
        
        if valid == True:
            # check seqnum
            scenario.verify(before_sequence_number != world.get_place_seqnum(place_bob))
            # check counter
            scenario.verify(prev_interaction_counter + 1 == world.data.places[lot_id].interaction_counter)
            # check tokens were transferred
            # TODO: breaks when removing tokens from multiple issuers. needs to be map of issuer to map of whatever
            balances_sender_after = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = sender.address)))
            balances_world_after = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, owner = world.address)))
            scenario.verify(items_utils.cmp_balances(sp.record(bal_a = balances_sender_after, bal_b = balances_sender_before, amts = tokens_amounts)))
            scenario.verify(items_utils.cmp_balances(sp.record(bal_a = balances_world_before, bal_b = balances_world_after, amts = tokens_amounts)))

    #
    # Test placing items
    #
    scenario.h2("Placing items")

    # place some items not owned
    place_items(place_bob, [sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position))], bob, valid = False, message='FA2_NOT_OPERATOR')
    place_items(place_bob, [sp.variant("item", sp.record(token_amount = 500, token_id = item_bob, mutez_per_token = sp.tez(1), item_data = position))], bob, valid = False, message='FA2_INSUFFICIENT_BALANCE')

    # place some items in a lot not owned (without setting owner)
    place_items(place_alice, [sp.variant("item", sp.record(token_amount = 1, token_id = item_bob, mutez_per_token = sp.tez(1), item_data = position))], bob, valid=False, message="NO_PERMISSION")
    place_items(place_bob, [sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position))], alice, valid=False, message="NO_PERMISSION")

    # place some items and make sure tokens are tranferred. TODO: remove
    place_items(place_bob, [sp.variant("item", sp.record(token_amount = 1, token_id = item_bob, mutez_per_token = sp.tez(1), item_data = position))], bob)

    # place some more items
    place_items(place_bob, [sp.variant("item", sp.record(token_amount = 2, token_id = item_bob, mutez_per_token = sp.tez(1), item_data = position))], bob)
    place_items(place_bob, [sp.variant("item", sp.record(token_amount = 1, token_id = item_bob, mutez_per_token = sp.tez(0), item_data = position))], bob)
    scenario.verify(~sp.is_failing(world.data.places[place_bob].stored_items[bob.address][0].open_variant('item')))

    place_items(place_alice, [sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position))], alice)
    place_items(place_alice, [sp.variant("item", sp.record(token_amount = 2, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position))], alice)
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

    # Correct amount
    get_item(place_bob, 1, bob.address, sender=alice, amount=sp.tez(1))

    # test not for sale
    get_item(place_bob, 2, bob.address, sender=alice, amount=sp.tez(1), valid=False, message="NOT_FOR_SALE")

    # test getting some more items
    get_item(place_bob, 1, bob.address, sender=alice, amount=sp.tez(1), valid=False) # missing item in map

    get_item(place_alice, 1, alice.address, sender=bob, amount=sp.tez(1), now=sp.now.add_days(80))

    get_item(place_alice, 1, alice.address, sender=bob, amount=sp.tez(1))
    get_item(place_alice, 1, alice.address, sender=bob, amount=sp.tez(1), valid=False) # missing item in map

    #
    # remove items
    #
    scenario.h2("Removing items")
    
    # remove items in a lot not owned
    remove_items(place_bob, {bob.address: [0]}, sender=alice, valid=False)
    remove_items(place_alice, {alice.address: [0]}, sender=bob, valid=False)

    # remove items and make sure tokens are transferred. TODO: remove this
    remove_items(place_bob, {bob.address: [0]}, sender=bob)
    
    remove_items(place_alice, {alice.address: [0]}, sender=alice)

    #place multiple items
    place_items(place_alice, [
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position))
    ], alice)

    #place items with invalid data
    place_items(place_alice, [sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = sp.bytes('0xFFFFFFFF')))], sender=alice, valid=False, message="DATA_LEN")

    #
    # test ext items
    #
    scenario.h2("Ext items")

    # place an ext item
    scenario.h3("Place ext items")
    place_items(place_bob, [
        sp.variant("ext", sp.utils.bytes_of_string("test_string data1")),
        sp.variant("ext", sp.utils.bytes_of_string("test_string data2")),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_bob, mutez_per_token = sp.tez(1), item_data = position))
    ], sender = bob)

    scenario.h3("Get ext item")
    item_counter = world.data.places.get(place_bob).next_id
    get_item(place_bob, sp.as_nat(item_counter - 2), bob.address, sender=bob, amount=sp.tez(1), valid=False, message="WRONG_ITEM_TYPE")
    get_item(place_bob, sp.as_nat(item_counter - 3), bob.address, sender=bob, amount=sp.tez(1), valid=False, message="WRONG_ITEM_TYPE")

    scenario.h3("Remvove ext items")
    remove_items(place_bob, {bob.address: [sp.as_nat(item_counter - 3)]}, sender=bob)

    #
    # set place props
    #
    scenario.h2("Set place props")
    valid_place_props = {sp.bytes("0x00"): sp.bytes('0xFFFFFF')}
    world.set_place_props(lot_id = place_bob, owner=sp.none, props = valid_place_props, extension = sp.none).run(sender = bob)
    scenario.verify(world.data.places[place_bob].place_props.get(sp.bytes("0x00")) == sp.bytes('0xFFFFFF'))
    world.set_place_props(lot_id = place_bob, owner=sp.none, props = valid_place_props, extension = sp.none).run(sender = bob)
    world.set_place_props(lot_id = place_bob, owner=sp.none, props = {sp.bytes("0x00"): sp.bytes('0xFFFF')}, extension = sp.none).run(sender = bob, valid = False, exception = "DATA_LEN")
    world.set_place_props(lot_id = place_bob, owner=sp.none, props = {sp.bytes("0x01"): sp.bytes('0xFFFFFF')}, extension = sp.none).run(sender = bob, valid = False, exception = "PARAM_ERROR")
    world.set_place_props(lot_id = place_bob, owner=sp.none, props = valid_place_props, extension = sp.none).run(sender = alice, valid = False, exception = "NO_PERMISSION")

    #
    # set_item_data
    #
    scenario.h2("Set item data")
    new_item_data = sp.bytes("0x010101010101010101010101010101")
    world.set_item_data(lot_id = place_bob, owner=sp.none, extension = sp.none, update_map = {bob.address: [
        sp.record(item_id = sp.as_nat(item_counter - 2), item_data = new_item_data),
        sp.record(item_id = sp.as_nat(item_counter - 1), item_data = new_item_data)
    ]} ).run(sender = alice, valid = False, exception = "NO_PERMISSION")

    world.set_item_data(lot_id = place_bob, owner=sp.none, extension = sp.none, update_map = {bob.address: [
        sp.record(item_id = sp.as_nat(item_counter - 2), item_data = new_item_data),
        sp.record(item_id = sp.as_nat(item_counter - 1), item_data = new_item_data)
    ]} ).run(sender = bob)

    scenario.verify(world.data.places[place_bob].stored_items[bob.address][sp.as_nat(item_counter - 2)].open_variant('ext') == new_item_data)
    scenario.verify(world.data.places[place_bob].stored_items[bob.address][sp.as_nat(item_counter - 1)].open_variant('item').item_data == new_item_data)

    #
    # test place related views
    #
    scenario.h2("Place views")

    scenario.h3("Stored items")
    stored_items = world.get_place_data(place_alice)
    scenario.verify(stored_items.place_props.get(sp.bytes("0x00")) == sp.bytes('0x82b881'))
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

    scenario.h3("set_global_limits")
    scenario.verify(world.data.item_limit == 64)
    world.update_item_limit(128).run(sender = bob, valid = False)
    world.update_item_limit(128).run(sender = admin)
    scenario.verify(world.data.item_limit == 128)

    scenario.verify(world.data.max_permission == places_contract.permissionFull)
    world.update_max_permission(127).run(sender = bob, valid = False)
    world.update_max_permission(96).run(sender = admin, valid = False, exception="PARAM_ERROR")
    world.update_max_permission(127).run(sender = admin)
    scenario.verify(world.data.max_permission == 127)

    scenario.h3("get_item_limit view")
    item_limit = world.get_item_limit()
    scenario.verify(item_limit == sp.nat(128))
    scenario.show(item_limit)

    scenario.h3("item limit on place_items")
    world.update_item_limit(10).run(sender = admin)
    place_items(place_alice, [
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position)),
        sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = position))
    ], sender=alice, valid=False, message='ITEM_LIMIT')

    #
    # Test other permitted FA2
    #
    scenario.h2("Other permitted FA2")

    scenario.h3("Other token mint and operator")
    other_token.mint(
        [sp.record(
            to_=alice.address,
            amount=50,
            token=sp.variant("new", sp.record(
                metadata={ "" : sp.utils.bytes_of_string("ipfs://Qtesttesttest") },
                royalties=sp.record(
                    royalties=250,
                    contributors=[ sp.record(address=alice.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ])
                )
            )
        )]
    ).run(sender = admin)

    other_token.update_operators([
        sp.variant("add_operator", sp.record(
            owner = alice.address,
            operator = world.address,
            token_id = 0
        ))
    ]).run(sender = alice, valid = True)

    # test unpermitted place_item
    scenario.h3("Test placing unpermitted 'other' type items")
    place_items(place_alice, [
        sp.variant("other", sp.record(token_id = 0, token_amount=1, mutez_per_token=sp.tez(0), fa2 = other_token.address, item_data = position))
    ], sender=alice, valid=False, message="TOKEN_NOT_PERMITTED")

    scenario.h3("set_fa2_permitted: swap_allowed=False")
    add_permitted = sp.list([sp.variant("add_permitted",
        sp.record(
            fa2 = other_token.address,
            props = sp.record(
                swap_allowed = False,
                royalties_kind = sp.variant("none", sp.unit))))])

    world.set_fa2_permitted(add_permitted).run(sender = admin)

    # test place_item
    scenario.h3("Test placing/removing/getting permitted 'other' type items")

    scenario.h4("place")
    place_items(place_alice, [
        sp.variant("other", sp.record(token_id = 0, token_amount=1, mutez_per_token=sp.tez(0), fa2 = other_token.address, item_data = position)),
        sp.variant("other", sp.record(token_id = 0, token_amount=1, mutez_per_token=sp.tez(0), fa2 = other_token.address, item_data = position))
    ], sender=alice)

    # NOTE: make sure other type tokens can only be placed one at a time and aren't swappable, for now.
    place_items(place_alice, [
        sp.variant("other", sp.record(token_id = 0, token_amount=2, mutez_per_token=sp.tez(0), fa2 = other_token.address, item_data = position)),
    ], sender=alice, valid=False, message="PARAM_ERROR")

    place_items(place_alice, [
        sp.variant("other", sp.record(token_id = 0, token_amount=1, mutez_per_token=sp.tez(1), fa2 = other_token.address, item_data = position)),
    ], sender=alice, valid=False, message="PARAM_ERROR")

    place_items(place_alice, [
        sp.variant("other", sp.record(token_id = 0, token_amount=22, mutez_per_token=sp.tez(1), fa2 = other_token.address, item_data = position)),
    ], sender=alice, valid=False, message="PARAM_ERROR")

    scenario.h4("get")
    item_counter = world.data.places.get(place_alice).next_id
    get_item(place_alice, sp.as_nat(item_counter - 1), alice.address, sender=bob, amount=sp.tez(1), valid=False, message="NOT_FOR_SALE")
    get_item(place_alice, sp.as_nat(item_counter - 2), alice.address, sender=bob, amount=sp.tez(1), valid=False, message="NOT_FOR_SALE")

    scenario.h4("remove")
    remove_items(place_alice, {alice.address: [sp.as_nat(item_counter - 1), sp.as_nat(item_counter - 2)]}, sender=alice)

    #
    # test world permissions
    #
    scenario.h2("World permissions")

    scenario.h3("Change place without perms")
    # alice tries to place an item in bobs place but isn't an op
    place_items(place_bob, [
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, mutez_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(bob.address), sender=alice, valid=False, message="NO_PERMISSION")

    scenario.verify(world.get_permissions(sp.record(lot_id=place_bob, owner=sp.some(bob.address), permittee=alice.address)) == places_contract.permissionNone)

    # alice tries to set place props in bobs place but isn't an op
    world.set_place_props(lot_id=place_bob, owner=sp.some(bob.address), props=valid_place_props, extension = sp.none).run(sender=alice, valid=False, exception="NO_PERMISSION")

    scenario.h3("Permissions")

    #
    #
    #
    scenario.h4("Full permissions")
    # bob gives alice permission to his place
    world.set_permissions([
        sp.variant("add_permission", world.permission_param.make_add(
            owner = bob.address,
            permittee = alice.address,
            token_id = place_bob,
            perm = places_contract.permissionFull
        ))
    ]).run(sender=bob, valid=True)

    # alice can now place/remove items in bobs place, set props and set item data
    scenario.verify(world.get_permissions(sp.record(lot_id=place_bob, owner=sp.some(bob.address), permittee=alice.address)) == places_contract.permissionFull)

    # get bobs last item to make sure alice can remove
    bobs_last_item = scenario.compute(sp.as_nat(world.data.places[place_bob].next_id - 1))
    scenario.verify(~sp.is_failing(world.data.places[place_bob].stored_items[bob.address][bobs_last_item]))

    place_items(place_bob, [
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, mutez_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(bob.address), sender=alice, valid=True)

    # verify issuer is set correctly.
    last_item = scenario.compute(sp.as_nat(world.data.places[place_bob].next_id - 1))
    scenario.verify(~sp.is_failing(world.data.places[place_bob].stored_items[alice.address][last_item]))

    world.set_item_data(lot_id = place_bob, owner=sp.some(bob.address), extension = sp.none, update_map = {alice.address: [
        sp.record(item_id = last_item, item_data = new_item_data)
    ]} ).run(sender = alice, valid = True)

    scenario.verify(world.data.places[place_bob].stored_items[alice.address][last_item].open_variant('item').item_data == new_item_data)

    world.set_place_props(lot_id=place_bob, owner=sp.some(bob.address), props=valid_place_props, extension = sp.none).run(sender=alice, valid=True)

    # remove place item and one of bobs
    remove_items(place_bob, {alice.address: [last_item]}, lot_owner=sp.some(bob.address), sender=alice, valid=True)
    # TODO: checking breaks for other owners...
    #remove_items(place_bob, {bob.address: [bobs_last_item]}, lot_owner=sp.some(bob.address), sender=alice, valid=True)

    #
    #
    #
    scenario.h4("PlaceItems permissions")
    # bob gives alice place item permission to his place
    world.set_permissions([
        sp.variant("add_permission", world.permission_param.make_add(
            owner = bob.address,
            permittee = alice.address,
            token_id = place_bob,
            perm = places_contract.permissionPlaceItems
        ))
    ]).run(sender=bob, valid=True)
    
    # alice can now place items in bobs place, but can't set props or remove bobs items
    scenario.verify(world.get_permissions(sp.record(lot_id=place_bob, owner=sp.some(bob.address), permittee=alice.address)) == places_contract.permissionPlaceItems)
    
    place_items(place_bob, [
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, mutez_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(bob.address), sender=alice, valid=True)

    # verify issuer is set correctly.
    last_item = scenario.compute(sp.as_nat(world.data.places[place_bob].next_id - 1))
    scenario.verify(~sp.is_failing(world.data.places[place_bob].stored_items[alice.address][last_item]))

    # can modify own items
    world.set_item_data(lot_id = place_bob, owner=sp.some(bob.address), extension = sp.none, update_map = {alice.address: [
        sp.record(item_id = last_item, item_data = new_item_data)
    ]} ).run(sender=alice, valid=True)

    # can't set props
    world.set_place_props(lot_id=place_bob, owner=sp.some(bob.address), props=valid_place_props, extension = sp.none).run(sender=alice, valid=False, exception="NO_PERMISSION")

    # can remove own items
    remove_items(place_bob, {alice.address: [last_item]}, lot_owner=sp.some(bob.address), sender=alice, valid=True)
    # can't remove others items
    remove_items(place_bob, {bob.address: [bobs_last_item]}, lot_owner=sp.some(bob.address), sender=alice, valid=False, message="NO_PERMISSION")

    #
    #
    #
    scenario.h4("ModifyAll permissions")
    # add an item with place permisssions to test
    place_items(place_bob, [
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, mutez_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(bob.address), sender=alice, valid=True)

    # bob gives alice place item permission to his place
    world.set_permissions([
        sp.variant("add_permission", world.permission_param.make_add(
            owner = bob.address,
            permittee = alice.address,
            token_id = place_bob,
            perm = places_contract.permissionModifyAll
        ))
    ]).run(sender=bob, valid=True)
    
    # alice can now modify items in bobs place, but can't set props or place or remove bobs items
    scenario.verify(world.get_permissions(sp.record(lot_id=place_bob, owner=sp.some(bob.address), permittee=alice.address)) == places_contract.permissionModifyAll)
    
    # can't place items
    place_items(place_bob, [
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, mutez_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(bob.address), sender=alice, valid=False, message="NO_PERMISSION")

    last_item = scenario.compute(sp.as_nat(world.data.places[place_bob].next_id - 1))

    # can modify all items
    world.set_item_data(lot_id = place_bob, owner=sp.some(bob.address), extension = sp.none, update_map = {bob.address: [
        sp.record(item_id = bobs_last_item, item_data = new_item_data)
    ]} ).run(sender=alice, valid=True)

    # can't set props
    world.set_place_props(lot_id=place_bob, owner=sp.some(bob.address), extension = sp.none, props=valid_place_props).run(sender=alice, valid=False, exception="NO_PERMISSION")

    # can remove own items
    remove_items(place_bob, {alice.address: [last_item]}, lot_owner=sp.some(bob.address), sender=alice, valid=True)
    # TODO: checking breaks for other owners...
    #remove_items(place_bob, {bob.address: [bobs_last_item]}, lot_owner=sp.some(bob.address), sender=alice, valid=True)

    #
    #
    #
    scenario.h4("Props permissions")
    # bob gives alice place item permission to his place
    world.set_permissions([
        sp.variant("add_permission", world.permission_param.make_add(
            owner = bob.address,
            permittee = alice.address,
            token_id = place_bob,
            perm = places_contract.permissionProps
        ))
    ]).run(sender=bob, valid=True)
    
    # alice can now modify items in bobs place, but can't set props or place or remove bobs items
    scenario.verify(world.get_permissions(sp.record(lot_id=place_bob, owner=sp.some(bob.address), permittee=alice.address)) == places_contract.permissionProps)
    
    # can't place items
    place_items(place_bob, [
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, mutez_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(bob.address), sender=alice, valid=False, message="NO_PERMISSION")

    last_item = scenario.compute(sp.as_nat(world.data.places[place_bob].next_id - 1))

    # can modify all items
    world.set_item_data(lot_id = place_bob, owner=sp.some(bob.address), extension = sp.none, update_map = {bob.address: [
        sp.record(item_id = bobs_last_item, item_data = new_item_data)
    ]} ).run(sender=alice, valid=False, exception="NO_PERMISSION")

    # can't set props
    world.set_place_props(lot_id=place_bob, owner=sp.some(bob.address), props=valid_place_props, extension = sp.none).run(sender=alice, valid=True)

    # can remove own items. no need to test that again...
    #remove_items(place_bob, {alice.address: [last_item]}, lot_owner=sp.some(bob.address), sender=alice, valid=True)
    # can't remove others items
    remove_items(place_bob, {bob.address: [bobs_last_item]}, lot_owner=sp.some(bob.address), sender=alice, valid=False, message="NO_PERMISSION")

    #
    #
    #
    scenario.h4("Mixed permissions")
    # bob gives alice place item permission to his place
    world.set_permissions([
        sp.variant("add_permission", world.permission_param.make_add(
            owner = bob.address,
            permittee = alice.address,
            token_id = place_bob,
            perm = places_contract.permissionPlaceItems | places_contract.permissionProps
        ))
    ]).run(sender=bob, valid=True)
    
    # alice can now modify items in bobs place, and can place items, but can't set props
    scenario.verify(world.get_permissions(sp.record(lot_id=place_bob, owner=sp.some(bob.address), permittee=alice.address)) == places_contract.permissionPlaceItems | places_contract.permissionProps)
    
    place_items(place_bob, [
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, mutez_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(bob.address), sender=alice, valid=True)

    last_item = scenario.compute(sp.as_nat(world.data.places[place_bob].next_id - 1))

    # can't modify all items
    world.set_item_data(lot_id = place_bob, owner=sp.some(bob.address), extension = sp.none, update_map = {bob.address: [
        sp.record(item_id = bobs_last_item, item_data = new_item_data)
    ]} ).run(sender=alice, valid=False, exception="NO_PERMISSION")

    world.set_place_props(lot_id=place_bob, owner=sp.some(bob.address), props=valid_place_props, extension = sp.none).run(sender=alice, valid=True)

    remove_items(place_bob, {alice.address: [last_item]}, lot_owner=sp.some(bob.address), sender=alice, valid=True)
    # can't remove others items
    remove_items(place_bob, {bob.address: [bobs_last_item]}, lot_owner=sp.some(bob.address), sender=alice, valid=False, message="NO_PERMISSION")

    scenario.h4("Invalid add permission")
    # incorrect perm parameter
    world.set_permissions([
        sp.variant("add_permission", world.permission_param.make_add(
            owner = bob.address,
            permittee = alice.address,
            token_id = place_bob,
            perm = world.data.max_permission + 1
        ))
    ]).run(sender=bob, valid=False, exception="PARAM_ERROR")

    # giving no permissions is invalid. use remove
    world.set_permissions([
        sp.variant("add_permission", world.permission_param.make_add(
            owner = bob.address,
            permittee = alice.address,
            token_id = place_bob,
            perm = places_contract.permissionNone
        ))
    ]).run(sender=bob, valid=False, exception="PARAM_ERROR")

    # bob gives himself permissions to alices place
    world.set_permissions([
        sp.variant("add_permission", world.permission_param.make_add(
            owner = alice.address,
            permittee = bob.address,
            token_id = place_alice,
            perm = places_contract.permissionFull
        ))
    ]).run(sender=bob, valid=False, exception="NOT_OWNER")

    scenario.verify(world.get_permissions(sp.record(lot_id=place_alice, owner=sp.some(alice.address), permittee=bob.address)) == places_contract.permissionNone)

    # bob is not allowed to place items in alices place.
    place_items(place_alice, [
        sp.variant("item", sp.record(token_amount=1, token_id=item_bob, mutez_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(alice.address), sender=bob, valid=False, message="NO_PERMISSION")

    scenario.h3("No permission after transfer")
    # bob transfers his place to carol
    places_tokens.transfer([
        sp.record(
            from_=bob.address,
            txs=[sp.record(to_=carol.address, amount=1, token_id=place_bob)],
        )
    ]).run(sender=bob)

    # alice won't have permission anymore
    place_items(place_bob, [
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, mutez_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(bob.address), sender=alice, valid=False, message="NO_PERMISSION")

    scenario.verify(world.get_permissions(sp.record(lot_id=place_bob, owner=sp.some(bob.address), permittee=alice.address)) == places_contract.permissionNone)

    # and also alice will not have persmissions on carols place
    place_items(place_bob, [
        sp.variant("item", sp.record(token_amount=2, token_id=item_alice, mutez_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(carol.address), sender=alice, valid=False, message="NO_PERMISSION")

    scenario.verify(world.get_permissions(sp.record(lot_id=place_bob, owner=sp.some(carol.address), permittee=alice.address)) == places_contract.permissionNone)

    # neither will bob
    place_items(place_bob, [
        sp.variant("item", sp.record(token_amount=1, token_id=item_bob, mutez_per_token=sp.tez(1), item_data=position))
    ], lot_owner=sp.some(carol.address), sender=bob, valid=False, message="NO_PERMISSION")

    scenario.verify(world.get_permissions(sp.record(lot_id=place_bob, owner=sp.some(carol.address), permittee=bob.address)) == places_contract.permissionNone)

    scenario.h3("Invalid remove permission")
    # alice cant remove own permission to bobs (now not owned) place
    world.set_permissions([
        sp.variant("remove_permission", world.permission_param.make_remove(
            owner = bob.address,
            permittee = alice.address,
            token_id = place_bob
        ))
    ]).run(sender=alice, valid=False, exception="NOT_OWNER")

    scenario.h3("Valid remove permission")
    # bob removes alice's permissions to his (now not owned) place
    world.set_permissions([
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
        sp.variant("item", sp.record(token_amount=1, token_id=item_alice, mutez_per_token=sp.mutez(1), item_data=position))
    ], sender=alice, valid=True)

    # try to get it
    item_counter = world.data.places.get(place_alice).next_id
    get_item(place_alice, sp.as_nat(item_counter - 1), alice.address, sender=bob, amount=sp.mutez(1), valid=True)

    #
    # test paused
    #
    scenario.h2("pausing")
    scenario.verify(world.data.paused == False)
    world.set_paused(True).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    world.set_paused(True).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    world.set_paused(True).run(sender = admin)
    scenario.verify(world.data.paused == True)

    # anything that changes a place or transfers tokens is now disabled
    world.set_place_props(lot_id=place_bob, owner=sp.none, props=valid_place_props, extension = sp.none).run(sender=carol, valid = False, exception = "ONLY_UNPAUSED")

    place_items(place_alice, [
        sp.variant("item", sp.record(token_amount=1, token_id=item_alice, mutez_per_token=sp.tez(1), item_data=position))
    ], sender=alice, valid=False, message="ONLY_UNPAUSED")

    get_item(place_alice, 3, alice.address, sender=bob, amount=sp.mutez(1), valid=False, message="ONLY_UNPAUSED")

    remove_items(place_alice, {alice.address: [3]}, sender=alice, valid=False, message="ONLY_UNPAUSED")

    # update permissions is still allowed
    world.set_permissions([
        sp.variant("remove_permission", world.permission_param.make_remove(
            owner = bob.address,
            permittee = alice.address,
            token_id = place_bob
        ))
    ]).run(sender=bob, valid=True)

    world.set_paused(False).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    world.set_paused(False).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    world.set_paused(False).run(sender = admin)
    scenario.verify(world.data.paused == False)

    world.set_place_props(lot_id=place_bob, owner=sp.none, props=valid_place_props, extension = sp.none).run(sender=carol)

    #
    # the end.
    scenario.table_of_contents()