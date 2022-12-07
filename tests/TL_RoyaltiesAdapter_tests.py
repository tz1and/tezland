import smartpy as sp

from contracts import TL_TokenRegistry, TL_LegacyRoyalties, TL_RoyaltiesAdapter, TL_RoyaltiesAdapterLegacyAndV1, Tokens


class RoyaltiesAdapterTest(sp.Contract):
    def __init__(self, adapter):
        self.init_storage(adapter = adapter)

    @sp.entry_point
    def testRoyalties(self, token_key, expected):
        sp.set_type(token_key, TL_LegacyRoyalties.t_token_key)
        royalties = sp.compute(TL_RoyaltiesAdapter.getRoyalties(self.data.adapter, token_key).open_some())
        sp.verify_equal(royalties, expected.open_some("unexpected result"))


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

    legacy_royalties.manage_registry([sp.variant("add_keys", {"key": royalties_key.public_key})]).run(sender=admin)

    scenario.h2("tokens")
    items_tokens = Tokens.tz1andItems_v2(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    items_tokens_legacy = Tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens_legacy

    other_token = Tokens.tz1andItems_v2(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += other_token

    scenario.h1("Test RoyaltiesAdapters")
    royalties_adapter_legacy = TL_RoyaltiesAdapterLegacyAndV1.TL_RoyaltiesAdapterLegacyAndV1(
        legacy_royalties.address, metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += royalties_adapter_legacy

    royalties_adapter = TL_RoyaltiesAdapter.TL_RoyaltiesAdapter(
        registry.address, royalties_adapter_legacy.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += royalties_adapter

    adapter_test = RoyaltiesAdapterTest(royalties_adapter.address)
    scenario += adapter_test

    scenario.h2("No collections in registry")

    token_keys = {
        "legacy0": sp.record(fa2=items_tokens_legacy.address, id=0),
        "legacy1": sp.record(fa2=items_tokens_legacy.address, id=1),
        "items0": sp.record(fa2=items_tokens.address, id=0),
        "items1": sp.record(fa2=items_tokens.address, id=1),
        "trusted": sp.record(fa2=other_token.address, id=0)
    }

    # View should fail if not in collections.
    for val in token_keys.values():
        adapter_test.testRoyalties(token_key=val, expected=sp.none).run(sender=admin, valid=False, exception="INVALID_COLLECTION")

    scenario.h2("Add collections to registry")

    signed_collection = TL_TokenRegistry.signCollection(
        sp.record(collection = other_token.address, royalties_type = TL_TokenRegistry.royaltiesLegacy),
        collections_key.secret_key)

    manage_public_params = { items_tokens_legacy.address: TL_TokenRegistry.royaltiesTz1andV1 }
    manage_private_params = { items_tokens.address: sp.record(owner = bob.address, royalties_type = TL_TokenRegistry.royaltiesTz1andV2) }
    manage_trusted_params = { other_token.address: sp.record(signature = signed_collection, royalties_type = TL_TokenRegistry.royaltiesLegacy) }

    registry.manage_collections([
        sp.variant("add_public", manage_public_params),
        sp.variant("add_private", manage_private_params),
        sp.variant("add_trusted", manage_trusted_params)
    ]).run(sender = admin)

    empty_royalties = sp.record(total=1000, shares={})
    valid_royalties1 = sp.record(total=1000, shares={
        bob.address: sp.nat(250)})
    valid_royalties2 = sp.record(total=1000, shares={
        bob.address: sp.nat(150),
        alice.address: sp.nat(50)})

    # It get's a little special here...
    # V1 items return empty royalties on success.
    adapter_test.testRoyalties(token_key=token_keys["legacy0"], expected=sp.some(empty_royalties)).run(sender=admin)
    # V2 items should fail with TOKEN_UNDEFINED.
    adapter_test.testRoyalties(token_key=token_keys["items0"], expected=sp.none).run(sender=admin, valid=False, exception="TOKEN_UNDEFINED")
    # Trusted should fail with UNKNOWN_ROYALTIES because no one added the royalties yet.
    adapter_test.testRoyalties(token_key=token_keys["trusted"], expected=sp.none).run(sender=admin, valid=False, exception="UNKNOWN_ROYALTIES")

    scenario.h2("Add trusted royalties but invalid token")

    offchain_royalties=sp.record(token_key=sp.record(fa2=token_keys["trusted"].fa2, id=sp.some(token_keys["trusted"].id)), token_royalties=valid_royalties1)
    offchain_royalties_signed = TL_LegacyRoyalties.signRoyalties(offchain_royalties, royalties_key.secret_key)
    legacy_royalties.add_royalties({"key": [sp.record(signature=offchain_royalties_signed, offchain_royalties=offchain_royalties)]}).run(sender=bob)

    # Trusted should succeed, even if token does not exist. Because they are trusted.
    adapter_test.testRoyalties(token_key=token_keys["trusted"], expected=sp.some(valid_royalties1)).run(sender=admin)

    scenario.h2("Mint v1 and v2 tokens.")

    items_tokens_legacy.mint([sp.record(
        to_=bob.address,
        amount=10,
        token=sp.variant("new", sp.record(
            metadata={"": sp.bytes("0x00")},
            royalties=sp.record(
                royalties=sp.nat(250),
                contributors=[
                    sp.record(address=bob.address, relative_royalties=1000, role=sp.variant("minter", sp.unit))
                ]
            )
        ))
    ),
    sp.record(
        to_=bob.address,
        amount=10,
        token=sp.variant("new", sp.record(
            metadata={"": sp.bytes("0x00")},
            royalties=sp.record(
                royalties=sp.nat(200),
                contributors=[
                    sp.record(address=bob.address, relative_royalties=750, role=sp.variant("minter", sp.unit)),
                    sp.record(address=alice.address, relative_royalties=250, role=sp.variant("minter", sp.unit)),
                ]
            )
        ))
    )]).run(sender=admin)

    items_tokens.mint([sp.record(
        to_=bob.address,
        amount=10,
        token=sp.variant("new", sp.record(
            metadata={"": sp.bytes("0x00")},
            royalties={
                bob.address: 250
            }
        ))
    ),
    sp.record(
        to_=bob.address,
        amount=10,
        token=sp.variant("new", sp.record(
            metadata={"": sp.bytes("0x00")},
            royalties={
                bob.address: 150,
                alice.address: 50
            }
        ))
    )]).run(sender=admin)

    # now legacy and items should succeed
    for key in ["legacy0", "items0"]:
        adapter_test.testRoyalties(token_key=token_keys[key], expected=sp.some(valid_royalties1)).run(sender=admin)

    for key in ["legacy1", "items1"]:
        adapter_test.testRoyalties(token_key=token_keys[key], expected=sp.some(valid_royalties2)).run(sender=admin)