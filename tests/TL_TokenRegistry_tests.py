import smartpy as sp

token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter_v2.py")
tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")


# TODO: test all the new views


@sp.add_test(name = "TL_TokenRegistry_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    royalties_key = sp.test_account("Royalties")
    collections_key = sp.test_account("Collections")
    scenario = sp.test_scenario()

    scenario.h1("TokenRegistry Tests")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h1("Accounts")
    scenario.show([admin, alice, bob, royalties_key, collections_key])

    # create a FA2 contract for testing
    scenario.h1("Create test env")

    scenario.h2("tokens")

    scenario.h3("tz1andItems")
    items_tokens = tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    scenario.h3("tz1andItems_v2")
    items_tokens_v2 = tokens.tz1andItems_v2(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens_v2

    scenario.h3("other token")
    other_tokens = tokens.tz1andItems_v2(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += other_tokens

    # create registry contract
    scenario.h1("Test TokenRegistry")
    registry = token_registry_contract.TL_TokenRegistry(admin.address, collections_key.public_key,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += registry

    scenario.h2("minter")
    minter = minter_contract.TL_Minter(admin.address, registry.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    # set items_tokens administrator to minter contract
    items_tokens.transfer_administrator(minter.address).run(sender = admin)
    minter.accept_fa2_administrator([items_tokens.address]).run(sender = admin)

    # test public collections
    scenario.h2("Public Collections")

    signed_collection = token_registry_contract.signCollection(
        sp.record(collection = items_tokens.address, royalties_type = 1),
        collections_key.secret_key
    )

    manage_public_params = { items_tokens.address: 1 }
    manage_private_params = { items_tokens.address: sp.record(owner = bob.address, royalties_type = 1) }
    manage_trusted_params = { items_tokens.address: sp.record(signature = signed_collection, royalties_type = 1) }

    # test adding public collections
    scenario.h3("manage_collection public")

    registry.manage_collections([sp.variant("add_public", manage_public_params)]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    registry.manage_collections([sp.variant("add_public", manage_public_params)]).run(sender = alice, valid = False, exception = "NOT_PERMITTED")

    # add permission for alice
    registry.manage_permissions([sp.variant("add_permissions", [alice.address])]).run(sender = admin)
    registry.manage_collections([sp.variant("add_public", manage_public_params)]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    registry.manage_collections([sp.variant("add_public", manage_public_params)]).run(sender = alice)
    scenario.verify_equal(registry.data.collections.get(items_tokens.address).collection_type, token_registry_contract.collectionPublic)

    # public collection can't be private
    registry.manage_collections([sp.variant("add_private", manage_private_params)]).run(sender = admin, valid = False, exception = "COLLECTION_EXISTS")

    registry.manage_collections([sp.variant("remove", [items_tokens.address])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    registry.manage_collections([sp.variant("remove", [items_tokens.address])]).run(sender = admin)
    scenario.verify(~registry.data.collections.contains(items_tokens.address))

    # only unpaused
    registry.update_settings([sp.variant("paused", True)]).run(sender = admin)
    registry.manage_collections([sp.variant("add_public", manage_public_params)]).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")
    registry.update_settings([sp.variant("paused", False)]).run(sender = admin)

    registry.manage_permissions([sp.variant("remove_permissions", [alice.address])]).run(sender = admin)

    # test trusted collections
    scenario.h2("Trusted Collections")

    # test adding trusted collections
    scenario.h3("manage_collections trusted")

    registry.manage_collections([sp.variant("add_trusted", manage_trusted_params)]).run(sender = bob)
    scenario.verify_equal(registry.data.collections.get(items_tokens.address).collection_type, token_registry_contract.collectionTrusted)

    # trusted collection can't be private
    registry.manage_collections([sp.variant("add_private", manage_private_params)]).run(sender = admin, valid = False, exception = "COLLECTION_EXISTS")

    registry.manage_collections([sp.variant("remove", [items_tokens.address])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    registry.manage_collections([sp.variant("remove", [items_tokens.address])]).run(sender = admin)
    scenario.verify(~registry.data.collections.contains(items_tokens.address))

    # only unpaused
    registry.update_settings([sp.variant("paused", True)]).run(sender = admin)
    registry.manage_collections([sp.variant("add_trusted", manage_trusted_params)]).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")
    registry.update_settings([sp.variant("paused", False)]).run(sender = admin)

    # test private collections
    scenario.h2("Private Collections")

    # test adding private collections
    scenario.h3("manage_collections private")

    registry.manage_collections([sp.variant("add_private", manage_private_params)]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    registry.manage_collections([sp.variant("add_private", manage_private_params)]).run(sender = alice, valid = False, exception = "NOT_PERMITTED")

    # add permission for alice
    registry.manage_permissions([sp.variant("add_permissions", [alice.address])]).run(sender = admin)
    registry.manage_collections([sp.variant("add_private", manage_private_params)]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    registry.manage_collections([sp.variant("add_private", manage_private_params)]).run(sender = alice)
    scenario.verify_equal(registry.data.collections.get(items_tokens.address).collection_type, token_registry_contract.collectionPrivate)

    # private collection can't be public
    registry.manage_collections([sp.variant("add_public", manage_public_params)]).run(sender = admin, valid = False, exception = "COLLECTION_EXISTS")

    registry.manage_collections([sp.variant("remove", [items_tokens.address])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    registry.manage_collections([sp.variant("remove", [items_tokens.address])]).run(sender = admin)
    scenario.verify(~registry.data.collections.contains(items_tokens.address))

    # only unpaused
    registry.update_settings([sp.variant("paused", True)]).run(sender = admin)
    registry.manage_collections([sp.variant("add_private", manage_private_params)]).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")
    registry.update_settings([sp.variant("paused", False)]).run(sender = admin)

    registry.manage_permissions([sp.variant("remove_permissions", [alice.address])]).run(sender = admin)

    scenario.h3("manage_collaborators")

    registry.manage_collections([sp.variant("add_private", manage_private_params)]).run(sender = admin)

    manager_collaborators_params = sp.record(collection = items_tokens.address, collaborators = [alice.address])
    registry.admin_private_collections([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = admin, valid = False, exception = "ONLY_OWNER")
    registry.admin_private_collections([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = alice, valid = False, exception = "ONLY_OWNER")
    scenario.verify(~registry.data.collaborators.contains(sp.record(collection = items_tokens.address, collaborator = alice.address)))
    registry.admin_private_collections([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = bob)
    scenario.verify(registry.data.collaborators.contains(sp.record(collection = items_tokens.address, collaborator = alice.address)))

    registry.admin_private_collections([sp.variant("remove_collaborators", manager_collaborators_params)]).run(sender = admin, valid = False, exception = "ONLY_OWNER")
    registry.admin_private_collections([sp.variant("remove_collaborators", manager_collaborators_params)]).run(sender = alice, valid = False, exception = "ONLY_OWNER")
    registry.admin_private_collections([sp.variant("remove_collaborators", manager_collaborators_params)]).run(sender = bob)
    scenario.verify(~registry.data.collaborators.contains(sp.record(collection = items_tokens.address, collaborator = alice.address)))

    registry.update_settings([sp.variant("paused", True)]).run(sender = admin)
    registry.admin_private_collections([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = bob, valid = False, exception = "ONLY_UNPAUSED")
    registry.update_settings([sp.variant("paused", False)]).run(sender = admin)

    registry.manage_collections([sp.variant("remove", [items_tokens.address])]).run(sender = admin)

    scenario.h3("transfer_private_ownership")

    registry.manage_collections([sp.variant("add_private", manage_private_params)]).run(sender = admin)

    registry.admin_private_collections([sp.variant("transfer_ownership", sp.record(collection = items_tokens.address, new_owner = alice.address))]).run(sender = admin, valid = False, exception = "ONLY_OWNER")
    registry.admin_private_collections([sp.variant("transfer_ownership", sp.record(collection = items_tokens.address, new_owner = alice.address))]).run(sender = alice, valid = False, exception = "ONLY_OWNER")
    scenario.verify(registry.data.collections[items_tokens.address].ownership.open_some().owner == bob.address)

    registry.admin_private_collections([sp.variant("transfer_ownership", sp.record(collection = items_tokens.address, new_owner = alice.address))]).run(sender = bob)
    scenario.verify(registry.data.collections[items_tokens.address].ownership.open_some().proposed_owner == sp.some(alice.address))

    registry.admin_private_collections([sp.variant("acccept_ownership", items_tokens.address)]).run(sender = admin, valid = False, exception = "NOT_PROPOSED_OWNER")
    registry.admin_private_collections([sp.variant("acccept_ownership", items_tokens.address)]).run(sender = bob, valid = False, exception = "NOT_PROPOSED_OWNER")
    registry.admin_private_collections([sp.variant("acccept_ownership", items_tokens.address)]).run(sender = alice)
    scenario.verify(registry.data.collections[items_tokens.address].ownership.open_some().owner == alice.address)
    scenario.verify(registry.data.collections[items_tokens.address].ownership.open_some().proposed_owner == sp.none)

    registry.admin_private_collections([sp.variant("acccept_ownership", items_tokens.address)]).run(sender = admin, valid = False, exception = "NOT_PROPOSED_OWNER")
    registry.admin_private_collections([sp.variant("acccept_ownership", items_tokens.address)]).run(sender = bob, valid = False, exception = "NOT_PROPOSED_OWNER")
    registry.admin_private_collections([sp.variant("acccept_ownership", items_tokens.address)]).run(sender = alice, valid = False, exception = "NOT_PROPOSED_OWNER")

    registry.update_settings([sp.variant("paused", True)]).run(sender = admin)
    registry.admin_private_collections([sp.variant("transfer_ownership", sp.record(collection = items_tokens.address, new_owner = bob.address))]).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")
    registry.admin_private_collections([sp.variant("acccept_ownership", items_tokens.address)]).run(sender = admin, valid = False, exception = "ONLY_UNPAUSED")
    registry.update_settings([sp.variant("paused", False)]).run(sender = admin)

    registry.manage_collections([sp.variant("remove", [items_tokens.address])]).run(sender = admin)

    scenario.h3("update_settings")

    registry.update_settings([sp.variant("paused", False)]).run(sender=alice, valid=False, exception="ONLY_ADMIN")
    registry.update_settings([sp.variant("paused", False)]).run(sender=bob, valid=False, exception="ONLY_ADMIN")

    scenario.verify_equal(registry.data.collections_public_key, collections_key.public_key)
    registry.update_settings([sp.variant("collections_public_key", royalties_key.public_key)]).run(sender = admin)
    scenario.verify_equal(registry.data.collections_public_key, royalties_key.public_key)
    registry.update_settings([sp.variant("collections_public_key", collections_key.public_key)]).run(sender = admin)
    scenario.verify_equal(registry.data.collections_public_key, collections_key.public_key)

    # Test onchain views
    scenario.h2("Test views")

    is_reg_param = sp.set([items_tokens.address])

    # Private.
    registry.manage_collections([sp.variant("add_private", manage_private_params)]).run(sender = admin)
    scenario.verify_equal(registry.is_registered(is_reg_param), is_reg_param)
    scenario.verify_equal(registry.get_collection_info(items_tokens.address).collection_type, token_registry_contract.collectionPrivate)
    scenario.verify_equal(registry.get_royalties_type(items_tokens.address), 1)
    scenario.verify(~sp.is_failing(registry.check_registered(is_reg_param)))
    scenario.verify_equal(registry.is_private_owner_or_collab(sp.record(address=bob.address, collection=items_tokens.address)), sp.bounded("owner"))
    scenario.verify(sp.is_failing(registry.is_private_owner_or_collab(sp.record(address=alice.address, collection=items_tokens.address))))
    registry.manage_collections([sp.variant("remove", [items_tokens.address])]).run(sender = admin)
    scenario.verify_equal(registry.is_registered(is_reg_param), sp.set([]))
    scenario.verify(sp.is_failing(registry.get_collection_info(items_tokens.address)))
    scenario.verify(sp.is_failing(registry.get_royalties_type(items_tokens.address)))
    scenario.verify(sp.is_failing(registry.check_registered(is_reg_param)))
    scenario.verify(sp.is_failing(registry.is_private_owner_or_collab(sp.record(address=bob.address, collection=items_tokens.address))))
    scenario.verify(sp.is_failing(registry.is_private_owner_or_collab(sp.record(address=alice.address, collection=items_tokens.address))))

    # Public.
    registry.manage_collections([sp.variant("add_public", manage_public_params)]).run(sender = admin)
    scenario.verify_equal(registry.is_registered(is_reg_param), is_reg_param)
    scenario.verify_equal(registry.get_collection_info(items_tokens.address).collection_type, token_registry_contract.collectionPublic)
    scenario.verify_equal(registry.get_royalties_type(items_tokens.address), 1)
    scenario.verify(~sp.is_failing(registry.check_registered(is_reg_param)))
    scenario.verify(sp.is_failing(registry.is_private_owner_or_collab(sp.record(address=bob.address, collection=items_tokens.address))))
    scenario.verify(sp.is_failing(registry.is_private_owner_or_collab(sp.record(address=alice.address, collection=items_tokens.address))))
    registry.manage_collections([sp.variant("remove", [items_tokens.address])]).run(sender = admin)
    scenario.verify_equal(registry.is_registered(is_reg_param), sp.set([]))
    scenario.verify(sp.is_failing(registry.get_collection_info(items_tokens.address)))
    scenario.verify(sp.is_failing(registry.get_royalties_type(items_tokens.address)))
    scenario.verify(sp.is_failing(registry.check_registered(is_reg_param)))

    # Trusted.
    registry.manage_collections([sp.variant("add_trusted", manage_trusted_params)]).run(sender = bob)
    scenario.verify_equal(registry.is_registered(is_reg_param), is_reg_param)
    scenario.verify_equal(registry.get_collection_info(items_tokens.address).collection_type, token_registry_contract.collectionTrusted)
    scenario.verify_equal(registry.get_royalties_type(items_tokens.address), 1)
    scenario.verify(~sp.is_failing(registry.check_registered(is_reg_param)))
    scenario.verify(sp.is_failing(registry.is_private_owner_or_collab(sp.record(address=bob.address, collection=items_tokens.address))))
    scenario.verify(sp.is_failing(registry.is_private_owner_or_collab(sp.record(address=alice.address, collection=items_tokens.address))))
    registry.manage_collections([sp.variant("remove", [items_tokens.address])]).run(sender = admin)
    scenario.verify_equal(registry.is_registered(is_reg_param), sp.set([]))
    scenario.verify(sp.is_failing(registry.get_collection_info(items_tokens.address)))
    scenario.verify(sp.is_failing(registry.get_royalties_type(items_tokens.address)))
    scenario.verify(sp.is_failing(registry.check_registered(is_reg_param)))

    # Test trusted validation
    scenario.h2("Test signing")

    scenario.verify_equal(registry.get_collections_public_key(), registry.data.collections_public_key)

    # Royalties and collections keys.
    scenario.verify_equal(registry.get_collections_public_key(), collections_key.public_key)

    scenario.h2("Test signed royalties and collections")

    # Collections
    collection_signed_valid1 = token_registry_contract.signCollection(sp.record(collection=items_tokens.address, royalties_type=1), collections_key.secret_key)
    manage_trusted_valid1 = { items_tokens.address: sp.record(signature = collection_signed_valid1, royalties_type = 1) }

    collection_signed_valid2 = token_registry_contract.signCollection(sp.record(collection=items_tokens_v2.address, royalties_type=2), collections_key.secret_key)
    manage_trusted_valid2 = { items_tokens_v2.address: sp.record(signature = collection_signed_valid2, royalties_type = 2) }

    collection_signed_valid3 = token_registry_contract.signCollection(sp.record(collection=other_tokens.address, royalties_type=0), collections_key.secret_key)
    manage_trusted_valid3 = { other_tokens.address: sp.record(signature = collection_signed_valid3, royalties_type = 0) }

    collection_signed_invalid = token_registry_contract.signCollection(sp.record(collection=minter.address, royalties_type=0), royalties_key.secret_key)
    manage_trusted_invalid = { minter.address: sp.record(signature = collection_signed_invalid, royalties_type = 0) }

    registry.manage_collections([sp.variant("add_trusted", manage_trusted_valid1)]).run(sender = bob)
    registry.manage_collections([sp.variant("add_trusted", manage_trusted_valid2)]).run(sender = bob)
    registry.manage_collections([sp.variant("add_trusted", manage_trusted_valid3)]).run(sender = bob)
    registry.manage_collections([sp.variant("add_trusted", manage_trusted_invalid)]).run(sender = bob, valid=False, exception="INVALID_SIGNATURE")

    scenario.table_of_contents()
