import smartpy as sp

from contracts import TL_Marketplace, TL_Minter_v2, TL_TokenFactory, TL_TokenRegistry, TL_LegacyRoyalties, TL_RoyaltiesAdapter, TL_RoyaltiesAdapterLegacyAndV1, TL_Blacklist, Tokens
from contracts.utils import ErrorMessages, FA2Utils


@sp.add_test(name = "TL_Marketplace_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    carol = sp.test_account("Carol")
    royalties_key = sp.test_account("Royalties")
    collections_key = sp.test_account("Collections")
    scenario = sp.test_scenario()

    scenario.h1("Swap and collect marketplace contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob, carol])

    # create a FA2 and minter contract for testing
    scenario.h2("Create test env")

    scenario.h3("Tokens")
    items_tokens = Tokens.tz1andItems_v2(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    other_tokens = Tokens.tz1andItems_v2(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += other_tokens

    scenario.h3("TokenRegistry")
    registry = TL_TokenRegistry.TL_TokenRegistry(admin.address, collections_key.public_key,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += registry

    scenario.h3("LegacyRoyalties")
    legacy_royalties = TL_LegacyRoyalties.TL_LegacyRoyalties(admin.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += legacy_royalties

    scenario.h3("RoyaltiesAdapters")
    royalties_adapter_legacy = TL_RoyaltiesAdapterLegacyAndV1.TL_RoyaltiesAdapterLegacyAndV1(
        legacy_royalties.address)
    scenario += royalties_adapter_legacy

    royalties_adapter = TL_RoyaltiesAdapter.TL_RoyaltiesAdapter(
        registry.address, royalties_adapter_legacy.address)
    scenario += royalties_adapter

    scenario.h3("Minter v2")
    minter = TL_Minter_v2.TL_Minter_v2(admin.address, registry.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    scenario.h3("Blacklist")
    blacklist = TL_Blacklist.TL_Blacklist(admin.address)
    scenario += blacklist

    scenario.h3("ItemCollectionProxyParent")
    collection_proxy_parent = Tokens.ItemCollectionProxyParent(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address, blacklist = blacklist.address, parent = admin.address)
    scenario += collection_proxy_parent

    scenario.h3("TokenFactory")
    token_factory = TL_TokenFactory.TL_TokenFactory(admin.address, registry.address, minter.address,
        blacklist = blacklist.address, proxy_parent = collection_proxy_parent.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += token_factory
    scenario.register(token_factory.collection_contract)

    scenario.h3("registry permissions for factory, etc")
    registry.manage_permissions([sp.variant("add_permissions", sp.set([token_factory.address]))]).run(sender=admin)
    registry.manage_collections([sp.variant("add_public", {items_tokens.address: TL_TokenRegistry.royaltiesTz1andV2})]).run(sender = admin)

    items_tokens.transfer_administrator(minter.address).run(sender = admin)
    minter.token_administration([
        sp.variant("accept_fa2_administrator", sp.set([items_tokens.address]))
    ]).run(sender = admin)

    # mint some item tokens for testing
    scenario.h3("mint some native tokens for testing")
    minter.mint_public(sp.record(
        collection = items_tokens.address,
        to_ = bob.address,
        amount = 4,
        metadata = sp.utils.bytes_of_string("test_metadata"),
        royalties = {bob.address: 250}
    )).run(sender = bob)

    minter.mint_public(sp.record(
        collection = items_tokens.address,
        to_ = alice.address,
        amount = 4,
        metadata = sp.utils.bytes_of_string("test_metadata"),
        royalties = {alice.address: 250}
    )).run(sender = alice)

    item_bob = sp.nat(0)
    item_alice = sp.nat(1)

    scenario.h3("mint some non-native tokens for testing")
    other_tokens.mint([
        sp.record(
            to_ = bob.address,
            amount = 4,
            token = sp.variant("new", sp.record(
                metadata = {"": sp.utils.bytes_of_string("test_metadata")},
                royalties = {bob.address: 250}))
        ),
        sp.record(
            to_ = alice.address,
            amount = 4,
            token = sp.variant("new", sp.record(
                metadata = {"": sp.utils.bytes_of_string("test_metadata")},
                royalties = {alice.address: 250}))
        )
    ]).run(sender = admin)

    other_token_bob = sp.nat(0)
    other_token_alice = sp.nat(0)

    scenario.h2("Test Marketplace")

    # create places contract
    scenario.h3("Originate Marketplace contract")
    marketplace = TL_Marketplace.TL_Marketplace(admin.address, registry.address, royalties_adapter.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += marketplace

    #
    # Test swap
    scenario.h4("test swap")

    # Not operator
    marketplace.swap(sp.record(
        swap_key_partial = sp.record(
            fa2 = items_tokens.address,
            token_id = item_bob,
            rate = sp.tez(100),
            primary = False),
        token_amount = 2,
        ext = sp.none)).run(sender = bob, valid = False, exception = "FA2_NOT_OPERATOR")

    scenario.h4("set opertors")
    for collection in [items_tokens, other_tokens]:
        for sender in [bob, alice]:
            collection.update_operators([
                sp.variant("add_operator", sp.record(
                    owner = sender.address,
                    operator = marketplace.address,
                    token_id = item_bob
                )),
                sp.variant("add_operator", sp.record(
                    owner = sender.address,
                    operator = marketplace.address,
                    token_id = item_alice
                ))
            ]).run(sender = sender)

    # No balance.
    marketplace.swap(sp.record(
        swap_key_partial = sp.record(
            fa2 = items_tokens.address,
            token_id = item_bob,
            rate = sp.tez(100),
            primary = False),
        token_amount = 1,
        ext = sp.none)).run(sender = alice, valid = False, exception = "FA2_INSUFFICIENT_BALANCE")

    # Wrong token_amount
    marketplace.swap(sp.record(
        swap_key_partial = sp.record(
            fa2 = items_tokens.address,
            token_id = item_bob,
            rate = sp.tez(100),
            primary = False),
        token_amount = 0,
        ext = sp.none)).run(sender = bob, valid = False, exception = "INVALID_PARAM")

    # Not registered
    marketplace.swap(sp.record(
        swap_key_partial = sp.record(
            fa2 = other_tokens.address,
            token_id = other_token_bob,
            rate = sp.tez(100),
            primary = False),
        token_amount = 3,
        ext = sp.none)).run(sender = bob, valid = False, exception = "TOKEN_NOT_REGISTERED")

    # Valid
    swap_key_bob_item_bob = sp.record(
        id = 0,
        owner = bob.address,
        partial = sp.record(
            fa2 = items_tokens.address,
            token_id = item_bob,
            rate = sp.tez(100),
            primary = False))

    marketplace.swap(sp.record(
        swap_key_partial = swap_key_bob_item_bob.partial,
        token_amount = 2,
        ext = sp.none)).run(sender = bob)

    # check balance
    scenario.verify(FA2Utils.fa2_get_balance(items_tokens.address, item_bob, bob.address) == 2)
    scenario.verify(FA2Utils.fa2_get_balance(items_tokens.address, item_bob, marketplace.address) == 2)

    # check view
    scenario.verify(marketplace.get_swap(swap_key_bob_item_bob).token_amount == 2)

    # Valid
    swap_key_alice_item_alice = sp.record(
        id = 1,
        owner = alice.address,
        partial = sp.record(
            fa2 = items_tokens.address,
            token_id = item_alice,
            rate = sp.tez(100),
            primary = False))

    marketplace.swap(sp.record(
        swap_key_partial = swap_key_alice_item_alice.partial,
        token_amount = 2,
        ext = sp.none)).run(sender = alice)

    # check balance
    scenario.verify(FA2Utils.fa2_get_balance(items_tokens.address, item_alice, alice.address) == 2)
    scenario.verify(FA2Utils.fa2_get_balance(items_tokens.address, item_alice, marketplace.address) == 2)

    # check view
    scenario.verify(marketplace.get_swap(swap_key_alice_item_alice).token_amount == 2)

    #
    # Test collect
    scenario.h4("test collect")

    # Wrong amount
    marketplace.collect(sp.record(
        swap_key = swap_key_alice_item_alice,
        ext = sp.none)).run(sender = bob, amount = sp.tez(3), valid = False, exception = "WRONG_AMOUNT")

    # Invalid swap key
    marketplace.collect(sp.record(
        swap_key = sp.record(
            id = 15,
            owner = admin.address,
            partial = sp.record(
                fa2 = carol.address,
                token_id = other_token_bob,
                rate = sp.tez(12),
                primary = True)),
        ext = sp.none)).run(sender = alice, amount = sp.tez(12), valid = False, exception = "INVALID_SWAP")

    # Valid
    marketplace.collect(sp.record(
        swap_key = swap_key_bob_item_bob,
        ext = sp.none)).run(sender = alice, amount = sp.tez(100))

    scenario.verify(marketplace.data.swaps[swap_key_bob_item_bob].token_amount == 1)

    # Check balance
    scenario.verify(FA2Utils.fa2_get_balance(items_tokens.address, item_bob, alice.address) == 1)
    scenario.verify(FA2Utils.fa2_get_balance(items_tokens.address, item_bob, marketplace.address) == 1)
    scenario.verify(FA2Utils.fa2_get_balance(items_tokens.address, item_bob, bob.address) == 2)

    # Valid
    marketplace.collect(sp.record(
        swap_key = swap_key_alice_item_alice,
        ext = sp.none)).run(sender = bob, amount = sp.tez(100))

    scenario.verify(marketplace.data.swaps[swap_key_alice_item_alice].token_amount == 1)

    # Check balance
    scenario.verify(FA2Utils.fa2_get_balance(items_tokens.address, item_alice, bob.address) == 1)
    scenario.verify(FA2Utils.fa2_get_balance(items_tokens.address, item_alice, marketplace.address) == 1)
    scenario.verify(FA2Utils.fa2_get_balance(items_tokens.address, item_alice, alice.address) == 2)

    # Valid, removes swap
    marketplace.collect(sp.record(
        swap_key = swap_key_alice_item_alice,
        ext = sp.none)).run(sender = bob, amount = sp.tez(100))

    scenario.verify(~marketplace.data.swaps.contains(swap_key_alice_item_alice))

    # Check balance
    scenario.verify(FA2Utils.fa2_get_balance(items_tokens.address, item_alice, bob.address) == 2)
    scenario.verify(FA2Utils.fa2_get_balance(items_tokens.address, item_alice, alice.address) == 2)

    # check view is failing
    scenario.verify(sp.is_failing(marketplace.get_swap(swap_key_alice_item_alice)))

    #
    # Test cancel

    # Invalid not owner
    marketplace.cancel(sp.record(
        swap_key = swap_key_bob_item_bob,
        ext = sp.none)).run(sender = alice, valid = False, exception = "NOT_OWNER")

    # Invalid swap
    marketplace.cancel(sp.record(
        swap_key = swap_key_alice_item_alice,
        ext = sp.none)).run(sender = alice, valid = False, exception = "INVALID_SWAP")

    # Valid
    marketplace.cancel(sp.record(
        swap_key = swap_key_bob_item_bob,
        ext = sp.none)).run(sender = bob)

    scenario.verify(~marketplace.data.swaps.contains(swap_key_bob_item_bob))

    # Check balance
    scenario.verify(FA2Utils.fa2_get_balance(items_tokens.address, item_bob, alice.address) == 1)
    scenario.verify(FA2Utils.fa2_get_balance(items_tokens.address, item_bob, bob.address) == 3)

    scenario.h4("Settings")

    scenario.h3("update registry")
    scenario.verify(marketplace.data.settings.registry == registry.address)
    marketplace.update_settings([sp.variant("registry", minter.address)]).run(sender = bob, valid = False)
    marketplace.update_settings([sp.variant("registry", bob.address)]).run(sender = admin, valid = False)
    marketplace.update_settings([sp.variant("registry", minter.address)]).run(sender = admin)
    scenario.verify(marketplace.data.settings.registry == minter.address)
    marketplace.update_settings([sp.variant("registry", royalties_adapter.address)]).run(sender = admin)

    scenario.h3("update royalties_adapter")
    scenario.verify(marketplace.data.settings.royalties_adapter == royalties_adapter.address)
    marketplace.update_settings([sp.variant("royalties_adapter", minter.address)]).run(sender = bob, valid = False)
    marketplace.update_settings([sp.variant("royalties_adapter", bob.address)]).run(sender = admin, valid = False)
    marketplace.update_settings([sp.variant("royalties_adapter", minter.address)]).run(sender = admin)
    scenario.verify(marketplace.data.settings.royalties_adapter == minter.address)
    marketplace.update_settings([sp.variant("royalties_adapter", royalties_adapter.address)]).run(sender = admin)

    # TODO: check roaylaties paid, token transferred