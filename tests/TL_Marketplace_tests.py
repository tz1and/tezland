import smartpy as sp

from contracts import TL_Marketplace, TL_Minter_v2, TL_TokenFactory, TL_TokenRegistry, TL_LegacyRoyalties, TL_RoyaltiesAdapter, TL_RoyaltiesAdapterLegacyAndV1, TL_Blacklist, Tokens
from contracts.utils import ErrorMessages


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
    #minter.mint_public(collection = items_tokens.address,
    #    to_ = bob.address,
    #    amount = 4,
    #    royalties = [ sp.record(address=bob.address, share=sp.nat(250)) ],
    #    metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    #item_bob = sp.nat(0)

    scenario.h2("Test Marketplace")

    # create places contract
    scenario.h3("Originate Marketplace contract")
    marketplace = TL_Marketplace.TL_Marketplace(admin.address, registry.address, royalties_adapter.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += marketplace

    # TODO: check roaylaties paid, token transferred