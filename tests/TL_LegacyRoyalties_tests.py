import smartpy as sp

from tz1and_contracts_smartpy.mixins.Administrable import Administrable
from contracts import TL_LegacyRoyalties, FA2


class tokenNoRoyalties(
    Administrable,
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
        FA2.MintFungible.__init__(self)
        Administrable.__init__(self, admin)


@sp.add_test(name = "TL_LegacyRoyalties_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    carol   = sp.test_account("Carol")
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

    pfp_tokens = tokenNoRoyalties(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += pfp_tokens

    # create registry contract
    scenario.h1("Test LegacyRoyalties")
    legacy_royalties = TL_LegacyRoyalties.TL_LegacyRoyalties(admin.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += legacy_royalties

    # Managing keys
    scenario.h2("manage_registry: keys")

    # Add permission only for admin
    for acc in [alice, bob, carol, admin]:
        legacy_royalties.manage_registry([sp.variant("add_keys", {
            "key1": royalties_key1.public_key})]).run(
                sender=acc,
                valid=(True if acc is admin else False),
                exception=(None if acc is admin else "NOT_PERMITTED"))
        
        if acc is admin:
            scenario.verify(legacy_royalties.data.public_keys.get("key1") == sp.record(owner=admin.address, key=royalties_key1.public_key))

    # Remove permission only for admin
    for acc in [alice, bob, carol, admin]:
        legacy_royalties.manage_registry([sp.variant("remove_keys", sp.set(["key1"]))]).run(
            sender=acc,
            valid=(True if acc is admin else False),
            exception=(None if acc is admin else "NOT_PERMITTED"))

        if acc is admin: scenario.verify(~legacy_royalties.data.public_keys.contains("key1"))

    # Give permission for carol
    legacy_royalties.manage_permissions([sp.variant("add_permissions", sp.set([carol.address]))]).run(sender=admin)

    # Add permission for carol
    for acc in [alice, bob, carol]:
        legacy_royalties.manage_registry([sp.variant("add_keys", {
            "key1": royalties_key1.public_key})]).run(
                sender=acc,
                valid=(True if acc is carol else False),
                exception=(None if acc is carol else "NOT_PERMITTED"))
        
        if acc is carol:
            scenario.verify(legacy_royalties.data.public_keys.get("key1") == sp.record(owner=carol.address, key=royalties_key1.public_key))

    # Remove permission only for carol
    for acc in [alice, bob, carol]:
        legacy_royalties.manage_registry([sp.variant("remove_keys", sp.set(["key1"]))]).run(
            sender=acc,
            valid=(True if acc is carol else False),
            exception=(None if acc is carol else "NOT_PERMITTED"))

        if acc is carol: scenario.verify(~legacy_royalties.data.public_keys.contains("key1"))

    # Add some more keys for further testing
    legacy_royalties.manage_registry([sp.variant("add_keys", {
        "key1": royalties_key1.public_key,
        "key2": royalties_key2.public_key
    })]).run(sender=admin)
    scenario.verify(legacy_royalties.data.public_keys.get("key1") == sp.record(owner=admin.address, key=royalties_key1.public_key))
    scenario.verify(legacy_royalties.data.public_keys.get("key2") == sp.record(owner=admin.address, key=royalties_key2.public_key))

    # no permission
    legacy_royalties.manage_registry([sp.variant("add_keys", {
        "key_invalid": royalties_key_invalid.public_key
    })]).run(sender=bob, valid=False, exception="NOT_PERMITTED")
    legacy_royalties.manage_registry([sp.variant("remove_keys", sp.set(["key_invalid"]))]).run(sender=alice, valid=False, exception="NOT_PERMITTED")

    # Adding royalties
    scenario.h2("add_royalties")

    # Royalties
    offchain_royalties_unique = sp.set_type_expr(sp.record(
        token_key=sp.record(
            id=sp.some(10),
            fa2=items_tokens.address
        ),
        token_royalties=sp.record(
            total=2000,
            shares={
                bob.address: 200,
                alice.address: 200 })
    ), TL_LegacyRoyalties.t_royalties_offchain)

    offchain_royalties_global = sp.set_type_expr(sp.record(
        token_key=sp.record(
            id=sp.none,
            fa2=pfp_tokens.address
        ),
        token_royalties=sp.record(
            total=2000,
            shares={
                bob.address: 200,
                alice.address: 200 })
    ), TL_LegacyRoyalties.t_royalties_offchain)

    token_key_unique=sp.record(
        id=10,
        fa2=items_tokens.address,
    )

    token_key_global=sp.record(
        id=10,
        fa2=pfp_tokens.address,
    )

    royalties_unique_signed_valid1 = TL_LegacyRoyalties.signRoyalties(offchain_royalties_unique, royalties_key1.secret_key)
    royalties_unique_signed_valid2 = TL_LegacyRoyalties.signRoyalties(offchain_royalties_unique, royalties_key2.secret_key)
    royalties_unique_signed_invalid = TL_LegacyRoyalties.signRoyalties(offchain_royalties_unique, royalties_key_invalid.secret_key)

    royalties_global_signed_valid1 = TL_LegacyRoyalties.signRoyalties(offchain_royalties_global, royalties_key1.secret_key)
    royalties_global_signed_valid2 = TL_LegacyRoyalties.signRoyalties(offchain_royalties_global, royalties_key2.secret_key)
    royalties_global_signed_invalid = TL_LegacyRoyalties.signRoyalties(offchain_royalties_global, royalties_key_invalid.secret_key)

    legacy_royalties.add_royalties({
        "key1": [
            sp.record(signature=royalties_unique_signed_valid1, offchain_royalties=offchain_royalties_unique),
            sp.record(signature=royalties_global_signed_valid1, offchain_royalties=offchain_royalties_global)
        ],
        "key2": [
            sp.record(signature=royalties_unique_signed_valid2, offchain_royalties=offchain_royalties_unique),
            sp.record(signature=royalties_global_signed_valid2, offchain_royalties=offchain_royalties_global)
        ]
    }).run(sender=bob)
    scenario.verify(legacy_royalties.data.royalties.contains(offchain_royalties_unique.token_key))
    scenario.verify(legacy_royalties.data.royalties.contains(offchain_royalties_global.token_key))

    legacy_royalties.add_royalties({"key_invalid": [
        sp.record(signature=royalties_unique_signed_invalid, offchain_royalties=offchain_royalties_unique)
    ]}).run(sender=alice, valid=False, exception="INVALID_KEY_ID")

    legacy_royalties.add_royalties({"key2": [
        sp.record(signature=royalties_unique_signed_invalid, offchain_royalties=offchain_royalties_unique)
    ]}).run(sender=bob, valid=False, exception="INVALID_SIGNATURE")

    legacy_royalties.add_royalties({"key2": [
        sp.record(signature=royalties_global_signed_invalid, offchain_royalties=offchain_royalties_global)
    ]}).run(sender=bob, valid=False, exception="INVALID_SIGNATURE")

    scenario.h2("manage_registry: remove royalties")

    remove_unique = {items_tokens.address: sp.set([sp.some(10)])}
    remove_global = {pfp_tokens.address: sp.set([sp.none])}
    legacy_royalties.manage_registry([sp.variant("remove_royalties", remove_unique)]).run(sender=bob, valid=False, exception="NOT_PERMITTED")
    legacy_royalties.manage_registry([sp.variant("remove_royalties", remove_unique)]).run(sender=alice, valid=False, exception="NOT_PERMITTED")
    legacy_royalties.manage_registry([sp.variant("remove_royalties", remove_unique)]).run(sender=admin)
    legacy_royalties.manage_registry([sp.variant("remove_royalties", remove_global)]).run(sender=admin)
    scenario.verify(~legacy_royalties.data.royalties.contains(offchain_royalties_unique.token_key))
    scenario.verify(~legacy_royalties.data.royalties.contains(offchain_royalties_global.token_key))

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

    scenario.h3("get_royalties_batch")
    legacy_royalties.add_royalties({"key2": [
        sp.record(signature=royalties_unique_signed_valid2, offchain_royalties=offchain_royalties_unique),
        sp.record(signature=royalties_global_signed_valid2, offchain_royalties=offchain_royalties_global)
    ]}).run(sender=bob)

    get_royalties = legacy_royalties.get_royalties_batch(sp.set([token_key_unique, token_key_global]))
    scenario.show(get_royalties)
    scenario.verify_equal(get_royalties, sp.map({
        token_key_unique: offchain_royalties_unique.token_royalties,
        token_key_global: offchain_royalties_global.token_royalties}))

    # includes unknown royalties
    get_royalties = legacy_royalties.get_royalties_batch(sp.set([token_key_unique, sp.record(fa2=items_tokens.address, id=10000234)]))
    scenario.show(get_royalties)
    scenario.verify(~sp.is_failing(get_royalties))
    scenario.verify_equal(get_royalties, sp.map({token_key_unique: offchain_royalties_unique.token_royalties}))

    scenario.h3("get_royalties")

    # unique
    get_royalties = legacy_royalties.get_royalties(token_key_unique)
    scenario.show(get_royalties)
    scenario.verify_equal(get_royalties, offchain_royalties_unique.token_royalties)

    # global
    get_royalties = legacy_royalties.get_royalties(token_key_global)
    scenario.show(get_royalties)
    scenario.verify_equal(get_royalties, offchain_royalties_global.token_royalties)

    scenario.table_of_contents()
