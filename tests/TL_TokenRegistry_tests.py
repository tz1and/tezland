import smartpy as sp

token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter_v2.py")
tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")


@sp.add_test(name = "TL_TokenRegistry_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("TokenRegistry Tests")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h1("Accounts")
    scenario.show([admin, alice, bob])

    # create a FA2 contract for testing
    scenario.h1("Create test env")

    scenario.h2("tokens")
    items_tokens = tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    # create token_registry contract
    scenario.h1("Test TokenRegistry")
    token_registry = token_registry_contract.TL_TokenRegistry(admin.address,
        sp.bytes("0x00"), sp.bytes("0x00"),
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += token_registry

    scenario.h2("minter")
    minter = minter_contract.TL_Minter(admin.address, token_registry.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    # set items_tokens administrator to minter contract
    items_tokens.transfer_administrator(minter.address).run(sender = admin)
    minter.accept_fa2_administrator([items_tokens.address]).run(sender = admin)

    # test public collections
    scenario.h2("Public Collections")

    # test adding public collections
    scenario.h3("manage_public_collection")

    token_registry.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    token_registry.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = alice, valid = False, exception = "NOT_PERMITTED")

    # add permission for alice
    token_registry.manage_permissions([sp.variant("add_permissions", [alice.address])]).run(sender = admin)
    token_registry.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    token_registry.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = alice)
    scenario.verify(token_registry.data.public_collections.contains(items_tokens.address))

    # public collection can't be private
    token_registry.manage_private_collections([sp.variant("add_collections", [sp.record(contract = items_tokens.address, owner = bob.address)])]).run(sender = admin, valid = False, exception = "PUBLIC_PRIVATE")

    token_registry.manage_public_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    token_registry.manage_public_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)
    scenario.verify(~token_registry.data.public_collections.contains(items_tokens.address))

    # only unpaused
    token_registry.update_settings([sp.variant("paused", True)]).run(sender = admin)
    token_registry.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")
    token_registry.update_settings([sp.variant("paused", False)]).run(sender = admin)

    token_registry.manage_permissions([sp.variant("remove_permissions", [alice.address])]).run(sender = admin)

    # test private collections
    scenario.h2("Private Collections")

    # test adding private collections
    scenario.h3("manage_private_collections")

    manage_private_params = sp.record(contract = items_tokens.address, owner = bob.address)
    token_registry.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    token_registry.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = alice, valid = False, exception = "NOT_PERMITTED")

    # add permission for alice
    token_registry.manage_permissions([sp.variant("add_permissions", [alice.address])]).run(sender = admin)
    token_registry.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    token_registry.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = alice)
    scenario.verify(token_registry.data.private_collections.contains(items_tokens.address))

    # private collection can't be public
    token_registry.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = admin, valid = False, exception = "PUBLIC_PRIVATE")

    token_registry.manage_private_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    token_registry.manage_private_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)
    scenario.verify(~token_registry.data.private_collections.contains(items_tokens.address))

    # only unpaused
    token_registry.update_settings([sp.variant("paused", True)]).run(sender = admin)
    token_registry.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")
    token_registry.update_settings([sp.variant("paused", False)]).run(sender = admin)

    token_registry.manage_permissions([sp.variant("remove_permissions", [alice.address])]).run(sender = admin)

    scenario.h3("manage_collaborators")

    token_registry.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = admin)

    manager_collaborators_params = sp.record(collection = items_tokens.address, collaborators = [alice.address])
    token_registry.manage_collaborators([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = admin, valid = False, exception = "ONLY_OWNER")
    token_registry.manage_collaborators([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = alice, valid = False, exception = "ONLY_OWNER")
    scenario.verify(~token_registry.data.collaborators.contains(sp.record(collection = items_tokens.address, collaborator = alice.address)))
    token_registry.manage_collaborators([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = bob)
    scenario.verify(token_registry.data.collaborators.contains(sp.record(collection = items_tokens.address, collaborator = alice.address)))

    token_registry.manage_collaborators([sp.variant("remove_collaborators", manager_collaborators_params)]).run(sender = admin, valid = False, exception = "ONLY_OWNER")
    token_registry.manage_collaborators([sp.variant("remove_collaborators", manager_collaborators_params)]).run(sender = alice, valid = False, exception = "ONLY_OWNER")
    token_registry.manage_collaborators([sp.variant("remove_collaborators", manager_collaborators_params)]).run(sender = bob)
    scenario.verify(~token_registry.data.collaborators.contains(sp.record(collection = items_tokens.address, collaborator = alice.address)))

    token_registry.update_settings([sp.variant("paused", True)]).run(sender = admin)
    token_registry.manage_collaborators([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = bob, valid = False, exception = "ONLY_UNPAUSED")
    token_registry.update_settings([sp.variant("paused", False)]).run(sender = admin)

    token_registry.manage_private_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)

    scenario.h3("transfer_private_ownership")

    token_registry.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = admin)

    token_registry.transfer_private_ownership(sp.record(collection = items_tokens.address, new_owner = alice.address)).run(sender = admin, valid = False, exception = "ONLY_OWNER")
    token_registry.transfer_private_ownership(sp.record(collection = items_tokens.address, new_owner = alice.address)).run(sender = alice, valid = False, exception = "ONLY_OWNER")
    scenario.verify(token_registry.data.private_collections[items_tokens.address].owner == bob.address)
    token_registry.transfer_private_ownership(sp.record(collection = items_tokens.address, new_owner = alice.address)).run(sender = bob)
    scenario.verify(token_registry.data.private_collections[items_tokens.address].proposed_owner == sp.some(alice.address))
    token_registry.accept_private_ownership(items_tokens.address).run(sender = admin, valid = False, exception = "NOT_PROPOSED_OWNER")
    token_registry.accept_private_ownership(items_tokens.address).run(sender = bob, valid = False, exception = "NOT_PROPOSED_OWNER")
    token_registry.accept_private_ownership(items_tokens.address).run(sender = alice)
    scenario.verify(token_registry.data.private_collections[items_tokens.address].owner == alice.address)
    scenario.verify(token_registry.data.private_collections[items_tokens.address].proposed_owner == sp.none)

    token_registry.accept_private_ownership(items_tokens.address).run(sender = admin, valid = False, exception = "NOT_PROPOSED_OWNER")
    token_registry.accept_private_ownership(items_tokens.address).run(sender = bob, valid = False, exception = "NOT_PROPOSED_OWNER")
    token_registry.accept_private_ownership(items_tokens.address).run(sender = alice, valid = False, exception = "NOT_PROPOSED_OWNER")

    token_registry.update_settings([sp.variant("paused", True)]).run(sender = admin)
    token_registry.transfer_private_ownership(sp.record(collection = items_tokens.address, new_owner = bob.address)).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")
    token_registry.accept_private_ownership(items_tokens.address).run(sender = admin, valid = False, exception = "ONLY_UNPAUSED")
    token_registry.update_settings([sp.variant("paused", False)]).run(sender = admin)

    token_registry.manage_private_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)

    # test get_item_royalties view
    #scenario.h2("get_item_royalties")
    #scenario.p("It's a view")
    #view_res = token_registry.get_item_royalties(sp.nat(0))
    #scenario.verify(view_res.royalties == 250)
    #scenario.verify(view_res.creator == bob.address)

    # Test onchain views
    scenario.h2("Test views")

    is_reg_param = sp.record(fa2_list = [items_tokens.address], merkle_proofs = {})

    token_registry.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = admin)
    scenario.verify_equal(token_registry.is_private_collection([items_tokens.address]), {items_tokens.address: True})
    scenario.verify_equal(token_registry.is_registered(is_reg_param), {items_tokens.address: True})
    token_registry.manage_private_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)
    scenario.verify_equal(token_registry.is_private_collection([items_tokens.address]), {items_tokens.address: False})
    scenario.verify_equal(token_registry.is_registered(is_reg_param), {items_tokens.address: False})

    token_registry.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = admin)
    scenario.verify_equal(token_registry.is_public_collection([items_tokens.address]), {items_tokens.address: True})
    scenario.verify_equal(token_registry.is_registered(is_reg_param), {items_tokens.address: True})
    token_registry.manage_public_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)
    scenario.verify_equal(token_registry.is_public_collection([items_tokens.address]), {items_tokens.address: False})
    scenario.verify_equal(token_registry.is_registered(is_reg_param), {items_tokens.address: False})

    # TODO: test is_private_owner etc views
    # TODO: test non-native tokens with merkle proof.

    scenario.table_of_contents()
