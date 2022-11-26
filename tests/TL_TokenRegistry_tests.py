import smartpy as sp

token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter_v2.py")
tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")


class TestSignedRoyaltiesAndCollections(sp.Contract):
    def __init__(self, registry):
        self.init_storage(
            registry = sp.set_type_expr(registry, sp.TAddress)
        )

    @sp.entry_point
    def testSignedCollection(self, params):
        sp.set_type(params, sp.TMap(sp.TAddress, token_registry_contract.t_collection_signed))

        #sp.trace(params)

        res = token_registry_contract.getTokenRegistryInfoSigned(self.data.registry, params.keys(), sp.some(params))

        with sp.for_("key", params.keys()) as key:
            sp.verify(res.contains(key))
            sp.verify(res[key] == True)


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
    items_tokens = tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

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

    manage_public_params = sp.record(contract = items_tokens.address, royalties_version = 1)
    manage_private_params = sp.record(contract = items_tokens.address, owner = bob.address, royalties_version = 1)

    # test adding public collections
    scenario.h3("manage_public_collection")

    registry.manage_public_collections([sp.variant("add", [manage_public_params])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    registry.manage_public_collections([sp.variant("add", [manage_public_params])]).run(sender = alice, valid = False, exception = "NOT_PERMITTED")

    # add permission for alice
    registry.manage_permissions([sp.variant("add_permissions", [alice.address])]).run(sender = admin)
    registry.manage_public_collections([sp.variant("add", [manage_public_params])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    registry.manage_public_collections([sp.variant("add", [manage_public_params])]).run(sender = alice)
    scenario.verify(registry.data.public_collections.contains(items_tokens.address))

    # public collection can't be private
    registry.manage_private_collections([sp.variant("add", [manage_private_params])]).run(sender = admin, valid = False, exception = "PUBLIC_PRIVATE")

    registry.manage_public_collections([sp.variant("remove", [items_tokens.address])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    registry.manage_public_collections([sp.variant("remove", [items_tokens.address])]).run(sender = admin)
    scenario.verify(~registry.data.public_collections.contains(items_tokens.address))

    # only unpaused
    registry.update_settings([sp.variant("paused", True)]).run(sender = admin)
    registry.manage_public_collections([sp.variant("add", [manage_public_params])]).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")
    registry.update_settings([sp.variant("paused", False)]).run(sender = admin)

    registry.manage_permissions([sp.variant("remove_permissions", [alice.address])]).run(sender = admin)

    # test private collections
    scenario.h2("Private Collections")

    # test adding private collections
    scenario.h3("manage_private_collections")

    registry.manage_private_collections([sp.variant("add", [manage_private_params])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    registry.manage_private_collections([sp.variant("add", [manage_private_params])]).run(sender = alice, valid = False, exception = "NOT_PERMITTED")

    # add permission for alice
    registry.manage_permissions([sp.variant("add_permissions", [alice.address])]).run(sender = admin)
    registry.manage_private_collections([sp.variant("add", [manage_private_params])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    registry.manage_private_collections([sp.variant("add", [manage_private_params])]).run(sender = alice)
    scenario.verify(registry.data.private_collections.contains(items_tokens.address))

    # private collection can't be public
    registry.manage_public_collections([sp.variant("add", [manage_public_params])]).run(sender = admin, valid = False, exception = "PUBLIC_PRIVATE")

    registry.manage_private_collections([sp.variant("remove", [items_tokens.address])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    registry.manage_private_collections([sp.variant("remove", [items_tokens.address])]).run(sender = admin)
    scenario.verify(~registry.data.private_collections.contains(items_tokens.address))

    # only unpaused
    registry.update_settings([sp.variant("paused", True)]).run(sender = admin)
    registry.manage_private_collections([sp.variant("add", [manage_private_params])]).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")
    registry.update_settings([sp.variant("paused", False)]).run(sender = admin)

    registry.manage_permissions([sp.variant("remove_permissions", [alice.address])]).run(sender = admin)

    scenario.h3("manage_collaborators")

    registry.manage_private_collections([sp.variant("add", [manage_private_params])]).run(sender = admin)

    manager_collaborators_params = sp.record(collection = items_tokens.address, collaborators = [alice.address])
    registry.manage_collaborators([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = admin, valid = False, exception = "ONLY_OWNER")
    registry.manage_collaborators([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = alice, valid = False, exception = "ONLY_OWNER")
    scenario.verify(~registry.data.collaborators.contains(sp.record(collection = items_tokens.address, collaborator = alice.address)))
    registry.manage_collaborators([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = bob)
    scenario.verify(registry.data.collaborators.contains(sp.record(collection = items_tokens.address, collaborator = alice.address)))

    registry.manage_collaborators([sp.variant("remove_collaborators", manager_collaborators_params)]).run(sender = admin, valid = False, exception = "ONLY_OWNER")
    registry.manage_collaborators([sp.variant("remove_collaborators", manager_collaborators_params)]).run(sender = alice, valid = False, exception = "ONLY_OWNER")
    registry.manage_collaborators([sp.variant("remove_collaborators", manager_collaborators_params)]).run(sender = bob)
    scenario.verify(~registry.data.collaborators.contains(sp.record(collection = items_tokens.address, collaborator = alice.address)))

    registry.update_settings([sp.variant("paused", True)]).run(sender = admin)
    registry.manage_collaborators([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = bob, valid = False, exception = "ONLY_UNPAUSED")
    registry.update_settings([sp.variant("paused", False)]).run(sender = admin)

    registry.manage_private_collections([sp.variant("remove", [items_tokens.address])]).run(sender = admin)

    scenario.h3("transfer_private_ownership")

    registry.manage_private_collections([sp.variant("add", [manage_private_params])]).run(sender = admin)

    registry.transfer_private_ownership(sp.record(collection = items_tokens.address, new_owner = alice.address)).run(sender = admin, valid = False, exception = "ONLY_OWNER")
    registry.transfer_private_ownership(sp.record(collection = items_tokens.address, new_owner = alice.address)).run(sender = alice, valid = False, exception = "ONLY_OWNER")
    scenario.verify(registry.data.private_collections[items_tokens.address].owner == bob.address)
    registry.transfer_private_ownership(sp.record(collection = items_tokens.address, new_owner = alice.address)).run(sender = bob)
    scenario.verify(registry.data.private_collections[items_tokens.address].proposed_owner == sp.some(alice.address))
    registry.accept_private_ownership(items_tokens.address).run(sender = admin, valid = False, exception = "NOT_PROPOSED_OWNER")
    registry.accept_private_ownership(items_tokens.address).run(sender = bob, valid = False, exception = "NOT_PROPOSED_OWNER")
    registry.accept_private_ownership(items_tokens.address).run(sender = alice)
    scenario.verify(registry.data.private_collections[items_tokens.address].owner == alice.address)
    scenario.verify(registry.data.private_collections[items_tokens.address].proposed_owner == sp.none)

    registry.accept_private_ownership(items_tokens.address).run(sender = admin, valid = False, exception = "NOT_PROPOSED_OWNER")
    registry.accept_private_ownership(items_tokens.address).run(sender = bob, valid = False, exception = "NOT_PROPOSED_OWNER")
    registry.accept_private_ownership(items_tokens.address).run(sender = alice, valid = False, exception = "NOT_PROPOSED_OWNER")

    registry.update_settings([sp.variant("paused", True)]).run(sender = admin)
    registry.transfer_private_ownership(sp.record(collection = items_tokens.address, new_owner = bob.address)).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")
    registry.accept_private_ownership(items_tokens.address).run(sender = admin, valid = False, exception = "ONLY_UNPAUSED")
    registry.update_settings([sp.variant("paused", False)]).run(sender = admin)

    registry.manage_private_collections([sp.variant("remove", [items_tokens.address])]).run(sender = admin)

    # Update settings
    registry.update_settings([sp.variant("paused", False)]).run(sender=alice, valid=False, exception="ONLY_ADMIN")
    registry.update_settings([sp.variant("paused", False)]).run(sender=bob, valid=False, exception="ONLY_ADMIN")

    scenario.verify_equal(registry.data.collections_public_key, collections_key.public_key)
    registry.update_settings([sp.variant("collections_public_key", royalties_key.public_key)]).run(sender = admin)
    scenario.verify_equal(registry.data.collections_public_key, royalties_key.public_key)
    registry.update_settings([sp.variant("collections_public_key", collections_key.public_key)]).run(sender = admin)
    scenario.verify_equal(registry.data.collections_public_key, collections_key.public_key)

    # Test onchain views
    scenario.h2("Test views")

    is_reg_param = [items_tokens.address]

    # Registered.
    # TODO: test is_private_owner_or_collab
    registry.manage_private_collections([sp.variant("add", [manage_private_params])]).run(sender = admin)
    scenario.verify_equal(registry.is_private_collection([items_tokens.address]), {items_tokens.address: True})
    scenario.verify_equal(registry.is_registered(is_reg_param).result_map, {items_tokens.address: True})
    scenario.verify_equal(registry.is_private_owner(sp.record(address=bob.address, collection=items_tokens.address)), True)
    scenario.verify_equal(registry.is_private_owner(sp.record(address=alice.address, collection=items_tokens.address)), False)
    registry.manage_private_collections([sp.variant("remove", [items_tokens.address])]).run(sender = admin)
    scenario.verify_equal(registry.is_private_collection([items_tokens.address]), {items_tokens.address: False})
    scenario.verify_equal(registry.is_registered(is_reg_param).result_map, {items_tokens.address: False})
    scenario.verify(sp.is_failing(registry.is_private_owner(sp.record(address=bob.address, collection=items_tokens.address))))
    scenario.verify(sp.is_failing(registry.is_private_owner(sp.record(address=alice.address, collection=items_tokens.address))))

    registry.manage_public_collections([sp.variant("add", [manage_public_params])]).run(sender = admin)
    scenario.verify_equal(registry.is_public_collection([items_tokens.address]), {items_tokens.address: True})
    scenario.verify_equal(registry.is_registered(is_reg_param).result_map, {items_tokens.address: True})
    scenario.verify(sp.is_failing(registry.is_private_owner(sp.record(address=bob.address, collection=items_tokens.address))))
    scenario.verify(sp.is_failing(registry.is_private_owner(sp.record(address=alice.address, collection=items_tokens.address))))
    registry.manage_public_collections([sp.variant("remove", [items_tokens.address])]).run(sender = admin)
    scenario.verify_equal(registry.is_public_collection([items_tokens.address]), {items_tokens.address: False})
    scenario.verify_equal(registry.is_registered(is_reg_param).result_map, {items_tokens.address: False})

    registry_info = registry.is_registered(is_reg_param)
    #scenario.verify_equal(registry_info.merkle_root, registry.data.collections_merkle_root)
    scenario.verify_equal(registry_info.public_key, registry.data.collections_public_key)

    # Royalties type.
    registry.manage_public_collections([sp.variant("add", [manage_public_params])]).run(sender = admin)
    royalties_info = registry.get_royalties_type(items_tokens.address)
    scenario.verify_equal(royalties_info, sp.nat(1))
    registry.manage_public_collections([sp.variant("remove", [items_tokens.address])]).run(sender = admin)

    # Royalties and collections keys.
    scenario.verify_equal(registry.get_collections_public_key(), collections_key.public_key)

    scenario.h2("Test signed royalties and collections")

    test_signed = TestSignedRoyaltiesAndCollections(
        registry = registry.address)
    scenario += test_signed

    # Collections
    collection_signed_valid1 = token_registry_contract.sign_collection(items_tokens.address, collections_key.secret_key)
    collection_signed_valid2 = token_registry_contract.sign_collection(minter.address, collections_key.secret_key)
    collection_signed_invalid = token_registry_contract.sign_collection(items_tokens.address, royalties_key.secret_key)

    test_signed.testSignedCollection({ items_tokens.address: collection_signed_valid1, minter.address: collection_signed_valid2 }).run(sender=admin)
    test_signed.testSignedCollection({ items_tokens.address: collection_signed_invalid }).run(sender=admin, valid=False, exception="INVALID_SIGNATURE")

    scenario.table_of_contents()
