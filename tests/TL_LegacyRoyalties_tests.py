import smartpy as sp

legacy_royalties_contract = sp.io.import_script_from_url("file:contracts/TL_LegacyRoyalties.py")
admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")


class tokenNoRoyalties(
    admin_mixin.Administrable,
    FA2.ChangeMetadata,
    FA2.MintFungible,
    FA2.BurnFungible,
    FA2.Fa2Fungible,
):
    """tz1and Items"""

    def __init__(self, metadata, admin):
        FA2.Fa2Fungible.__init__(
            self, metadata=metadata,
            name="tz1and Items", description="tz1and Item FA2 Tokens.",
            policy=FA2.PauseTransfer(FA2.OwnerOrOperatorAdhocTransfer()), has_royalties=False,
            allow_mint_existing=False
        )
        admin_mixin.Administrable.__init__(self, admin)


@sp.add_test(name = "TL_LegacyRoyalties_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    royalties_key1 = sp.test_account("Royalties 1")
    royalties_key2 = sp.test_account("Royalties 2")
    royalties_key_invalid = sp.test_account("Royalties Invalid")
    scenario = sp.test_scenario()

    scenario.h1("LegacyRoyalties Tests")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h1("Accounts")
    scenario.show([admin, alice, bob, royalties_key1, royalties_key2, royalties_key_invalid])

    # create a FA2 contract for testing
    scenario.h1("Create test env")

    scenario.h2("tokens")
    items_tokens = tokenNoRoyalties(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    # create registry contract
    scenario.h1("Test LegacyRoyalties")
    legacy_royalties = legacy_royalties_contract.TL_LegacyRoyalties(admin.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += legacy_royalties

    # Managing keys
    scenario.h2("manage_public_keys")
    legacy_royalties.manage_public_keys([sp.variant("add", [
        sp.record(id="key1", key=royalties_key1.public_key)
    ])]).run(sender=admin)
    scenario.verify(legacy_royalties.data.public_keys.get("key1") == royalties_key1.public_key)

    legacy_royalties.manage_public_keys([sp.variant("remove", ["key1"])]).run(sender=admin)
    scenario.verify(~legacy_royalties.data.public_keys.contains("key1"))

    legacy_royalties.manage_public_keys([sp.variant("add", [
        sp.record(id="key1", key=royalties_key1.public_key),
        sp.record(id="key2", key=royalties_key2.public_key)
    ])]).run(sender=admin)
    scenario.verify(legacy_royalties.data.public_keys.get("key1") == royalties_key1.public_key)
    scenario.verify(legacy_royalties.data.public_keys.get("key2") == royalties_key2.public_key)

    # no permission
    legacy_royalties.manage_public_keys([sp.variant("add", [
        sp.record(id="key_invalid", key=royalties_key_invalid.public_key)
    ])]).run(sender=bob, valid=False, exception="NOT_PERMITTED")
    legacy_royalties.manage_public_keys([sp.variant("remove", ["key_invalid"])]).run(sender=alice, valid=False, exception="NOT_PERMITTED")

    # Update settings
    scenario.h2("update_settings")
    #legacy_royalties.update_settings([sp.variant("paused", False)]).run(sender=alice, valid=False, exception="ONLY_ADMIN")
    #legacy_royalties.update_settings([sp.variant("paused", False)]).run(sender=bob, valid=False, exception="ONLY_ADMIN")

    # Adding royalties
    scenario.h2("add_royalties")

    # Royalties
    offchain_royalties = sp.set_type_expr(sp.record(
        token_key=sp.record(
            id=sp.some(10),
            fa2=items_tokens.address,
        ),
        token_royalties=sp.record(
            total=2000,
            shares=[
                sp.record(address=bob.address, share=200),
                sp.record(address=alice.address, share=200)])
    ), legacy_royalties_contract.t_royalties_offchain)

    royalties_signed_valid1 = legacy_royalties_contract.sign_royalties(offchain_royalties, royalties_key1.secret_key)
    royalties_signed_valid2 = legacy_royalties_contract.sign_royalties(offchain_royalties, royalties_key2.secret_key)
    royalties_signed_invalid = legacy_royalties_contract.sign_royalties(offchain_royalties, royalties_key_invalid.secret_key)

    legacy_royalties.add_royalties({
        "key1": [
            sp.record(signature=royalties_signed_valid1, offchain_royalties=offchain_royalties)
        ],
        "key2": [
            sp.record(signature=royalties_signed_valid2, offchain_royalties=offchain_royalties)
        ]
    }).run(sender=bob)
    scenario.verify(legacy_royalties.data.royalties.contains(offchain_royalties.token_key))

    legacy_royalties.add_royalties({"key_invalid": [
        sp.record(signature=royalties_signed_invalid, offchain_royalties=offchain_royalties)
    ]}).run(sender=alice, valid=False, exception="INVALID_KEY_ID")

    legacy_royalties.add_royalties({"key2": [
        sp.record(signature=royalties_signed_invalid, offchain_royalties=offchain_royalties)
    ]}).run(sender=bob, valid=False, exception="INVALID_SIGNATURE")

    scenario.h2("remove_royalties")

    legacy_royalties.remove_royalties(sp.set([offchain_royalties.token_key])).run(sender=bob, valid=False, exception="NOT_PERMITTED")
    legacy_royalties.remove_royalties(sp.set([offchain_royalties.token_key])).run(sender=alice, valid=False, exception="NOT_PERMITTED")
    legacy_royalties.remove_royalties(sp.set([offchain_royalties.token_key])).run(sender=admin)
    scenario.verify(~legacy_royalties.data.royalties.contains(offchain_royalties.token_key))

    # Test onchain views
    scenario.h2("Test views")

    scenario.h3("get_public_keys")
    get_public_keys = legacy_royalties.get_public_keys(sp.set(["key1", "key2"]))
    scenario.show(get_public_keys)
    scenario.verify_equal(get_public_keys, sp.map({"key1": royalties_key1.public_key, "key2": royalties_key2.public_key}))

    # includes an invalid key
    get_public_keys = legacy_royalties.get_public_keys(sp.set(["key1", "invalid_key"]))
    scenario.show(get_public_keys)
    scenario.verify(~sp.is_failing(get_public_keys))
    scenario.verify_equal(get_public_keys, sp.map({"key1": royalties_key1.public_key}))

    scenario.h3("get_token_royalties_batch")
    legacy_royalties.add_royalties({"key2": [
        sp.record(signature=royalties_signed_valid2, offchain_royalties=offchain_royalties)
    ]}).run(sender=bob)

    get_royalties = legacy_royalties.get_token_royalties_batch(sp.set([offchain_royalties.token_key]))
    scenario.show(get_royalties)
    scenario.verify_equal(get_royalties, sp.map({offchain_royalties.token_key: offchain_royalties.token_royalties}))

    # includes unknown royalties
    get_royalties = legacy_royalties.get_token_royalties_batch(sp.set([offchain_royalties.token_key, sp.record(fa2=items_tokens.address, id=sp.some(10000234))]))
    scenario.show(get_royalties)
    scenario.verify(~sp.is_failing(get_royalties))
    scenario.verify_equal(get_royalties, sp.map({offchain_royalties.token_key: offchain_royalties.token_royalties}))

    scenario.h3("get_token_royalties")
    legacy_royalties.add_royalties({"key2": [
        sp.record(signature=royalties_signed_valid2, offchain_royalties=offchain_royalties)
    ]}).run(sender=bob)

    get_royalties = legacy_royalties.get_token_royalties(offchain_royalties.token_key)
    scenario.show(get_royalties)
    scenario.verify_equal(get_royalties, offchain_royalties.token_royalties)

    # TODO: get keys
    # TODO: get royalties

    scenario.table_of_contents()
