import smartpy as sp

minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter_v2.py")
token_factory_contract = sp.io.import_script_from_url("file:contracts/TL_TokenFactory.py")
token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
legacy_royalties_contract = sp.io.import_script_from_url("file:contracts/TL_LegacyRoyalties.py")
places_contract = sp.io.import_script_from_url("file:contracts/TL_World_v2.py")
tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")
#merkle_tree = sp.io.import_script_from_url("file:contracts/MerkleTree.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")

# Some frequently used forwarded types
PermissionParams = places_contract.PermissionParams


# TODO: test royalties, fees, issuer being paid, lol
# TODO: test chunk limits
# TODO: test chunks
# TODO: test place keys?
# TODO: test registry and collections.
# TODO: test placing items with collection merkle proof.
# TODO: test getting items with royalties merkle proof.
# TODO: test place owned items.
# TODO: token amounts calc probably still wrong in some cases (place owned items).


# utility contract to get token balances
class FA2_utils(sp.Contract):
    def __init__(self):
        self.init(last_sum = 0)

    t_token_balance_map = sp.TMap(
        sp.TRecord(
            fa2=sp.TAddress,
            token_id=sp.TNat,
            owner=sp.TOption(sp.TAddress)
        ).layout(("fa2", ("token_id", "owner"))),
        sp.TNat)

    @sp.onchain_view(pure=True)
    def token_amounts(self, params):
        sp.set_type(params.token_map, sp.TMap(sp.TNat, sp.TMap(sp.TBool, sp.TMap(sp.TAddress, sp.TList(places_contract.extensibleVariantItemType)))))
        sp.set_type(params.issuer, sp.TAddress)

        token_amts = sp.local("token_amts", sp.set_type_expr({}, self.t_token_balance_map))
        with sp.for_("issuer_map", params.token_map.values()) as issuer_map:
            with sp.for_("fa2_map", issuer_map.values()) as fa2_map:
                with sp.for_("fa2_item", fa2_map.items()) as fa2_item:
                    with sp.for_("curr", fa2_item.value) as curr:
                        with curr.match("item") as item:
                            key = sp.record(fa2=fa2_item.key, token_id=item.token_id, owner=sp.some(params.issuer))
                            token_amts.value[key] = token_amts.value.get(key, default_value=sp.nat(0)) + item.amount
        
        #sp.trace(token_amts.value)
        sp.result(token_amts.value)

    @sp.onchain_view(pure=True)
    def get_chunk_next_ids(self, params):
        sp.set_type(params.place_key, places_contract.placeKeyType)
        sp.set_type(params.chunk_ids, sp.TSet(sp.TNat))
        sp.set_type(params.world, sp.TAddress)

        world_data = sp.compute(self.world_get_place_data(params.world, params.place_key, params.chunk_ids))
        chunk_next_ids = sp.local("chunk_counters", sp.map(tkey=sp.TNat, tvalue=sp.TNat))
        with sp.for_("chunk_id", params.chunk_ids.elements()) as chunk_id:
            chunk_next_ids.value[chunk_id] = world_data.chunks[chunk_id].next_id

        sp.result(chunk_next_ids.value)

    @sp.onchain_view(pure=True)
    def check_chunk_next_ids_valid(self, params):
        sp.set_type(params.place_key, places_contract.placeKeyType)
        sp.set_type(params.prev_next_ids, sp.TMap(sp.TNat, sp.TNat))
        sp.set_type(params.place_items_map, sp.TMap(sp.TNat, sp.TMap(sp.TBool, sp.TMap(sp.TAddress, sp.TList(places_contract.extensibleVariantItemType)))))
        sp.set_type(params.world, sp.TAddress)

        per_chunk_item_add_count = sp.local("per_chunk_item_add_count", sp.map(tkey=sp.TNat, tvalue=sp.TNat))
        chunk_id_set = sp.local("chunk_id_set", sp.set(t=sp.TNat))
        with sp.for_("chunk_item", params.place_items_map.items()) as chunk_item:
            chunk_id_set.value.add(chunk_item.key)
            with sp.for_("fa2_map", chunk_item.value.values()) as fa2_map:
                with sp.for_("item_list", fa2_map.values()) as item_list:
                    per_chunk_item_add_count.value[chunk_item.key] = per_chunk_item_add_count.value.get(chunk_item.key, sp.nat(0)) + sp.len(item_list)

        #sp.trace("chunk add count and prev next ids")
        #sp.trace(per_chunk_item_add_count.value)
        #sp.trace(params.prev_next_ids)

        # validate next_ids from world data
        world_data = sp.compute(self.world_get_place_data(params.world, params.place_key, chunk_id_set.value))
        with sp.for_("chunk_id", chunk_id_set.value.elements()) as chunk_id:
            sp.verify(params.prev_next_ids[chunk_id] + per_chunk_item_add_count.value[chunk_id] == world_data.chunks[chunk_id].next_id)

        sp.result(True)

    @sp.onchain_view(pure=True)
    def get_chunk_counters(self, params):
        sp.set_type(params.place_key, places_contract.placeKeyType)
        sp.set_type(params.chunk_ids, sp.TSet(sp.TNat))
        sp.set_type(params.world, sp.TAddress)

        world_data = sp.compute(self.world_get_place_data(params.world, params.place_key, params.chunk_ids))
        chunk_counters = sp.local("chunk_counters", sp.map(tkey=sp.TNat, tvalue=sp.TNat))
        with sp.for_("chunk_id", params.chunk_ids.elements()) as chunk_id:
            chunk_counters.value[chunk_id] = world_data.chunks[chunk_id].counter

        sp.result(chunk_counters.value)

    @sp.onchain_view(pure=True)
    def check_chunk_counters_increased(self, params):
        sp.set_type(params.place_key, places_contract.placeKeyType)
        sp.set_type(params.prev_chunk_counters, sp.TMap(sp.TNat, sp.TNat))
        sp.set_type(params.world, sp.TAddress)

        chunk_id_set = sp.local("chunk_id_set", sp.set(t=sp.TNat))
        with sp.for_("chunk_id", params.prev_chunk_counters.keys()) as chunk_id:
            chunk_id_set.value.add(chunk_id)

        world_data = sp.compute(self.world_get_place_data(params.world, params.place_key, chunk_id_set.value))
        with sp.for_("chunk_counter_item", params.prev_chunk_counters.items()) as chunk_counter_item:
            sp.verify(chunk_counter_item.value + 1 == world_data.chunks[chunk_counter_item.key].counter)

        sp.result(True)

    @sp.onchain_view(pure=True)
    def remove_token_amounts_in_storage(self, params):
        sp.set_type(params.place_key, places_contract.placeKeyType)
        sp.set_type(params.chunk_ids, sp.TSet(sp.TNat))
        sp.set_type(params.world, sp.TAddress)
        sp.set_type(params.remove_map, sp.TMap(sp.TNat, sp.TMap(sp.TOption(sp.TAddress), sp.TMap(sp.TAddress, sp.TList(sp.TNat)))))

        world_data = sp.compute(self.world_get_place_data(params.world, params.place_key, params.chunk_ids))

        token_amts = sp.local("token_amts", sp.set_type_expr({}, self.t_token_balance_map))
        with sp.for_("issuer_map", params.remove_map.values()) as issuer_map:
            with sp.for_("issuer_item", issuer_map.items()) as issuer_item:
                with sp.for_("fa2", issuer_item.value.keys()) as fa2:
                    with sp.for_("chunk", world_data.chunks.values()) as chunk:
                        fa2_store = chunk.storage[issuer_item.key][fa2]
                        with sp.for_("item_id", issuer_item.value[fa2]) as item_id:
                            with fa2_store[item_id].match("item") as item:
                                key = sp.record(fa2=fa2, token_id=item.token_id, owner=issuer_item.key)
                                token_amts.value[key] = token_amts.value.get(key, default_value=sp.nat(0)) + item.amount

        #sp.trace(token_amts.value)
        sp.result(token_amts.value)

    @sp.onchain_view(pure=True)
    def all_token_amounts_in_storage(self, params):
        sp.set_type(params.place_key, places_contract.placeKeyType)
        sp.set_type(params.chunk_ids, sp.TSet(sp.TNat))
        sp.set_type(params.world, sp.TAddress)

        world_data = sp.compute(self.world_get_place_data(params.world, params.place_key, params.chunk_ids))

        token_amts = sp.local("token_amts", sp.set_type_expr({}, self.t_token_balance_map))
        
        with sp.for_("chunk_item", world_data.chunks.items()) as chunk_item:
            with sp.for_("issuer_item", chunk_item.value.storage.items()) as issuer_item:
                with sp.for_("fa2_item", issuer_item.value.items()) as fa2_item:
                    with sp.for_("item_item", fa2_item.value.items()) as item_item:
                        with item_item.value.match("item") as item:
                            key = sp.record(fa2=fa2_item.key, token_id=item.token_id, owner=issuer_item.key)
                            token_amts.value[key] = token_amts.value.get(key, default_value=sp.nat(0)) + item.amount

        #sp.trace(token_amts.value)
        sp.result(token_amts.value)

    @sp.onchain_view(pure=True)
    def get_balances(self, params):
        sp.set_type(params.tokens, self.t_token_balance_map)
        sp.set_type(params.place_owner, sp.TAddress)

        balances = sp.local("balances", sp.set_type_expr({}, self.t_token_balance_map))
        with sp.for_("curr", params.tokens.keys()) as curr:
            balances.value[curr] = utils.fa2_get_balance(curr.fa2, curr.token_id, utils.openSomeOrDefault(curr.owner, params.place_owner))
        
        #sp.trace(balances.value)
        sp.result(balances.value)

    @sp.onchain_view(pure=True)
    def get_balances_other(self, params):
        sp.set_type(params.tokens, self.t_token_balance_map)
        sp.set_type(params.owner, sp.TAddress)

        balances = sp.local("balances", sp.set_type_expr({}, self.t_token_balance_map))
        with sp.for_("curr", params.tokens.keys()) as curr:
            balances.value[curr] = utils.fa2_get_balance(curr.fa2, curr.token_id, params.owner)
        
        #sp.trace(balances.value)
        sp.result(balances.value)

    @sp.onchain_view(pure=True)
    def cmp_balances(self, params):
        sp.set_type(params.bal_a, self.t_token_balance_map)
        sp.set_type(params.bal_b, self.t_token_balance_map)
        sp.set_type(params.amts, self.t_token_balance_map)

        #sp.trace("cmp_balances")
        #sp.trace(params.amts)
        #sp.trace(params.bal_a)
        #sp.trace(params.bal_b)

        sp.verify((sp.len(params.bal_a) == sp.len(params.bal_b)) & (sp.len(params.bal_b) == sp.len(params.amts)))

        with sp.for_("curr", params.bal_a.keys()) as curr:
            sp.verify(params.bal_a[curr] == params.bal_b[curr] + params.amts[curr]) #, sp.record(bal_a = params.bal_a, bal_b = params.bal_b, amts = params.amts))
        
        sp.result(True)

    def world_get_place_data(self, world, place_key, chunk_ids):
        return sp.view("get_place_data", world,
            sp.set_type_expr(
                sp.record(place_key = place_key, chunk_ids = sp.some(chunk_ids)),
                places_contract.placeDataParam),
            t = places_contract.placeDataResultType).open_some()



@sp.add_test(name = "TL_World_v2_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    carol = sp.test_account("Carol")
    royalties_key = sp.test_account("Royalties")
    collections_key = sp.test_account("Collections")
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
    scenario.h2("Items v1")
    items_tokens = tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    items_utils = FA2_utils()
    scenario += items_utils

    scenario.h2("Places v2")
    places_tokens = tokens.tz1andPlaces_v2(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += places_tokens

    scenario.h2("TokenRegistry")
    registry = token_registry_contract.TL_TokenRegistry(admin.address, collections_key.public_key,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += registry

    scenario.h2("LegacyRoyalties")
    legacy_royalties = legacy_royalties_contract.TL_LegacyRoyalties(admin.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += legacy_royalties

    scenario.h2("Minter v2")
    minter = minter_contract.TL_Minter(admin.address, registry.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    scenario.h2("TokenFactory")
    token_factory = token_factory_contract.TL_TokenFactory(admin.address, registry.address, minter.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += token_factory
    scenario.register(token_factory.collection_contract)

    scenario.h3("registry permissions for factory")
    registry.manage_permissions([sp.variant("add_permissions", [token_factory.address])]).run(sender=admin)

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

    scenario.h2("private collection token")
    token_factory.create_token(sp.utils.bytes_of_string("ipfs://QmbWqxBEKC3P8tqsKc98xmWNzrzDtRLMiMPL8wBuTGsMnR")).run(sender=admin)
    dyn_collection_token = scenario.dynamic_contract(0, token_factory.collection_contract)

    scenario.h2("preparation")

    scenario.h3("transfer/register/mint items tokens in minter")
    items_tokens.transfer_administrator(minter.address).run(sender = admin)
    minter.accept_fa2_administrator([items_tokens.address]).run(sender = admin)
    registry.manage_collections([sp.variant("add_public", {items_tokens.address: 1})]).run(sender = admin)

    # mint some item tokens for testing
    scenario.h3("minting items")
    minter.mint_public_v1(collection = items_tokens.address,
        to_ = bob.address,
        amount = 14,
        royalties = 250,
        contributors = [ sp.record(address=alice.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    minter.mint_public_v1(collection = items_tokens.address,
        to_ = alice.address,
        amount = 25,
        royalties = 250,
        contributors = [
            sp.record(address=alice.address, relative_royalties=sp.nat(400), role=sp.variant("minter", sp.unit)),
            sp.record(address=bob.address, relative_royalties=sp.nat(300), role=sp.variant("creator", sp.unit)),
            sp.record(address=bob.address, relative_royalties=sp.nat(300), role=sp.variant("creator", sp.unit)), ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)

    minter.mint_public_v1(collection = items_tokens.address,
        to_ = admin.address,
        amount = 1000,
        royalties = 250,
        contributors = [ sp.record(address=carol.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)

    item_bob = sp.nat(0)
    item_alice = sp.nat(1)
    item_admin = sp.nat(2)

    # mint some place tokens for testing
    place_mint_params = [
        sp.record(
            to_ = bob.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        ),
        sp.record(
            to_ = alice.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        ),
        sp.record(
            to_ = carol.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        )
    ]

    scenario.h3("minting places")
    places_tokens.mint(place_mint_params).run(sender = admin)

    place_bob = sp.record(
        fa2 = places_tokens.address,
        id = sp.nat(0))
    place_bob_chunk_0 = sp.record(
        place_key = place_bob,
        chunk_id = sp.nat(0))

    place_alice = sp.record(
        fa2 = places_tokens.address,
        id = sp.nat(1))
    place_alice_chunk_0 = sp.record(
        place_key = place_alice,
        chunk_id = sp.nat(0))

    place_carol = sp.record(
        fa2 = places_tokens.address,
        id = sp.nat(2))
    place_carol_chunk_0 = sp.record(
        place_key = place_carol,
        chunk_id = sp.nat(0))
    place_carol_chunk_1 = sp.record(
        place_key = place_carol,
        chunk_id = sp.nat(1))

    #
    # Test places
    #
    scenario.h1("Test World")

    #
    # create World contract
    #
    scenario.h2("Originate World contract")
    world = places_contract.TL_World(admin.address, registry.address, legacy_royalties.address, False, items_tokens.address,
        metadata = sp.utils.metadata_of_url("https://example.com"), name = "Test World", description = "A world for testing")
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

    items_tokens.update_operators([
        sp.variant("add_operator", sp.record(
            owner = admin.address,
            operator = world.address,
            token_id = item_admin
        ))
    ]).run(sender = admin, valid = True)

    position = sp.bytes("0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")

    # utility function for getting last placed item id.
    def last_placed_item_id(chunk_key: places_contract.chunkPlaceKeyType, last_index = 1):
        return scenario.compute(sp.as_nat(world.data.chunks.get(chunk_key).next_id - last_index))

    # utility function for checking correctness of placing item using the FA2_utils contract
    # TODO: also check item id is in map now
    def place_items(
        place_key: places_contract.placeKeyType,
        token_arr: sp.TMap(sp.TNat, sp.TMap(sp.TBool, sp.TMap(sp.TAddress, sp.TList(places_contract.extensibleVariantItemType)))),
        sender: sp.TestAccount,
        valid: bool = True,
        message: str = None):

        if valid == True:
            before_sequence_numbers = scenario.compute(world.get_place_seqnum(place_key).chunk_seqs)
            tokens_amounts = scenario.compute(items_utils.token_amounts(sp.record(token_map = token_arr, issuer = sender.address)))
            balances_sender_before = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, place_owner = sender.address))) # TODO: don't use sender
            balances_world_before = scenario.compute(items_utils.get_balances_other(sp.record(tokens = tokens_amounts, owner = world.address)))
    
        prev_next_ids = scenario.compute(items_utils.get_chunk_next_ids(sp.record(place_key = place_key, chunk_ids = sp.set(token_arr.keys()), world = world.address)))
        world.place_items(
            place_key = place_key,
            place_item_map = token_arr,
            ext = sp.none
        ).run(sender = sender, valid = valid, exception = message)
    
        if valid == True:
            # check seqnum
            scenario.verify(sp.pack(before_sequence_numbers) != sp.pack(world.get_place_seqnum(place_key).chunk_seqs))
            # check next ids
            scenario.verify(items_utils.check_chunk_next_ids_valid(sp.record(place_key = place_key, prev_next_ids = prev_next_ids, place_items_map = token_arr, world = world.address)))
            # check tokens were transferred
            balances_sender_after = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, place_owner = sender.address))) # TODO: don't use sender
            balances_world_after = scenario.compute(items_utils.get_balances_other(sp.record(tokens = tokens_amounts, owner = world.address)))
            scenario.verify(items_utils.cmp_balances(sp.record(bal_a = balances_sender_before, bal_b = balances_sender_after, amts = tokens_amounts)))
            scenario.verify(items_utils.cmp_balances(sp.record(bal_a = balances_world_after, bal_b = balances_world_before, amts = tokens_amounts)))

    # utility function for checking correctness of getting item using the FA2_utils contract
    # TODO: also check item in map changed
    def get_item(
        chunk_key: places_contract.chunkPlaceKeyType,
        item_id: sp.TNat,
        issuer: sp.TOption(sp.TAddress),
        fa2: sp.TAddress,
        sender: sp.TestAccount,
        amount: sp.TMutez,
        valid: bool = True,
        message: str = None,
        now = None):

        if valid == True:
            before_sequence_number = scenario.compute(world.get_place_seqnum(chunk_key.place_key).chunk_seqs[chunk_key.chunk_id])
            tokens_amounts = {sp.record(fa2 = fa2, token_id = scenario.compute(world.data.chunks[chunk_key].storage[issuer].get(fa2).get(item_id).open_variant("item").token_id), owner = sp.some(sender.address)) : sp.nat(1)}
            balances_sender_before = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, place_owner = sender.address))) # TODO: don't use sender
            balances_world_before = scenario.compute(items_utils.get_balances_other(sp.record(tokens = tokens_amounts, owner = world.address)))
    
        prev_counter = scenario.compute(world.data.chunks.get(chunk_key, default_value=places_contract.chunkStorageDefault).counter)
        world.get_item(
            place_key = chunk_key.place_key,
            chunk_id = chunk_key.chunk_id,
            item_id = item_id,
            issuer = issuer,
            fa2 = fa2,
            ext = sp.none
        ).run(sender = sender, amount = amount, valid = valid, exception = message, now = now)
    
        if valid == True:
            # check seqnum
            scenario.verify(before_sequence_number != world.get_place_seqnum(chunk_key.place_key).chunk_seqs[chunk_key.chunk_id])
            # check counter
            scenario.verify(prev_counter + 1 == world.data.chunks[chunk_key].counter)
            # check tokens were transferred
            balances_sender_after = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, place_owner = sender.address))) # TODO: don't use sender
            balances_world_after = scenario.compute(items_utils.get_balances_other(sp.record(tokens = tokens_amounts, owner = world.address)))
            scenario.verify(items_utils.cmp_balances(sp.record(bal_a = balances_sender_after, bal_b = balances_sender_before, amts = tokens_amounts)))
            scenario.verify(items_utils.cmp_balances(sp.record(bal_a = balances_world_before, bal_b = balances_world_after, amts = tokens_amounts)))

    # utility function for checking correctness of removing items using the FA2_utils contract
    # TODO: make sure item is not in map
    def remove_items(
        place_key: places_contract.placeKeyType,
        remove_map: sp.TMap(sp.TNat, sp.TMap(sp.TOption(sp.TAddress), sp.TMap(sp.TAddress, sp.TList(sp.TNat)))),
        sender: sp.TestAccount,
        valid: bool = True,
        message: str = None):

        if valid == True:
            before_sequence_numbers = scenario.compute(world.get_place_seqnum(place_key).chunk_seqs)
            tokens_amounts = scenario.compute(items_utils.remove_token_amounts_in_storage(
                sp.record(world = world.address, place_key = place_key, chunk_ids = sp.set(remove_map.keys()), remove_map = remove_map)))
            balances_sender_before = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, place_owner = sender.address))) # TODO: don't use sender
            balances_world_before = scenario.compute(items_utils.get_balances_other(sp.record(tokens = tokens_amounts, owner = world.address)))

        prev_counters = scenario.compute(items_utils.get_chunk_counters(sp.record(place_key = place_key, chunk_ids = sp.set(remove_map.keys()), world = world.address)))
        world.remove_items(
            place_key = place_key,
            remove_map = remove_map,
            ext = sp.none
        ).run(sender = sender, valid = valid, exception = message)
        
        if valid == True:
            # check seqnum
            scenario.verify(sp.pack(before_sequence_numbers) != sp.pack(world.get_place_seqnum(place_key).chunk_seqs))
            # check counters
            scenario.verify(items_utils.check_chunk_counters_increased(sp.record(place_key = place_key, prev_chunk_counters = prev_counters, world = world.address)))
            # check tokens were transferred
            # TODO: breaks when removing tokens from multiple issuers. needs to be map of issuer to map of whatever
            balances_sender_after = scenario.compute(items_utils.get_balances(sp.record(tokens = tokens_amounts, place_owner = sender.address))) # TODO: don't use sender
            balances_world_after = scenario.compute(items_utils.get_balances_other(sp.record(tokens = tokens_amounts, owner = world.address)))
            scenario.verify(items_utils.cmp_balances(sp.record(bal_a = balances_sender_after, bal_b = balances_sender_before, amts = tokens_amounts)))
            scenario.verify(items_utils.cmp_balances(sp.record(bal_a = balances_world_before, bal_b = balances_world_after, amts = tokens_amounts)))

    #
    # Allowed places
    #

    # place items in disallowed place
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False))
    ]}}}, bob, valid = False, message='PLACE_TOKEN_NOT_ALLOWED')
    world.set_allowed_place_token(sp.list([sp.variant("add", sp.record(fa2 = places_tokens.address, place_limits = sp.record(chunk_limit = 1, chunk_item_limit = 64)))])).run(sender = admin)
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False))
    ]}}}, bob, valid = False, message='FA2_NOT_OPERATOR')

    #
    # Test placing items
    #
    scenario.h2("Placing items")

    scenario.h3("not owned")
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False))
    ]}}}, bob, valid = False, message='FA2_NOT_OPERATOR')
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 500, token_id = item_bob, rate = sp.tez(1), data = position, primary = False))
    ]}}}, bob, valid = False, message='FA2_INSUFFICIENT_BALANCE')

    scenario.h3("in a lot not owned (without setting owner)")
    place_items(place_alice, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 1, token_id = item_bob, rate = sp.tez(1), data = position, primary = False))
    ]}}}, bob, valid=False, message="NO_PERMISSION")
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False))
    ]}}}, alice, valid=False, message="NO_PERMISSION")

    scenario.h3("some more") # TODO: remove
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 1, token_id = item_bob, rate = sp.tez(1), data = position, primary = False))
    ]}}}, bob)
    bob_placed_item0 = last_placed_item_id(place_bob_chunk_0)

    # place some more items
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 2, token_id = item_bob, rate = sp.tez(1), data = position, primary = False))
    ]}}}, bob)
    bob_placed_item1 = last_placed_item_id(place_bob_chunk_0)

    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 1, token_id = item_bob, rate = sp.tez(0), data = position, primary = False))
    ]}}}, bob)
    bob_placed_item2 = last_placed_item_id(place_bob_chunk_0)
    scenario.verify(~sp.is_failing(world.data.chunks[place_bob_chunk_0].storage[sp.some(bob.address)][items_tokens.address][bob_placed_item2].open_variant('item')))

    place_items(place_alice, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False))
    ]}}}, alice)
    alice_placed_item0 = last_placed_item_id(place_alice_chunk_0)

    scenario.h3("primary = True")
    place_items(place_alice, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 2, token_id = item_alice, rate = sp.tez(1), data = position, primary = True))
    ]}}}, alice)
    alice_placed_primary = last_placed_item_id(place_alice_chunk_0)
    scenario.verify(~sp.is_failing(world.data.chunks[place_alice_chunk_0].storage[sp.some(alice.address)][items_tokens.address][alice_placed_primary].open_variant('item')))

    scenario.h3("send_to_place = True")
    place_items(place_alice, {0: {True: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 2, token_id = item_alice, rate = sp.tez(1), data = position, primary = False))
    ]}}}, alice)
    alice_placed_item_to_place_owner = last_placed_item_id(place_alice_chunk_0)
    scenario.verify(~sp.is_failing(world.data.chunks[place_alice_chunk_0].storage[sp.none][items_tokens.address][alice_placed_item_to_place_owner].open_variant('item')))

    scenario.h3("multiple items")
    place_items(place_alice, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False)),
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False)),
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False))
    ]}}}, alice)
    alice_placed_item1 = last_placed_item_id(place_alice_chunk_0, 3)
    alice_placed_item2 = last_placed_item_id(place_alice_chunk_0, 2)
    alice_placed_item3 = last_placed_item_id(place_alice_chunk_0, 1)

    scenario.h3("invalid data")
    place_items(place_alice, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = sp.bytes('0xFFFFFFFF'), primary = False))
    ]}}}, sender=alice, valid=False, message="DATA_LEN")

    #
    # get (buy) items.
    #
    scenario.h2("Gettting items")

    scenario.h3("valid")
    get_item(place_bob_chunk_0, bob_placed_item1, sp.some(bob.address), items_tokens.address, sender = alice, amount = sp.tez(1))

    scenario.h3("wrong amount")
    get_item(place_bob_chunk_0, bob_placed_item1, sp.some(bob.address), items_tokens.address, sender=alice, amount=sp.tez(15), valid=False, message="WRONG_AMOUNT")
    get_item(place_bob_chunk_0, bob_placed_item1, sp.some(bob.address), items_tokens.address, sender=alice, amount=sp.mutez(1500), valid=False, message="WRONG_AMOUNT")

    scenario.h3("correct amount")
    get_item(place_bob_chunk_0, bob_placed_item1, sp.some(bob.address), items_tokens.address, sender=alice, amount=sp.tez(1))

    scenario.h3("not for sale")
    get_item(place_bob_chunk_0, bob_placed_item2, sp.some(bob.address), items_tokens.address, sender=alice, amount=sp.tez(1), valid=False, message="NOT_FOR_SALE")

    scenario.h3("not in storage")
    get_item(place_bob_chunk_0, bob_placed_item1, sp.some(bob.address), items_tokens.address, sender=alice, amount=sp.tez(1), valid=False) # missing item in map

    scenario.h3("primary = True")
    get_item(place_alice_chunk_0, alice_placed_primary, sp.some(alice.address), items_tokens.address, sender=bob, amount=sp.tez(1), now=sp.now.add_days(80))
    get_item(place_alice_chunk_0, alice_placed_primary, sp.some(alice.address), items_tokens.address, sender=bob, amount=sp.tez(1))

    scenario.h3("place owned")
    get_item(place_alice_chunk_0, alice_placed_item_to_place_owner, sp.none, items_tokens.address, sender=carol, amount=sp.tez(1))

    scenario.h3("Missing item")
    get_item(place_alice_chunk_0, alice_placed_primary, sp.some(alice.address), items_tokens.address, sender=bob, amount=sp.tez(1), valid=False) # missing item in map

    #
    # remove items
    #
    scenario.h2("Removing items")
    
    scenario.h3("in a lot not owned")
    remove_items(place_bob, {0: {sp.some(bob.address): {items_tokens.address: [bob_placed_item0]}}}, sender=alice, valid=False)
    remove_items(place_alice, {0: {sp.some(alice.address): {items_tokens.address: [alice_placed_item0]}}}, sender=bob, valid=False)

    scenario.h3("valid and make sure tokens are transferred") # TODO: remove this
    remove_items(place_bob, {0: {sp.some(bob.address): {items_tokens.address: [bob_placed_item0]}}}, sender=bob)
    remove_items(place_alice, {0: {sp.some(alice.address): {items_tokens.address: [alice_placed_item0]}}}, sender=alice)

    scenario.h3("place owned")
    remove_items(place_alice, {0: {sp.none: {items_tokens.address: [alice_placed_item_to_place_owner]}}}, sender=bob, valid=False)
    remove_items(place_alice, {0: {sp.none: {items_tokens.address: [alice_placed_item_to_place_owner]}}}, sender=alice)

    #
    # test ext items
    #
    scenario.h2("Ext items")

    # place an ext item
    scenario.h3("Place ext items")
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("ext", sp.utils.bytes_of_string("test_string data1")),
        sp.variant("ext", sp.utils.bytes_of_string("test_string data2")),
        sp.variant("item", sp.record(amount = 1, token_id = item_bob, rate = sp.tez(1), data = position, primary = False))
    ]}}}, sender = bob)

    bob_placed_item_props = last_placed_item_id(place_bob_chunk_0, 1)
    bob_placed_ext1 = last_placed_item_id(place_bob_chunk_0, 2)
    bob_placed_ext2 = last_placed_item_id(place_bob_chunk_0, 3)

    scenario.h3("Get ext item")
    get_item(place_bob_chunk_0, bob_placed_ext1, sp.some(bob.address), items_tokens.address, sender=bob, amount=sp.tez(1), valid=False, message="WRONG_ITEM_TYPE")
    get_item(place_bob_chunk_0, bob_placed_ext2, sp.some(bob.address), items_tokens.address, sender=bob, amount=sp.tez(1), valid=False, message="WRONG_ITEM_TYPE")

    scenario.h3("Remvove ext items")
    remove_items(place_bob, {0: {sp.some(bob.address): {items_tokens.address: [
        bob_placed_ext2
    ]}}}, sender=bob)

    #
    # set place props
    #
    scenario.h2("Set place props")
    valid_place_props = [sp.variant("add_props", {sp.bytes("0x00"): sp.bytes('0xFFFFFF')})]
    other_valid_place_props_2 = [sp.variant("add_props", {sp.bytes("0xf1"): sp.utils.bytes_of_string("blablablabla")})]
    world.update_place_props(place_key = place_bob, updates = valid_place_props, ext = sp.none).run(sender = bob)
    scenario.verify(world.data.places[place_bob].props.get(sp.bytes("0x00")) == sp.bytes('0xFFFFFF'))
    world.update_place_props(place_key = place_bob, updates = other_valid_place_props_2, ext = sp.none).run(sender = bob)
    scenario.verify(world.data.places[place_bob].props.contains(sp.bytes("0x00")))
    scenario.verify(world.data.places[place_bob].props.get(sp.bytes("0xf1")) == sp.utils.bytes_of_string("blablablabla"))
    world.update_place_props(place_key = place_bob, updates = valid_place_props, ext = sp.none).run(sender = bob)
    world.update_place_props(place_key = place_bob, updates = [sp.variant("add_props", {sp.bytes("0x00"): sp.bytes('0xFFFF')})], ext = sp.none).run(sender = bob, valid = False, exception = "DATA_LEN")
    world.update_place_props(place_key = place_bob, updates = [sp.variant("del_props", [sp.bytes("0x00")])], ext = sp.none).run(sender = bob, valid = False, exception = "PARAM_ERROR")
    world.update_place_props(place_key = place_bob, updates = valid_place_props, ext = sp.none).run(sender = alice, valid = False, exception = "NO_PERMISSION")
    world.update_place_props(place_key = place_bob, updates = [sp.variant("del_props", [sp.bytes("0xf1")])], ext = sp.none).run(sender = bob)
    scenario.verify(~world.data.places[place_bob].props.contains(sp.bytes("0xf1")))

    #
    # set_item_data
    #
    scenario.h2("Set item data")
    new_item_data = sp.bytes("0x010101010101010101010101010101")
    world.set_item_data(place_key = place_bob, ext = sp.none, update_map = {0: {sp.some(bob.address): {items_tokens.address: [
        sp.record(item_id = bob_placed_ext1, data = new_item_data),
        sp.record(item_id = bob_placed_item_props, data = new_item_data)
    ]}}} ).run(sender = alice, valid = False, exception = "NO_PERMISSION")

    world.set_item_data(place_key = place_bob, ext = sp.none, update_map = {0: {sp.some(bob.address): {items_tokens.address: [
        sp.record(item_id = bob_placed_ext1, data = new_item_data),
        sp.record(item_id = bob_placed_item_props, data = new_item_data)
    ]}}} ).run(sender = bob)

    scenario.verify(world.data.chunks[place_bob_chunk_0].storage[sp.some(bob.address)][items_tokens.address][bob_placed_ext1].open_variant('ext') == new_item_data)
    scenario.verify(world.data.chunks[place_bob_chunk_0].storage[sp.some(bob.address)][items_tokens.address][bob_placed_item_props].open_variant('item').data == new_item_data)

    #
    # test place related views
    #
    scenario.h2("Place views")

    scenario.h3("Stored items")
    place_data = world.get_place_data(sp.record(place_key = place_alice, chunk_ids = sp.none))
    scenario.verify(place_data.place.props.get(sp.bytes("0x00")) == sp.bytes('0x82b881'))
    scenario.verify(place_data.chunks[0].storage[sp.some(alice.address)][items_tokens.address][alice_placed_item1].open_variant("item").amount == 1)
    scenario.verify(place_data.chunks[0].storage[sp.some(alice.address)][items_tokens.address][alice_placed_item2].open_variant("item").amount == 1)
    scenario.verify(place_data.chunks[0].storage[sp.some(alice.address)][items_tokens.address][alice_placed_item3].open_variant("item").amount == 1)
    scenario.show(place_data)

    place_data = world.get_place_data(sp.record(place_key = place_alice, chunk_ids = sp.some(sp.set([0, 1]))))
    scenario.verify(place_data.place.props.get(sp.bytes("0x00")) == sp.bytes('0x82b881'))
    scenario.verify(place_data.chunks[0].storage[sp.some(alice.address)][items_tokens.address][alice_placed_item1].open_variant("item").amount == 1)
    scenario.verify(place_data.chunks[0].storage[sp.some(alice.address)][items_tokens.address][alice_placed_item2].open_variant("item").amount == 1)
    scenario.verify(place_data.chunks[0].storage[sp.some(alice.address)][items_tokens.address][alice_placed_item3].open_variant("item").amount == 1)
    scenario.verify(sp.len(place_data.chunks[1].storage) == 0)
    scenario.show(place_data)

    empty_place_key = sp.record(fa2 = places_tokens.address, id = sp.nat(5))
    place_data = world.get_place_data(sp.record(place_key = empty_place_key, chunk_ids = sp.none))
    scenario.verify(sp.len(place_data.chunks) == 0)
    place_data = world.get_place_data(sp.record(place_key = empty_place_key, chunk_ids = sp.some(sp.set([0]))))
    scenario.verify(sp.len(place_data.chunks[0].storage) == 0)
    scenario.show(place_data)

    scenario.h3("Sequence numbers")
    sequence_number = scenario.compute(world.get_place_seqnum(place_alice))
    scenario.verify(sequence_number.place_seq == sp.sha3(sp.pack(sp.nat(0))))
    scenario.verify(sp.len(sequence_number.chunk_seqs) == 1)
    scenario.verify(sequence_number.chunk_seqs[0] == sp.sha3(sp.pack(sp.pair(sp.nat(5), sp.nat(6)))))
    scenario.show(sequence_number)

    sequence_number_empty = scenario.compute(world.get_place_seqnum(empty_place_key))
    scenario.verify(sequence_number_empty.place_seq == sp.sha3(sp.pack(sp.nat(0))))
    scenario.verify(sp.len(sequence_number_empty.chunk_seqs) == 0)
    scenario.show(sequence_number_empty)

    #
    # Test item limit
    #
    scenario.h2("Settings")

    scenario.h3("update max_permission")
    scenario.verify(world.data.max_permission == places_contract.permissionFull)
    world.update_settings([sp.variant("max_permission", 127)]).run(sender = bob, valid = False)
    world.update_settings([sp.variant("max_permission", 96)]).run(sender = admin, valid = False, exception="PARAM_ERROR")
    world.update_settings([sp.variant("max_permission", 127)]).run(sender = admin)
    scenario.verify(world.data.max_permission == 127)

    scenario.h3("update registry")
    scenario.verify(world.data.registry == registry.address)
    world.update_settings([sp.variant("registry", admin.address)]).run(sender = bob, valid = False)
    world.update_settings([sp.variant("registry", admin.address)]).run(sender = admin)
    scenario.verify(world.data.registry == admin.address)
    world.update_settings([sp.variant("registry", registry.address)]).run(sender = admin)

    scenario.h3("update migration_from")
    scenario.verify(world.data.migration_from == sp.none)
    world.update_settings([sp.variant("migration_from", sp.some(admin.address))]).run(sender = bob, valid = False)
    world.update_settings([sp.variant("migration_from", sp.some(admin.address))]).run(sender = admin)
    scenario.verify(world.data.migration_from == sp.some(admin.address))
    world.update_settings([sp.variant("migration_from", sp.none)]).run(sender = admin)

    scenario.h3("update moderation_contract")
    scenario.verify(world.data.moderation_contract == sp.none)
    world.update_settings([sp.variant("moderation_contract", sp.some(admin.address))]).run(sender = bob, valid = False)
    world.update_settings([sp.variant("moderation_contract", sp.some(admin.address))]).run(sender = admin)
    scenario.verify(world.data.moderation_contract == sp.some(admin.address))
    world.update_settings([sp.variant("moderation_contract", sp.none)]).run(sender = admin)

    scenario.h3("update fees_to")
    scenario.verify(world.data.fees_to == admin.address)
    world.update_settings([sp.variant("fees_to", bob.address)]).run(sender = bob, valid = False)
    world.update_settings([sp.variant("fees_to", bob.address)]).run(sender = admin)
    scenario.verify(world.data.fees_to == bob.address)
    world.update_settings([sp.variant("fees_to", admin.address)]).run(sender = admin)

    scenario.h3("update fees")
    scenario.verify(world.data.fees == sp.nat(25))
    world.update_settings([sp.variant("fees", sp.nat(55))]).run(sender = bob, valid = False)
    world.update_settings([sp.variant("fees", sp.nat(61))]).run(sender = admin, valid = False, exception = "FEE_ERROR")
    world.update_settings([sp.variant("fees", sp.nat(55))]).run(sender = admin)
    scenario.verify(world.data.fees == 55)
    world.update_settings([sp.variant("fees", sp.nat(25))]).run(sender = admin)

    scenario.h3("update metadata")
    scenario.verify(world.data.metadata.get("") == sp.utils.bytes_of_string("https://example.com"))
    world.update_settings([sp.variant("metadata", sp.utils.metadata_of_url("https://elpmaxe.com"))]).run(sender = bob, valid = False)
    world.update_settings([sp.variant("metadata", sp.utils.metadata_of_url("https://elpmaxe.com"))]).run(sender = admin)
    scenario.verify(world.data.metadata.get("") == sp.utils.bytes_of_string("https://elpmaxe.com"))
    world.update_settings([sp.variant("metadata", sp.utils.metadata_of_url("https://example.com"))]).run(sender = admin)

    # NOTE: paused is tested elsewhere

    scenario.h2("Limits")

    scenario.h3("chunk item limit on place_items")
    world.set_allowed_place_token(sp.list([sp.variant("add", sp.record(fa2 = places_tokens.address, place_limits = sp.record(chunk_limit = 1, chunk_item_limit = 10)))])).run(sender = admin)
    place_items(place_alice, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False)),
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False)),
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False)),
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False)),
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False)),
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False)),
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False)),
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False)),
        sp.variant("item", sp.record(amount = 1, token_id = item_alice, rate = sp.tez(1), data = position, primary = False))
    ]}}}, sender=alice, valid=False, message='CHUNK_ITEM_LIMIT')

    #
    # Test FA2 registry related stuff
    #
    scenario.h2("FA2 registry")

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

    scenario.h3("Private collection mint and operator")
    minter.mint_private(
        collection=dyn_collection_token.address,
        to_=alice.address,
        amount=50,
        metadata=sp.utils.bytes_of_string("ipfs://Qtesttesttest"),
        royalties=[ sp.record(address=carol.address, share=sp.nat(250)) ]
    ).run(sender = admin)

    dyn_collection_token.call("update_operators", [
        sp.variant("add_operator", sp.record(
            owner = alice.address,
            operator = world.address,
            token_id = 0
        ))
    ]).run(sender = alice, valid = True)

    # test unpermitted place_item
    # TODO: other type item tests are a bit broken because all kinds of reasons...
    scenario.h3("Test placing/removing/getting unregistered non-tz1and FA2s")
    place_items(place_alice, {0: {False: {other_token.address: [
        sp.variant("item", sp.record(token_id = 0, amount=1, rate=sp.tez(0), data = position, primary = False))
    ]}}}, sender=alice, valid=False, message="TOKEN_NOT_REGISTERED")

    # TODO: test with registry merkle root.

    # test place_item
    scenario.h3("Test placing/removing/getting registered tz1and collection FA2s")

    # TODO:
    scenario.h4("place")
    place_items(place_alice, {0: {False: {dyn_collection_token.address: [
        sp.variant("item", sp.record(token_id = 0, amount=1, rate=sp.tez(0), data = position, primary = False)),
        sp.variant("item", sp.record(token_id = 0, amount=1, rate=sp.tez(0), data = position, primary = False))
    ]}}}, sender=alice)

    # If a token is registered, you can place as many as you want and also swap them.
    place_items(place_alice, {0: {False: {dyn_collection_token.address: [
        sp.variant("item", sp.record(token_id = 0, amount=2, rate=sp.tez(0), data = position, primary = False)),
    ]}}}, sender=alice, valid=True)

    place_items(place_alice, {0: {False: {dyn_collection_token.address: [
        sp.variant("item", sp.record(token_id = 0, amount=1, rate=sp.tez(1), data = position, primary = False)),
    ]}}}, sender=alice, valid=True)

    place_items(place_alice, {0: {False: {dyn_collection_token.address: [
        sp.variant("item", sp.record(token_id = 0, amount=22, rate=sp.tez(1), data = position, primary = False)),
    ]}}}, sender=alice, valid=True)

    scenario.h4("get")
    item_counter = scenario.compute(world.data.chunks.get(place_alice_chunk_0).next_id)
    get_item(place_alice_chunk_0, sp.as_nat(item_counter - 1), sp.some(alice.address), dyn_collection_token.address, sender=bob, amount=sp.tez(1))
    get_item(place_alice_chunk_0, sp.as_nat(item_counter - 4), sp.some(alice.address), dyn_collection_token.address, sender=bob, amount=sp.tez(1), valid=False, message="NOT_FOR_SALE")
    get_item(place_alice_chunk_0, sp.as_nat(item_counter - 5), sp.some(alice.address), dyn_collection_token.address, sender=bob, amount=sp.tez(1), valid=False, message="NOT_FOR_SALE")

    scenario.h4("remove")
    remove_items(place_alice, {0: {sp.some(alice.address): {dyn_collection_token.address: [
        sp.as_nat(item_counter - 1),
        sp.as_nat(item_counter - 2),
        sp.as_nat(item_counter - 3),
        sp.as_nat(item_counter - 4),
        sp.as_nat(item_counter - 5)
    ]}}}, sender=alice)

    #
    # test world permissions
    #
    scenario.h2("World permissions")

    # bob place multiple items for testing removals
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount = 1, token_id = item_bob, rate = sp.tez(1), data = position, primary = False)),
        sp.variant("item", sp.record(amount = 1, token_id = item_bob, rate = sp.tez(1), data = position, primary = False)),
        sp.variant("item", sp.record(amount = 1, token_id = item_bob, rate = sp.tez(1), data = position, primary = False))
    ]}}}, bob)

    # Remember the item ids
    remove_bobs_item1 = scenario.compute(sp.as_nat(world.data.chunks[place_bob_chunk_0].next_id - 1))
    remove_bobs_item2 = scenario.compute(sp.as_nat(world.data.chunks[place_bob_chunk_0].next_id - 2))
    remove_bobs_item3 = scenario.compute(sp.as_nat(world.data.chunks[place_bob_chunk_0].next_id - 3))

    scenario.h3("Change place without perms")
    # alice tries to place an item in bobs place but isn't an op
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount=2, token_id=item_alice, rate=sp.tez(1), data=position, primary = False))
    ]}}}, sender=alice, valid=False, message="NO_PERMISSION")

    scenario.verify(world.get_permissions(sp.record(place_key=place_bob, permittee=alice.address)) == places_contract.permissionNone)

    # alice tries to set place props in bobs place but isn't an op
    world.update_place_props(place_key=place_bob, updates=valid_place_props, ext = sp.none).run(sender=alice, valid=False, exception="NO_PERMISSION")

    # alice tries to remove an item but has no permission
    remove_items(place_bob, {0: {
        sp.some(bob.address): {items_tokens.address: [remove_bobs_item1]}
    }}, sender=alice, valid=False, message="NO_PERMISSION")

    scenario.h3("Permissions")

    #
    #
    #
    scenario.h4("Full permissions")
    # bob gives alice permission to his place
    world.set_permissions([
        sp.variant("add", PermissionParams.make_add(
            owner = bob.address,
            permittee = alice.address,
            place_key = place_bob,
            perm = places_contract.permissionFull
        ))
    ]).run(sender=bob, valid=True)

    # alice can now place/remove items in bobs place, set props and set item data
    scenario.verify(world.get_permissions(sp.record(place_key=place_bob, permittee=alice.address)) == places_contract.permissionFull)

    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount=2, token_id=item_alice, rate=sp.tez(1), data=position, primary = False))
    ]}}}, sender=alice, valid=True)

    # verify issuer is set correctly.
    last_item = scenario.compute(sp.as_nat(world.data.chunks[place_bob_chunk_0].next_id - 1))
    scenario.verify(~sp.is_failing(world.data.chunks[place_bob_chunk_0].storage[sp.some(alice.address)][items_tokens.address][last_item]))

    world.set_item_data(place_key = place_bob, ext = sp.none, update_map = {0: {sp.some(alice.address): {items_tokens.address: [
        sp.record(item_id = last_item, data = new_item_data)
    ]}}} ).run(sender = alice, valid = True)

    scenario.verify(world.data.chunks[place_bob_chunk_0].storage[sp.some(alice.address)][items_tokens.address][last_item].open_variant('item').data == new_item_data)

    world.update_place_props(place_key=place_bob, updates=valid_place_props, ext = sp.none).run(sender=alice, valid=True)

    # remove placed item and one of bobs
    remove_items(place_bob, {0: {
        sp.some(alice.address): {items_tokens.address: [last_item]},
        sp.some(bob.address): {items_tokens.address: [remove_bobs_item1]}
    }}, sender=alice, valid=True)

    #
    #
    #
    scenario.h4("PlaceItems permissions")
    # bob gives alice place item permission to his place
    world.set_permissions([
        sp.variant("add", PermissionParams.make_add(
            owner = bob.address,
            permittee = alice.address,
            place_key = place_bob,
            perm = places_contract.permissionPlaceItems
        ))
    ]).run(sender=bob, valid=True)
    
    # alice can now place items in bobs place, but can't set props or remove bobs items
    scenario.verify(world.get_permissions(sp.record(place_key=place_bob, permittee=alice.address)) == places_contract.permissionPlaceItems)
    
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount=2, token_id=item_alice, rate=sp.tez(1), data=position, primary = False))
    ]}}}, sender=alice, valid=True)

    # verify issuer is set correctly.
    last_item = scenario.compute(sp.as_nat(world.data.chunks[place_bob_chunk_0].next_id - 1))
    scenario.verify(~sp.is_failing(world.data.chunks[place_bob_chunk_0].storage[sp.some(alice.address)][items_tokens.address][last_item]))

    # can modify own items
    world.set_item_data(place_key = place_bob, ext = sp.none, update_map = {0: {sp.some(alice.address): {items_tokens.address: [
        sp.record(item_id = last_item, data = new_item_data)
    ]}}} ).run(sender=alice, valid=True)

    # can't set props
    world.update_place_props(place_key=place_bob, updates=valid_place_props, ext = sp.none).run(sender=alice, valid=False, exception="NO_PERMISSION")

    # can remove own items
    remove_items(place_bob, {0: {sp.some(alice.address): {items_tokens.address: [last_item]}}}, sender=alice, valid=True)
    # can't remove others items
    remove_items(place_bob, {0: {sp.some(bob.address): {items_tokens.address: [remove_bobs_item2]}}}, sender=alice, valid=False, message="NO_PERMISSION")

    #
    #
    #
    scenario.h4("ModifyAll permissions")
    # add an item with place permisssions to test
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount=2, token_id=item_alice, rate=sp.tez(1), data=position, primary = False))
    ]}}}, sender=alice, valid=True)

    # bob gives alice place item permission to his place
    world.set_permissions([
        sp.variant("add", PermissionParams.make_add(
            owner = bob.address,
            permittee = alice.address,
            place_key = place_bob,
            perm = places_contract.permissionModifyAll
        ))
    ]).run(sender=bob, valid=True)
    
    # alice can now modify items in bobs place, but can't set props or place or remove bobs items
    scenario.verify(world.get_permissions(sp.record(place_key=place_bob, permittee=alice.address)) == places_contract.permissionModifyAll)
    
    # can't place items
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount=2, token_id=item_alice, rate=sp.tez(1), data=position, primary = False))
    ]}}}, sender=alice, valid=False, message="NO_PERMISSION")

    last_item = scenario.compute(sp.as_nat(world.data.chunks[place_bob_chunk_0].next_id - 1))

    # can modify all items
    world.set_item_data(place_key = place_bob, ext = sp.none, update_map = {0: {sp.some(bob.address): {items_tokens.address: [
        sp.record(item_id = remove_bobs_item2, data = new_item_data)
    ]}}} ).run(sender=alice, valid=True)

    # can't set props
    world.update_place_props(place_key=place_bob, ext = sp.none, updates=valid_place_props).run(sender=alice, valid=False, exception="NO_PERMISSION")

    # can remove own items and bobs items
    remove_items(place_bob, {0: {
        sp.some(alice.address): {items_tokens.address: [last_item]},
        sp.some(bob.address): {items_tokens.address: [remove_bobs_item2]}
    }}, sender=alice, valid=True)

    #
    #
    #
    scenario.h4("Props permissions")
    # bob gives alice place item permission to his place
    world.set_permissions([
        sp.variant("add", PermissionParams.make_add(
            owner = bob.address,
            permittee = alice.address,
            place_key = place_bob,
            perm = places_contract.permissionProps
        ))
    ]).run(sender=bob, valid=True)
    
    # alice can now modify items in bobs place, but can't set props or place or remove bobs items
    scenario.verify(world.get_permissions(sp.record(place_key=place_bob, permittee=alice.address)) == places_contract.permissionProps)
    
    # can't place items
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount=2, token_id=item_alice, rate=sp.tez(1), data=position, primary = False))
    ]}}}, sender=alice, valid=False, message="NO_PERMISSION")

    last_item = scenario.compute(sp.as_nat(world.data.chunks[place_bob_chunk_0].next_id - 1))

    # can't modify all items
    world.set_item_data(place_key = place_bob, ext = sp.none, update_map = {0: {sp.some(bob.address): {items_tokens.address: [
        sp.record(item_id = remove_bobs_item3, data = new_item_data)
    ]}}} ).run(sender=alice, valid=False, exception="NO_PERMISSION")

    # can't set props
    world.update_place_props(place_key=place_bob, updates=valid_place_props, ext = sp.none).run(sender=alice, valid=True)

    # can remove own items. no need to test that again...
    #remove_items(place_bob, {0: {sp.some(alice.address): {items_tokens.address: [last_item]}}}, sender=alice, valid=True)
    # can't remove others items
    remove_items(place_bob, {0: {sp.some(bob.address): {items_tokens.address: [remove_bobs_item3]}}}, sender=alice, valid=False, message="NO_PERMISSION")

    #
    #
    #
    scenario.h4("Mixed permissions")
    # bob gives alice place item permission to his place
    world.set_permissions([
        sp.variant("add", PermissionParams.make_add(
            owner = bob.address,
            permittee = alice.address,
            place_key = place_bob,
            perm = places_contract.permissionPlaceItems | places_contract.permissionProps
        ))
    ]).run(sender=bob, valid=True)
    
    # alice can now modify items in bobs place, and can place items, but can't set props
    scenario.verify(world.get_permissions(sp.record(place_key=place_bob, permittee=alice.address)) == places_contract.permissionPlaceItems | places_contract.permissionProps)
    
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount=2, token_id=item_alice, rate=sp.tez(1), data=position, primary = False))
    ]}}}, sender=alice, valid=True)

    last_item = scenario.compute(sp.as_nat(world.data.chunks[place_bob_chunk_0].next_id - 1))

    # can't modify all items
    world.set_item_data(place_key = place_bob, ext = sp.none, update_map = {0: {sp.some(bob.address): {items_tokens.address: [
        sp.record(item_id = remove_bobs_item3, data = new_item_data)
    ]}}} ).run(sender=alice, valid=False, exception="NO_PERMISSION")

    world.update_place_props(place_key=place_bob, updates=valid_place_props, ext = sp.none).run(sender=alice, valid=True)

    # Can of course remove own items
    remove_items(place_bob, {0: {sp.some(alice.address): {items_tokens.address: [last_item]}}}, sender=alice, valid=True)
    # can't remove others items
    remove_items(place_bob, {0: {sp.some(bob.address): {items_tokens.address: [remove_bobs_item3]}}}, sender=alice, valid=False, message="NO_PERMISSION")

    scenario.h4("Invalid add permission")
    # incorrect perm parameter
    world.set_permissions([
        sp.variant("add", PermissionParams.make_add(
            owner = bob.address,
            permittee = alice.address,
            place_key = place_bob,
            perm = world.data.max_permission + 1
        ))
    ]).run(sender=bob, valid=False, exception="PARAM_ERROR")

    # giving no permissions is invalid. use remove
    world.set_permissions([
        sp.variant("add", PermissionParams.make_add(
            owner = bob.address,
            permittee = alice.address,
            place_key = place_bob,
            perm = places_contract.permissionNone
        ))
    ]).run(sender=bob, valid=False, exception="PARAM_ERROR")

    # bob gives himself permissions to alices place
    world.set_permissions([
        sp.variant("add", PermissionParams.make_add(
            owner = alice.address,
            permittee = bob.address,
            place_key = place_alice,
            perm = places_contract.permissionFull
        ))
    ]).run(sender=bob, valid=False, exception="NOT_OWNER")

    scenario.verify(world.get_permissions(sp.record(place_key=place_alice, permittee=bob.address)) == places_contract.permissionNone)

    # bob is not allowed to place items in alices place.
    place_items(place_alice, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount=1, token_id=item_bob, rate=sp.tez(1), data=position, primary = False))
    ]}}}, sender=bob, valid=False, message="NO_PERMISSION")

    scenario.h3("No permission after transfer")
    # bob transfers his place to carol
    places_tokens.transfer([
        sp.record(
            from_=bob.address,
            txs=[sp.record(to_=carol.address, amount=1, token_id=place_bob.id)],
        )
    ]).run(sender=bob)

    # alice won't have permission anymore
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount=2, token_id=item_alice, rate=sp.tez(1), data=position, primary = False))
    ]}}}, sender=alice, valid=False, message="NO_PERMISSION")

    scenario.verify(world.get_permissions(sp.record(place_key=place_bob, permittee=alice.address)) == places_contract.permissionNone)

    # and also alice will not have persmissions on carols place
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount=2, token_id=item_alice, rate=sp.tez(1), data=position, primary = False))
    ]}}}, sender=alice, valid=False, message="NO_PERMISSION")

    scenario.verify(world.get_permissions(sp.record(place_key=place_bob, permittee=alice.address)) == places_contract.permissionNone)

    # neither will bob
    place_items(place_bob, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount=1, token_id=item_bob, rate=sp.tez(1), data=position, primary = False))
    ]}}}, sender=bob, valid=False, message="NO_PERMISSION")

    scenario.verify(world.get_permissions(sp.record(place_key=place_bob, permittee=bob.address)) == places_contract.permissionNone)

    scenario.h3("Invalid remove permission")
    # alice cant remove own permission to bobs (now not owned) place
    world.set_permissions([
        sp.variant("remove", PermissionParams.make_remove(
            owner = bob.address,
            permittee = alice.address,
            place_key = place_bob,
        ))
    ]).run(sender=alice, valid=False, exception="NOT_OWNER")

    scenario.h3("Valid remove permission")
    # bob removes alice's permissions to his (now not owned) place
    world.set_permissions([
        sp.variant("remove", PermissionParams.make_remove(
            owner = bob.address,
            permittee = alice.address,
            place_key = place_bob,
        ))
    ]).run(sender=bob, valid=True)

    scenario.verify(world.get_permissions(sp.record(place_key=place_bob, permittee=alice.address)) == places_contract.permissionNone)

    #
    # test some swapping edge cases
    #
    scenario.h2("place/get item edge cases")

    # place item for 1 mutez
    place_items(place_alice, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount=1, token_id=item_alice, rate=sp.mutez(1), data=position, primary = False))
    ]}}}, sender=alice, valid=True)

    # try to get it
    item_counter = world.data.chunks.get(place_alice_chunk_0).next_id
    get_item(place_alice_chunk_0, sp.as_nat(item_counter - 1), sp.some(alice.address), items_tokens.address, sender=bob, amount=sp.mutez(1), valid=True)

    #
    # test paused
    #
    scenario.h2("pausing")
    scenario.verify(world.data.paused == False)
    world.update_settings([sp.variant("paused", True)]).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    world.update_settings([sp.variant("paused", True)]).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    world.update_settings([sp.variant("paused", True)]).run(sender = admin)
    scenario.verify(world.data.paused == True)

    # anything that changes a place or transfers tokens is now disabled
    world.update_place_props(place_key=place_bob, updates=valid_place_props, ext = sp.none).run(sender=carol, valid = False, exception = "ONLY_UNPAUSED")

    place_items(place_alice, {0: {False: {items_tokens.address: [
        sp.variant("item", sp.record(amount=1, token_id=item_alice, rate=sp.tez(1), data=position, primary = False))
    ]}}}, sender=alice, valid=False, message="ONLY_UNPAUSED")

    get_item(place_alice_chunk_0, 3, sp.some(alice.address), items_tokens.address, sender=bob, amount=sp.mutez(1), valid=False, message="ONLY_UNPAUSED")

    remove_items(place_alice, {0: {sp.some(alice.address): {items_tokens.address: [3]}}}, sender=alice, valid=False, message="ONLY_UNPAUSED")

    # update permissions is still allowed
    world.set_permissions([
        sp.variant("remove", PermissionParams.make_remove(
            owner = bob.address,
            permittee = alice.address,
            place_key = place_bob,
        ))
    ]).run(sender=bob, valid=True)

    world.update_settings([sp.variant("paused", False)]).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    world.update_settings([sp.variant("paused", False)]).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    world.update_settings([sp.variant("paused", False)]).run(sender = admin)
    scenario.verify(world.data.paused == False)

    world.update_place_props(place_key=place_bob, updates=valid_place_props, ext = sp.none).run(sender=carol)

    #
    # Test migration
    #
    scenario.h2("migration")

    # Set migration contract to be admin address.
    world.update_settings([sp.variant("migration_from", sp.some(admin.address))]).run(sender = admin)
    world.set_allowed_place_token(sp.list([sp.variant("add", sp.record(fa2 = places_tokens.address, place_limits = sp.record(chunk_limit = 2, chunk_item_limit = 4)))])).run(sender = admin)

    # Invalid migration - place not not empty.
    world.migration(
        place_key=place_bob,
        # For migration from v1 we basically need the same data as a chunk but with a list as the leaf.
        item_map = {
            carol.address: {
                items_tokens.address: [
                    sp.variant("item", sp.record(amount = 1, token_id = item_admin, rate = sp.tez(1), data = position, primary = False)) for n in range(8)
                ]
            }
        },
        props = {sp.bytes("0x00"): sp.bytes("0xaaaaaa")},
        ext = sp.none
    ).run(sender=admin, valid=False, exception="MIGRATION_PLACE_NOT_EMPTY")

    # Invalid migration - chunk limit.
    world.migration(
        place_key=place_carol,
        # For migration from v1 we basically need the same data as a chunk but with a list as the leaf.
        item_map = {
            carol.address: {
                items_tokens.address: [
                    sp.variant("item", sp.record(amount = 1, token_id = item_admin, rate = sp.tez(1), data = position, primary = False)) for n in range(9)
                ]
            }
        },
        props = {sp.bytes("0x00"): sp.bytes("0xaaaaaa")},
        ext = sp.none
    ).run(sender=admin, valid=False, exception="CHUNK_LIMIT")

    # Valid migration.
    world.migration(
        place_key=place_carol,
        # For migration from v1 we basically need the same data as a chunk but with a list as the leaf.
        item_map = {
            carol.address: {
                items_tokens.address: [
                    sp.variant("item", sp.record(amount = 1, token_id = item_admin, rate = sp.tez(1), data = position, primary = False)) for n in range(2)
                ]
            },
            alice.address: {
                items_tokens.address: [
                    sp.variant("item", sp.record(amount = 1, token_id = item_admin, rate = sp.tez(1), data = position, primary = False)) for n in range(3)
                ]
            },
            bob.address: {
                items_tokens.address: [
                    sp.variant("item", sp.record(amount = 1, token_id = item_admin, rate = sp.tez(1), data = position, primary = False)) for n in range(2)
                ]
            },
            admin.address: {
                items_tokens.address: [
                    sp.variant("item", sp.record(amount = 1, token_id = item_admin, rate = sp.tez(1), data = position, primary = False)) for n in range(1)
                ]
            }
        },
        props = {sp.bytes("0x00"): sp.bytes("0xaaaaaa")},
        ext = sp.none
    ).run(sender=admin)

    # Make sure we have n chunks an all the items, somehow.
    scenario.verify(sp.len(world.data.places.get(place_carol).chunks) == 2)
    scenario.verify(world.data.places.get(place_carol).chunks.contains(0))
    scenario.verify(world.data.places.get(place_carol).chunks.contains(1))
    # Check chunk 0 contents
    scenario.verify(world.data.chunks.contains(place_carol_chunk_0))
    scenario.verify(world.data.chunks[place_carol_chunk_0].storage.contains(sp.some(bob.address)))
    scenario.verify(world.data.chunks[place_carol_chunk_0].storage.contains(sp.some(carol.address)))
    scenario.verify(~world.data.chunks[place_carol_chunk_0].storage.contains(sp.some(alice.address)))
    scenario.verify(~world.data.chunks[place_carol_chunk_0].storage.contains(sp.some(admin.address)))

    # Check chunk 1 contents
    scenario.verify(world.data.chunks.contains(place_carol_chunk_1))
    scenario.verify(~world.data.chunks[place_carol_chunk_1].storage.contains(sp.some(bob.address)))
    scenario.verify(~world.data.chunks[place_carol_chunk_1].storage.contains(sp.some(carol.address)))
    scenario.verify(world.data.chunks[place_carol_chunk_1].storage.contains(sp.some(alice.address)))
    scenario.verify(world.data.chunks[place_carol_chunk_1].storage.contains(sp.some(admin.address)))

    scenario.h3("tokens in storage after migration")
    # NOTE: Migration ep doesn't actually transfer tokens. It's expected the other side does it.
    token_amounts = scenario.compute(items_utils.all_token_amounts_in_storage(
        sp.record(world = world.address, place_key = place_carol_chunk_0.place_key, chunk_ids = sp.set([place_carol_chunk_0.chunk_id, place_carol_chunk_1.chunk_id]))))
    scenario.show(token_amounts)

    scenario.verify(sp.len(token_amounts) == 4)
    scenario.verify(token_amounts[sp.record(fa2 = items_tokens.address, token_id = item_admin, owner = sp.some(admin.address))] == 1)
    scenario.verify(token_amounts[sp.record(fa2 = items_tokens.address, token_id = item_admin, owner = sp.some(bob.address))] == 2)
    scenario.verify(token_amounts[sp.record(fa2 = items_tokens.address, token_id = item_admin, owner = sp.some(alice.address))] == 3)
    scenario.verify(token_amounts[sp.record(fa2 = items_tokens.address, token_id = item_admin, owner = sp.some(carol.address))] == 2)


    #
    # the end.
    scenario.table_of_contents()
