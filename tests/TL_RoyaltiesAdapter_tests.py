import smartpy as sp

token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
legacy_royalties_contract = sp.io.import_script_from_url("file:contracts/TL_LegacyRoyalties.py")
royalties_adapter_contract = sp.io.import_script_from_url("file:contracts/TL_RoyaltiesAdapter.py")
admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")


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
    registry = token_registry_contract.TL_TokenRegistry(admin.address, collections_key.public_key,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += registry

    scenario.h2("LegacyRoyalties")
    legacy_royalties = legacy_royalties_contract.TL_LegacyRoyalties(admin.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += legacy_royalties

    scenario.h1("Test RoyaltiesAdapter")
    royalties_adapter = royalties_adapter_contract.TL_RoyaltiesAdapter(
        registry.address, legacy_royalties.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += royalties_adapter

    raise Exception("NO TESTS IMPLEMENTED")