import smartpy as sp

minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter.py")
minter_v2_contract = sp.io.import_script_from_url("file:contracts/TL_Minter_v2.py")
token_factory_contract = sp.io.import_script_from_url("file:contracts/TL_TokenFactory.py")
token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
places_contract = sp.io.import_script_from_url("file:contracts/TL_World_v2.py")
world_upgrade = sp.io.import_script_from_url("file:contracts/upgrades/TL_World_v1_1.py")
tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")
fa2_test_lib = sp.io.import_script_from_url("file:tests/lib/FA2_test_lib.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")


@sp.add_test(name = "TL_World_v1_1_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    carol   = sp.test_account("Carol")
    scenario = sp.test_scenario()

    scenario.h1("Fees contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
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
        amount = 64,
        royalties = 250,
        contributors = [ sp.record(address=bob.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    minter.mint_Item(to_ = alice.address,
        amount = 64,
        royalties = 250,
        contributors = [ sp.record(address=alice.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)

    minter.mint_Item(to_ = carol.address,
        amount = 64,
        royalties = 250,
        contributors = [ sp.record(address=alice.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)

    item_bob = sp.nat(0)
    item_alice = sp.nat(1)
    item_carol = sp.nat(2)

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
        ),
        sp.record(
            to_ = carol.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        ),
        sp.record(
            to_ = carol.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        ),
        sp.record(
            to_ = carol.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        ),
        sp.record(
            to_ = alice.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        ),
        sp.record(
            to_ = bob.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        )
    ]).run(sender = admin)

    place_bob = sp.nat(0)
    place_alice = sp.nat(1)
    place_carol = sp.nat(2)
    place_carol_uninit = sp.nat(3)
    place_carol_only_props = sp.nat(4)
    place_alice_emptied = sp.nat(5)
    place_bob_only_ext = sp.nat(6)

    #
    # Originate contract
    #
    scenario.h2("Originate contracts")

    scenario.h3("TokenRegistry")
    token_registry = token_registry_contract.TL_TokenRegistry(admin.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += token_registry

    scenario.h3("Minter v2")
    minter_v2 = minter_v2_contract.TL_Minter(admin.address, token_registry.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter_v2

    scenario.h3("TokenFactory")
    token_factory = token_factory_contract.TL_TokenFactory(admin.address, token_registry.address, minter_v2.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += token_factory
    scenario.register(token_factory.collection_contract)

    scenario.h3("World v2")
    world_v2 = places_contract.TL_World(admin.address, token_registry.address, paused = True,
        metadata = sp.utils.metadata_of_url("https://example.com"), name = "Test World", description = "A world for testing")
    scenario += world_v2

    scenario.h3("Originate World v1 contract")
    world = world_upgrade.TL_World_v1_1(admin.address, items_tokens.address, places_tokens.address, dao_token.address, world_v2.address,
        metadata = sp.utils.metadata_of_url("https://example.com"), name = "Test World", description = "A world for testing")
    scenario += world


    #
    # Prep
    scenario.h3("preparation")

    scenario.h4("set world v1 item limit")
    world.update_item_limit(6).run(sender=admin)

    scenario.h4("registry permissions for factory")
    token_registry.manage_permissions([sp.variant("add_permissions", [token_factory.address])]).run(sender=admin)

    scenario.h4("add public collection")
    token_registry.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = admin)

    scenario.h4("add allowed place token")
    world_v2.set_allowed_place_token(sp.list([sp.variant("add_allowed_place_token", sp.record(fa2 = places_tokens.address, place_limits = sp.record(chunk_limit = 4, chunk_item_limit = 2)))])).run(sender = admin)

    scenario.h4("set migration contract")
    world_v2.update_settings([sp.variant("migration_contract", sp.some(world.address))]).run(sender = admin)

    scenario.h4("set up operators")
    def set_operators(owner, item_ids):
        items_tokens.update_operators([sp.variant("add_operator", sp.record(
            owner = owner.address,
            operator = world.address,
            token_id = item_id
        )) for item_id in item_ids]).run(sender = owner, valid = True)

    item_ids = [item_bob, item_alice, item_carol]
    set_operators(bob, item_ids)
    set_operators(alice, item_ids)
    set_operators(carol, item_ids)


    scenario.h1("Test migration")

    #
    # Test access control.
    scenario.h2("Test access control")
    
    world.set_item_data(
        lot_id = place_carol_only_props,
        owner = sp.none,
        update_map = {},
        extension = sp.none).run(sender=carol, valid=False, exception="ONLY_ADMIN")

    world.set_item_data(
        lot_id = place_carol_only_props,
        owner = sp.none,
        update_map = {},
        extension = sp.none).run(sender=bob, valid=False, exception="ONLY_ADMIN")


    #
    # TODO: test migrating places that:
    scenario.h2("Test migration")
    item_data = sp.bytes("0xFFFFFFFAAFFFFFFFFFFFFCCFFFFFFF")

    # - contain items and ext items
    # - contain multiple types of items
    # - contain only ext items
    place_key = sp.record(place_contract=places_tokens.address, lot_id=place_bob_only_ext)
    chunk_key_0 = sp.record(place_key=place_key, chunk_id=sp.nat(0))
    chunk_key_1 = sp.record(place_key=place_key, chunk_id=sp.nat(1))
    chunk_key_2 = sp.record(place_key=place_key, chunk_id=sp.nat(2))

    world.place_items(
        lot_id = place_bob_only_ext,
        owner = sp.none,
        item_list = [sp.variant("ext", item_data) for x in range(6)],
        extension = sp.none).run(sender=bob)

    world.set_item_data(
        lot_id = place_bob_only_ext,
        owner = sp.none,
        update_map = {},
        extension = sp.none).run(sender=admin)

    # have props and three chunks in v2.
    scenario.verify(world_v2.data.places.contains(place_key))
    scenario.verify(sp.len(world_v2.data.places.get(place_key).chunks) == 3)
    scenario.verify(world_v2.data.chunks.contains(chunk_key_0))
    scenario.verify(world_v2.data.chunks.contains(chunk_key_1))
    scenario.verify(world_v2.data.chunks.contains(chunk_key_2))
    # place deleted in world v1
    scenario.verify(~world.data.places.contains(place_bob_only_ext))


    # - used to contain items but props weren't changed
    scenario.h3("Place that used to contain items but default props")
    place_key = sp.record(place_contract=places_tokens.address, lot_id=place_alice_emptied)
    chunk_key_0 = sp.record(place_key=place_key, chunk_id=sp.nat(0))

    world.place_items(
        lot_id = place_alice_emptied,
        owner = sp.none,
        item_list = [
            sp.variant("item", sp.record(token_amount = 1, token_id = item_alice, mutez_per_token = sp.tez(1), item_data = item_data)),
            sp.variant("ext", item_data)
        ],
        extension = sp.none).run(sender=alice)

    world.remove_items(
        lot_id = place_alice_emptied,
        owner = sp.none,
        remove_map = {alice.address: [ sp.nat(0), sp.nat(1) ]},
        extension = sp.none).run(sender=alice)

    world.set_item_data(
        lot_id = place_alice_emptied,
        owner = sp.none,
        update_map = {},
        extension = sp.none).run(sender=admin)

    # have no props and no chunks in v2
    scenario.verify(~world_v2.data.places.contains(place_key))
    scenario.verify(~world_v2.data.chunks.contains(chunk_key_0))
    # place deleted in world v1
    scenario.verify(~world.data.places.contains(place_alice_emptied))


    # - just have props set
    scenario.h3("Place with only props set")
    place_key = sp.record(place_contract=places_tokens.address, lot_id=place_carol_only_props)
    chunk_key_0 = sp.record(place_key=place_key, chunk_id=sp.nat(0))

    world.set_place_props(
        lot_id = place_carol_only_props,
        owner = sp.none,
        props = {sp.bytes("0x00"): sp.bytes("0xabcdef"), sp.bytes("0x01"): sp.utils.bytes_of_string("place title and stuff")},
        extension = sp.none).run(sender=carol)

    prev_props = scenario.compute(world.data.places.get(place_carol_only_props).place_props)
    
    world.set_item_data(
        lot_id = place_carol_only_props,
        owner = sp.none,
        update_map = {},
        extension = sp.none).run(sender=admin)

    # have props but no chunks in v2
    scenario.verify(world_v2.data.places.contains(place_key))
    scenario.verify(sp.len(world_v2.data.places.get(place_key).chunks) == 0)
    scenario.verify(~world_v2.data.chunks.contains(chunk_key_0))
    # props are what they used to be
    scenario.verify_equal(world_v2.data.places.get(place_key).place_props, prev_props)
    # place deleted in world v1
    scenario.verify(~world.data.places.contains(place_carol_only_props))


    # - never were initialised.
    scenario.h3("Place never initialised")
    place_key = sp.record(place_contract=places_tokens.address, lot_id=place_carol_uninit)
    chunk_key_0 = sp.record(place_key=place_key, chunk_id=sp.nat(0))

    world.set_item_data(
        lot_id = place_carol_uninit,
        owner = sp.none,
        update_map = {},
        extension = sp.none).run(sender=admin)

    # Place shouldn't exist anywhere
    scenario.verify(~world_v2.data.places.contains(place_key))
    scenario.verify(~world_v2.data.chunks.contains(chunk_key_0))
    scenario.verify(~world.data.places.contains(place_carol_uninit))


    scenario.table_of_contents()
