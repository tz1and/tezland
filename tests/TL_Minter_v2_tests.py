import smartpy as sp

minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter_v2.py")
tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")

@sp.add_test(name = "TL_Minter_v2_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("Minter v2 Tests")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h1("Accounts")
    scenario.show([admin, alice, bob])

    # create a FA2 contract for testing
    scenario.h1("Create test env")
    items_tokens = tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    # create minter contract
    scenario.h1("Test Minter")
    minter = minter_contract.TL_Minter(admin.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    # set items_tokens and places_tokens administrator to minter contract
    items_tokens.transfer_administrator(minter.address).run(sender = admin)
    minter.accept_fa2_administrator([items_tokens.address]).run(sender = admin)

    # test public collections
    scenario.h2("Public Collections")

    # test adding public collections
    scenario.h3("manage_public_collection")

    minter.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    minter.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = alice, valid = False, exception = "NOT_PERMITTED")

    # add permission for alice
    minter.manage_permissions([sp.variant("add_permissions", [alice.address])]).run(sender = admin)
    minter.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    minter.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = alice)
    scenario.verify(minter.data.public_collections.contains(items_tokens.address))

    # public collection can't be private
    minter.manage_private_collections([sp.variant("add_collections", [sp.record(contract = items_tokens.address, owner = bob.address)])]).run(sender = admin, valid = False, exception = "PUBLIC_PRIVATE")

    minter.manage_public_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    minter.manage_public_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)
    scenario.verify(~minter.data.public_collections.contains(items_tokens.address))

    # only unpaused
    minter.set_paused(True).run(sender = admin)
    minter.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")
    minter.set_paused(False).run(sender = admin)

    minter.manage_permissions([sp.variant("remove_permissions", [alice.address])]).run(sender = admin)

    # test Item minting
    scenario.h3("mint_public")

    minter.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = admin)

    minter.mint_public(collection = minter.address,
        to_ = bob.address,
        amount = 4,
        royalties = 250,
        contributors = [ sp.record(address=bob.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob, valid = False, exception = "INVALID_COLLECTION")

    minter.mint_public(collection = items_tokens.address,
        to_ = bob.address,
        amount = 4,
        royalties = 250,
        contributors = [ sp.record(address=bob.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    minter.mint_public(collection = items_tokens.address,
        to_ = alice.address,
        amount = 25,
        royalties = 250,
        contributors = [ sp.record(address=alice.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)

    minter.set_paused(True).run(sender = admin)

    minter.mint_public(collection = items_tokens.address,
        to_ = alice.address,
        amount = 25,
        royalties = 250,
        contributors = [ sp.record(address=alice.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice, valid = False)

    minter.set_paused(False).run(sender = admin)
    minter.manage_public_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)

    # test private collections
    scenario.h2("Private Collections")

    # test adding private collections
    scenario.h3("manage_private_collections")

    manage_private_params = sp.record(contract = items_tokens.address, owner = bob.address)
    minter.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    minter.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = alice, valid = False, exception = "NOT_PERMITTED")

    # add permission for alice
    minter.manage_permissions([sp.variant("add_permissions", [alice.address])]).run(sender = admin)
    minter.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    minter.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = alice)
    scenario.verify(minter.data.private_collections.contains(items_tokens.address))

    # private collection can't be public
    minter.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = admin, valid = False, exception = "PUBLIC_PRIVATE")

    minter.manage_private_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = bob, valid = False, exception = "NOT_PERMITTED")
    minter.manage_private_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)
    scenario.verify(~minter.data.private_collections.contains(items_tokens.address))

    # only unpaused
    minter.set_paused(True).run(sender = admin)
    minter.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")
    minter.set_paused(False).run(sender = admin)

    minter.manage_permissions([sp.variant("remove_permissions", [alice.address])]).run(sender = admin)

    scenario.h3("manage_collaborators")

    minter.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = admin)

    manager_collaborators_params = sp.record(collection = items_tokens.address, collaborators = [alice.address])
    minter.manage_collaborators([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = admin, valid = False, exception = "ONLY_OWNER")
    minter.manage_collaborators([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = alice, valid = False, exception = "ONLY_OWNER")
    scenario.verify(~minter.data.collaborators.contains(sp.record(collection = items_tokens.address, collaborator = alice.address)))
    minter.manage_collaborators([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = bob)
    scenario.verify(minter.data.collaborators.contains(sp.record(collection = items_tokens.address, collaborator = alice.address)))

    minter.manage_collaborators([sp.variant("remove_collaborators", manager_collaborators_params)]).run(sender = admin, valid = False, exception = "ONLY_OWNER")
    minter.manage_collaborators([sp.variant("remove_collaborators", manager_collaborators_params)]).run(sender = alice, valid = False, exception = "ONLY_OWNER")
    minter.manage_collaborators([sp.variant("remove_collaborators", manager_collaborators_params)]).run(sender = bob)
    scenario.verify(~minter.data.collaborators.contains(sp.record(collection = items_tokens.address, collaborator = alice.address)))

    minter.set_paused(True).run(sender = admin)
    minter.manage_collaborators([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = bob, valid = False, exception = "ONLY_UNPAUSED")
    minter.set_paused(False).run(sender = admin)

    minter.manage_private_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)

    # test Item minting
    scenario.h3("mint_private")

    minter.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = admin)

    minter.mint_private(collection = minter.address,
        to_ = bob.address,
        amount = 4,
        royalties = 250,
        contributors = [ sp.record(address=bob.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob, valid = False, exception = "INVALID_COLLECTION")

    minter.mint_private(collection = items_tokens.address,
        to_ = bob.address,
        amount = 4,
        royalties = 250,
        contributors = [ sp.record(address=bob.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    # add alice as collaborator
    minter.manage_collaborators([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = bob)
    minter.mint_private(collection = items_tokens.address,
        to_ = alice.address,
        amount = 25,
        royalties = 250,
        contributors = [ sp.record(address=alice.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)
    minter.manage_collaborators([sp.variant("remove_collaborators", manager_collaborators_params)]).run(sender = bob)

    minter.mint_private(collection = items_tokens.address,
        to_ = alice.address,
        amount = 25,
        royalties = 250,
        contributors = [ sp.record(address=alice.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice, valid = False, exception = "ONLY_OWNER_OR_COLLABORATOR")

    minter.set_paused(True).run(sender = admin)

    minter.mint_private(collection = items_tokens.address,
        to_ = alice.address,
        amount = 25,
        royalties = 250,
        contributors = [ sp.record(address=alice.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice, valid = False)

    minter.set_paused(False).run(sender = admin)
    minter.manage_private_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)

    scenario.h3("transfer_private_ownership")

    minter.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = admin)

    minter.transfer_private_ownership(sp.record(collection = items_tokens.address, new_owner = alice.address)).run(sender = admin, valid = False, exception = "ONLY_OWNER")
    minter.transfer_private_ownership(sp.record(collection = items_tokens.address, new_owner = alice.address)).run(sender = alice, valid = False, exception = "ONLY_OWNER")
    scenario.verify(minter.data.private_collections[items_tokens.address].owner == bob.address)
    minter.transfer_private_ownership(sp.record(collection = items_tokens.address, new_owner = alice.address)).run(sender = bob)
    scenario.verify(minter.data.private_collections[items_tokens.address].proposed_owner == sp.some(alice.address))
    minter.accept_private_ownership(items_tokens.address).run(sender = admin, valid = False, exception = "NOT_PROPOSED_OWNER")
    minter.accept_private_ownership(items_tokens.address).run(sender = bob, valid = False, exception = "NOT_PROPOSED_OWNER")
    minter.accept_private_ownership(items_tokens.address).run(sender = alice)
    scenario.verify(minter.data.private_collections[items_tokens.address].owner == alice.address)
    scenario.verify(minter.data.private_collections[items_tokens.address].proposed_owner == sp.none)

    minter.accept_private_ownership(items_tokens.address).run(sender = admin, valid = False, exception = "NO_OWNER_TRANSFER")
    minter.accept_private_ownership(items_tokens.address).run(sender = bob, valid = False, exception = "NO_OWNER_TRANSFER")
    minter.accept_private_ownership(items_tokens.address).run(sender = alice, valid = False, exception = "NO_OWNER_TRANSFER")

    minter.set_paused(True).run(sender = admin)
    minter.transfer_private_ownership(sp.record(collection = items_tokens.address, new_owner = bob.address)).run(sender = alice, valid = False, exception = "ONLY_UNPAUSED")
    minter.accept_private_ownership(items_tokens.address).run(sender = admin, valid = False, exception = "ONLY_UNPAUSED")
    minter.set_paused(False).run(sender = admin)

    minter.manage_private_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)

    scenario.h3("update_private_metadata")

    minter.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = admin)

    invalid_metadata_uri = sp.utils.bytes_of_string("ipf://QmbWqxBEKC3P8tqsKc98xmWNzrzDtRLMiMPL8")
    valid_metadata_uri = sp.utils.bytes_of_string("ipfs://QmbWqxBEKC3P8tqsKc98xmWNzrzDtRLMiMPL8wBuTGsMnR")

    minter.update_private_metadata(sp.record(collection = items_tokens.address, metadata_uri = valid_metadata_uri)).run(sender = admin, valid = False, exception = "ONLY_OWNER")
    minter.update_private_metadata(sp.record(collection = items_tokens.address, metadata_uri = valid_metadata_uri)).run(sender = alice, valid = False, exception = "ONLY_OWNER")
    minter.update_private_metadata(sp.record(collection = items_tokens.address, metadata_uri = invalid_metadata_uri)).run(sender = bob, valid = False, exception = "INVALID_METADATA")

    scenario.verify(items_tokens.data.metadata[""] == sp.utils.bytes_of_string("https://example.com"))
    minter.update_private_metadata(sp.record(collection = items_tokens.address, metadata_uri = valid_metadata_uri)).run(sender = bob)
    scenario.verify(items_tokens.data.metadata[""] == valid_metadata_uri)

    minter.set_paused(True).run(sender = admin)
    minter.update_private_metadata(sp.record(collection = items_tokens.address, metadata_uri = valid_metadata_uri)).run(sender = bob, valid = False, exception = "ONLY_UNPAUSED")
    minter.set_paused(False).run(sender = admin)

    minter.manage_private_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)

    # test get_item_royalties view
    #scenario.h2("get_item_royalties")
    #scenario.p("It's a view")
    #view_res = minter.get_item_royalties(sp.nat(0))
    #scenario.verify(view_res.royalties == 250)
    #scenario.verify(view_res.creator == bob.address)

    # test pause_fa2
    scenario.h2("pause_fa2")

    # check tokens are unpaused to begin with
    scenario.verify(items_tokens.data.paused == False)

    minter.pause_fa2(sp.record(tokens = [items_tokens.address], new_paused = True)).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    minter.pause_fa2(sp.record(tokens = [items_tokens.address], new_paused = True)).run(sender = admin)

    # check tokens are paused
    scenario.verify(items_tokens.data.paused == True)

    minter.pause_fa2(sp.record(tokens = [items_tokens.address], new_paused = False)).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    minter.pause_fa2(sp.record(tokens = [items_tokens.address], new_paused = False)).run(sender = admin)

    # check tokens are unpaused
    scenario.verify(items_tokens.data.paused == False)

    #  test clear_adhoc_operators_fa2
    scenario.h2("clear_adhoc_operators_fa2")

    items_tokens.update_adhoc_operators(sp.variant("add_adhoc_operators", [
        sp.record(operator=minter.address, token_id=0),
        sp.record(operator=minter.address, token_id=1),
        sp.record(operator=minter.address, token_id=2),
        sp.record(operator=minter.address, token_id=3),
    ])).run(sender = alice)

    scenario.verify(sp.len(items_tokens.data.adhoc_operators) == 4)

    minter.clear_adhoc_operators_fa2([items_tokens.address]).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    minter.clear_adhoc_operators_fa2([items_tokens.address]).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    minter.clear_adhoc_operators_fa2([items_tokens.address]).run(sender = admin)

    scenario.verify(sp.len(items_tokens.data.adhoc_operators) == 0)

    scenario.table_of_contents()
