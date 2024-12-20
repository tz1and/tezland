import smartpy as sp

from contracts import TL_Blacklist, TL_TokenRegistry, Tokens
from contracts.upgrades import TL_Minter_v2_1
from contracts.utils import ErrorMessages


@sp.add_test(name = "TL_Minter_v2_1_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    carol   = sp.test_account("Carol")
    collections_key = sp.test_account("Collections")
    scenario = sp.test_scenario()

    scenario.h1("Minter v2.1 Tests")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h1("Accounts")
    scenario.show([admin, alice, bob, carol])

    # create a FA2 contract for testing
    scenario.h1("Create test env")

    scenario.h2("tokens")
    items_tokens = Tokens.tz1andItems_v2(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    # create registry contract
    scenario.h1("Test Minter")
    registry = TL_TokenRegistry.TL_TokenRegistry(admin.address, collections_key.public_key,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += registry

    scenario.h2("Blacklist")
    blacklist = TL_Blacklist.TL_Blacklist(admin.address)
    scenario += blacklist

    scenario.h2("minter")
    minter = TL_Minter_v2_1.TL_Minter_v2_1(admin.address, registry.address, blacklist.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    # set items_tokens v2 and administrator to minter contract
    items_tokens.transfer_administrator(minter.address).run(sender = admin)
    minter.token_administration([sp.variant("accept_fa2_administrator", sp.set([items_tokens.address]))]).run(sender = admin)


    scenario.h2("update_settings")

    # check defaults
    scenario.verify(minter.data.settings.registry == registry.address)
    scenario.verify(minter.data.settings.max_contributors == 3)
    scenario.verify(minter.data.settings.max_royalties == 250)

    scenario.h3("registry")

    # failure cases.
    for t in [(bob, "ONLY_ADMIN"), (alice, "ONLY_ADMIN"), (admin, "NOT_CONTRACT")]:
        sender, exception = t
        minter.update_settings([sp.variant("registry", bob.address)]).run(sender = sender, valid = False, exception = exception)

    minter.update_settings([sp.variant("registry", minter.address)]).run(sender = admin)
    scenario.verify(minter.data.settings.registry == minter.address)
    minter.update_settings([sp.variant("registry", registry.address)]).run(sender = admin)
    scenario.verify(minter.data.settings.registry == registry.address)

    scenario.h3("max_contributors")
    minter.update_settings([sp.variant("max_contributors", 6)]).run(sender = admin)
    scenario.verify(minter.data.settings.max_contributors == 6)
    minter.update_settings([sp.variant("max_contributors", 3)]).run(sender = admin)
    scenario.verify(minter.data.settings.max_contributors == 3)

    scenario.h3("max_royalties")
    minter.update_settings([sp.variant("max_royalties", 100)]).run(sender = admin)
    scenario.verify(minter.data.settings.max_royalties == 100)
    minter.update_settings([sp.variant("max_royalties", 250)]).run(sender = admin)
    scenario.verify(minter.data.settings.max_royalties == 250)


    #
    # test public collections
    #
    scenario.h2("Public Collections")

    # test Item minting
    scenario.h3("mint_public")

    registry.manage_collections([sp.variant("add_public", {items_tokens.address: TL_TokenRegistry.royaltiesTz1andV2})]).run(sender = admin)

    minter.mint_public(collection = minter.address,
        to_ = bob.address,
        amount = 4,
        royalties = { bob.address: sp.nat(250) },
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob, valid = False, exception = ErrorMessages.invalid_collection())

    minter.mint_public(collection = items_tokens.address,
        to_ = bob.address,
        amount = 4,
        royalties = { bob.address: sp.nat(250) },
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    minter.mint_public(collection = items_tokens.address,
        to_ = alice.address,
        amount = 25,
        royalties = { alice.address: sp.nat(250) },
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)

    minter.update_settings([sp.variant("paused", True)]).run(sender = admin)

    minter.mint_public(collection = items_tokens.address,
        to_ = alice.address,
        amount = 25,
        royalties = { alice.address: sp.nat(250) },
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice, valid = False)

    minter.update_settings([sp.variant("paused", False)]).run(sender = admin)
    registry.manage_collections([sp.variant("remove", sp.set([items_tokens.address]))]).run(sender = admin)


    #
    # test private collections
    #
    scenario.h2("Private Collections")

    # test Item minting
    scenario.h3("mint_private")

    manage_private_params = {items_tokens.address: sp.record(owner = bob.address, royalties_type = TL_TokenRegistry.royaltiesTz1andV2)}
    manager_collaborators_params = {items_tokens.address: sp.set([alice.address])}
    registry.manage_collections([sp.variant("add_private", manage_private_params)]).run(sender = admin)

    minter.mint_private(collection = minter.address,
        to_ = bob.address,
        amount = 4,
        royalties = { bob.address: sp.nat(250) },
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob, valid = False, exception = ErrorMessages.invalid_collection())

    minter.mint_private(collection = items_tokens.address,
        to_ = bob.address,
        amount = 4,
        royalties = { bob.address: sp.nat(250) },
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    # add alice as collaborator
    registry.admin_private_collections([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = bob)
    minter.mint_private(collection = items_tokens.address,
        to_ = alice.address,
        amount = 25,
        royalties = { alice.address: sp.nat(250) },
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)
    registry.admin_private_collections([sp.variant("remove_collaborators", manager_collaborators_params)]).run(sender = bob)

    minter.mint_private(collection = items_tokens.address,
        to_ = alice.address,
        amount = 25,
        royalties = { alice.address: sp.nat(250) },
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice, valid = False, exception = ErrorMessages.not_owner_or_collaborator())

    minter.update_settings([sp.variant("paused", True)]).run(sender = admin)

    minter.mint_private(collection = items_tokens.address,
        to_ = alice.address,
        amount = 25,
        royalties = { alice.address: sp.nat(250) },
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice, valid = False)

    minter.update_settings([sp.variant("paused", False)]).run(sender = admin)
    registry.manage_collections([sp.variant("remove", sp.set([items_tokens.address]))]).run(sender = admin)

    scenario.h3("update_private_metadata")

    registry.manage_collections([sp.variant("add_private", manage_private_params)]).run(sender = admin)

    invalid_metadata_uri = sp.utils.bytes_of_string("ipf://QmbWqxBEKC3P8tqsKc98xmWNzrzDtRLMiMPL8")
    valid_metadata_uri = sp.utils.bytes_of_string("ipfs://QmbWqxBEKC3P8tqsKc98xmWNzrzDtRLMiMPL8wBuTGsMnR")

    minter.update_private_metadata({items_tokens.address: valid_metadata_uri}).run(sender = admin, valid = False, exception = ErrorMessages.not_owner_or_collaborator())
    minter.update_private_metadata({items_tokens.address: valid_metadata_uri}).run(sender = alice, valid = False, exception = ErrorMessages.not_owner_or_collaborator())
    minter.update_private_metadata({items_tokens.address: invalid_metadata_uri}).run(sender = bob, valid = False, exception = "INVALID_METADATA")

    scenario.verify(items_tokens.data.metadata[""] == sp.utils.bytes_of_string("https://example.com"))
    minter.update_private_metadata({items_tokens.address: valid_metadata_uri}).run(sender = bob)
    scenario.verify(items_tokens.data.metadata[""] == valid_metadata_uri)

    minter.update_settings([sp.variant("paused", True)]).run(sender = admin)
    minter.update_private_metadata({items_tokens.address: valid_metadata_uri}).run(sender = bob, valid = False, exception = "ONLY_UNPAUSED")
    minter.update_settings([sp.variant("paused", False)]).run(sender = admin)

    registry.manage_collections([sp.variant("remove", sp.set([items_tokens.address]))]).run(sender = admin)


    #
    # test pause_fa2
    #
    scenario.h2("token_administration")

    scenario.h3("pause")

    # check tokens are unpaused to begin with
    scenario.verify(items_tokens.data.paused == False)

    # Invalid for anyone but admin.
    for acc in [alice, bob, admin]:
        minter.token_administration([
            sp.variant("pause", {items_tokens.address: True})
        ]).run(
            sender = acc,
            valid = (True if acc is admin else False),
            exception = (None if acc is admin else "ONLY_ADMIN"))

    # check tokens are paused
    scenario.verify(items_tokens.data.paused == True)

    # Invalid for anyone but admin.
    for acc in [alice, bob, admin]:
        minter.token_administration([
            sp.variant("pause", {items_tokens.address: False})
        ]).run(
            sender = acc,
            valid = (True if acc is admin else False),
            exception = (None if acc is admin else "ONLY_ADMIN"))

    # check tokens are unpaused
    scenario.verify(items_tokens.data.paused == False)

    scenario.h3("update_collection_metadata")

    # Invalid for anyone but admin.
    for acc in [alice, bob, admin]:
        minter.token_administration([
            sp.variant("update_collection_metadata", {items_tokens.address: valid_metadata_uri})
        ]).run(
            sender = acc,
            valid = (True if acc is admin else False),
            exception = (None if acc is admin else "ONLY_ADMIN"))


    #
    # test clear_adhoc_operators_fa2
    #
    scenario.h3("clear_adhoc_operators")

    items_tokens.update_adhoc_operators(sp.variant("add_adhoc_operators", sp.set([
        sp.record(operator=registry.address, token_id=0),
        sp.record(operator=registry.address, token_id=1),
        sp.record(operator=registry.address, token_id=2),
        sp.record(operator=registry.address, token_id=3),
    ]))).run(sender = alice)

    scenario.verify(sp.len(items_tokens.data.adhoc_operators) == 4)

    # Invalid for anyone but admin.
    for acc in [alice, bob, admin]:
        minter.token_administration([
            sp.variant("clear_adhoc_operators", sp.set([items_tokens.address]))
        ]).run(
            sender = acc,
            valid = (True if acc is admin else False),
            exception = (None if acc is admin else "ONLY_ADMIN"))

    scenario.verify(sp.len(items_tokens.data.adhoc_operators) == 0)


    #
    # test accept_fa2_administrator
    #
    scenario.h3("accept_fa2_administrator/transfer_fa2_administrator")

    # Invalid for anyone if admin not proposed.
    for t in [(alice, "ONLY_ADMIN"), (bob, "ONLY_ADMIN"), (admin, "NOT_PROPOSED_ADMIN")]:
        sender, exception = t
        minter.token_administration([
            sp.variant("accept_fa2_administrator", sp.set([items_tokens.address]))
        ]).run(
            sender = sender,
            valid = False,
            exception = exception)

    # transfer to fa2_admin
    # Invalid for anyone but admin.
    for acc in [alice, bob, admin]:
        minter.token_administration([
            sp.variant("transfer_fa2_administrator", { items_tokens.address: admin.address })
        ]).run(
            sender = acc,
            valid = (True if acc is admin else False),
            exception = (None if acc is admin else "ONLY_ADMIN"))

    # Accept, transfer back.
    items_tokens.accept_administrator().run(sender = admin)
    items_tokens.transfer_administrator(minter.address).run(sender = admin)

    # Invalid for anyone but admin.
    for acc in [alice, bob, admin]:
        minter.token_administration([
            sp.variant("accept_fa2_administrator", sp.set([items_tokens.address]))
        ]).run(
            sender = acc,
            valid = (True if acc is admin else False),
            exception = (None if acc is admin else "ONLY_ADMIN"))


    #
    # Test royalties.
    #
    scenario.h2("test royalties")

    # add a v2 collection for private minting
    items_tokens_private = Tokens.tz1andItems_v2(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens_private

    items_tokens_private.transfer_administrator(minter.address).run(sender = admin)
    minter.token_administration([sp.variant("accept_fa2_administrator", sp.set([items_tokens_private.address]))]).run(sender = admin)

    registry.manage_collections([sp.variant("add_public", {items_tokens.address: TL_TokenRegistry.royaltiesTz1andV2})]).run(sender = admin)

    registry.manage_collections([sp.variant("add_private", {
        items_tokens_private.address: sp.record(owner = bob.address, royalties_type = TL_TokenRegistry.royaltiesTz1andV2)
    })]).run(sender = admin)

    scenario.h3("valid royalties")

    # Define some valid royalties
    valid_royalties = [
        { alice.address: sp.nat(250) },
        {},
        {
            admin.address: sp.nat(90),
            bob.address: sp.nat(30),
            alice.address: sp.nat(30)
        }
    ]

    for royalties in valid_royalties:
        minter.mint_public(collection = items_tokens.address,
            metadata=sp.utils.bytes_of_string("test_metadata"),
            to_=alice.address,
            amount=10,
            royalties=royalties
        ).run(sender=admin)

        minter.mint_private(collection = items_tokens_private.address,
            metadata=sp.utils.bytes_of_string("test_metadata"),
            to_=alice.address,
            amount=10,
            royalties=royalties
        ).run(sender=bob)

    scenario.h3("invalid royalties")

    # Define some invalid royalties
    invalid_royalties = [
        { alice.address: sp.nat(251) },
        {
            admin.address: sp.nat(0),
            alice.address: sp.nat(0),
            bob.address: sp.nat(0),
            carol.address: sp.nat(0)
        },
        {
            admin.address: sp.nat(100),
            bob.address: sp.nat(100),
            alice.address: sp.nat(100)
        }
    ]

    for royalties in invalid_royalties:
        minter.mint_public(collection = items_tokens.address,
            metadata=sp.utils.bytes_of_string("test_metadata"),
            to_=alice.address,
            amount=10,
            royalties=royalties
        ).run(sender=admin, valid=False, exception="FA2_INV_ROYALTIES")

        minter.mint_private(collection = items_tokens_private.address,
            metadata=sp.utils.bytes_of_string("test_metadata"),
            to_=alice.address,
            amount=10,
            royalties=royalties
        ).run(sender=bob, valid=False, exception="FA2_INV_ROYALTIES")

    scenario.table_of_contents()
