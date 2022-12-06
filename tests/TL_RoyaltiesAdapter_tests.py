import smartpy as sp

from contracts import TL_TokenRegistry, TL_LegacyRoyalties, TL_RoyaltiesAdapter, TL_RoyaltiesAdapterLegacyAndV1, FA2


# TODO: test permissions!!!
# TODO: test removing keys not owned.


@sp.add_test(name = "TL_RoyaltiesAdapter_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    royalties_key = sp.test_account("Royalties")
    collections_key = sp.test_account("Collections")
    scenario = sp.test_scenario()

    scenario.h1("LegacyRoyalties Tests")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h1("Accounts")
    scenario.show([admin, alice, bob, royalties_key, collections_key])

    # create a FA2 contract for testing
    scenario.h1("Create test env")

    scenario.h2("TokenRegistry")
    registry = TL_TokenRegistry.TL_TokenRegistry(admin.address, collections_key.public_key,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += registry

    scenario.h2("LegacyRoyalties")
    legacy_royalties = TL_LegacyRoyalties.TL_LegacyRoyalties(admin.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += legacy_royalties

    scenario.h1("Test RoyaltiesAdapters")
    royalties_adapter_legacy = TL_RoyaltiesAdapterLegacyAndV1.TL_RoyaltiesAdapterLegacyAndV1(
        legacy_royalties.address, metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += royalties_adapter_legacy

    royalties_adapter = TL_RoyaltiesAdapter.TL_RoyaltiesAdapter(
        registry.address, royalties_adapter_legacy.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += royalties_adapter

    raise Exception("NO TESTS IMPLEMENTED")