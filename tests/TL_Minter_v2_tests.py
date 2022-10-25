import smartpy as sp

token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
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

    scenario.h2("tokens")
    items_tokens = tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    # create token_registry contract
    scenario.h1("Test Minter")
    token_registry = token_registry_contract.TL_TokenRegistry(admin.address,
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

    # test Item minting
    scenario.h3("mint_public")

    token_registry.manage_public_collections([sp.variant("add_collections", [items_tokens.address])]).run(sender = admin)

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

    minter.update_settings([sp.variant("paused", True)]).run(sender = admin)

    minter.mint_public(collection = items_tokens.address,
        to_ = alice.address,
        amount = 25,
        royalties = 250,
        contributors = [ sp.record(address=alice.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice, valid = False)

    minter.update_settings([sp.variant("paused", False)]).run(sender = admin)
    token_registry.manage_public_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)

    # test private collections
    scenario.h2("Private Collections")

    # test Item minting
    scenario.h3("mint_private")

    manage_private_params = sp.record(contract = items_tokens.address, owner = bob.address)
    manager_collaborators_params = sp.record(collection = items_tokens.address, collaborators = [alice.address])
    token_registry.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = admin)

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
    token_registry.manage_collaborators([sp.variant("add_collaborators", manager_collaborators_params)]).run(sender = bob)
    minter.mint_private(collection = items_tokens.address,
        to_ = alice.address,
        amount = 25,
        royalties = 250,
        contributors = [ sp.record(address=alice.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)
    token_registry.manage_collaborators([sp.variant("remove_collaborators", manager_collaborators_params)]).run(sender = bob)

    minter.mint_private(collection = items_tokens.address,
        to_ = alice.address,
        amount = 25,
        royalties = 250,
        contributors = [ sp.record(address=alice.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice, valid = False, exception = "ONLY_OWNER_OR_COLLABORATOR")

    minter.update_settings([sp.variant("paused", True)]).run(sender = admin)

    minter.mint_private(collection = items_tokens.address,
        to_ = alice.address,
        amount = 25,
        royalties = 250,
        contributors = [ sp.record(address=alice.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice, valid = False)

    minter.update_settings([sp.variant("paused", False)]).run(sender = admin)
    token_registry.manage_private_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)

    scenario.h3("update_private_metadata")

    token_registry.manage_private_collections([sp.variant("add_collections", [manage_private_params])]).run(sender = admin)

    invalid_metadata_uri = sp.utils.bytes_of_string("ipf://QmbWqxBEKC3P8tqsKc98xmWNzrzDtRLMiMPL8")
    valid_metadata_uri = sp.utils.bytes_of_string("ipfs://QmbWqxBEKC3P8tqsKc98xmWNzrzDtRLMiMPL8wBuTGsMnR")

    minter.update_private_metadata(sp.record(collection = items_tokens.address, metadata_uri = valid_metadata_uri)).run(sender = admin, valid = False, exception = "ONLY_OWNER")
    minter.update_private_metadata(sp.record(collection = items_tokens.address, metadata_uri = valid_metadata_uri)).run(sender = alice, valid = False, exception = "ONLY_OWNER")
    minter.update_private_metadata(sp.record(collection = items_tokens.address, metadata_uri = invalid_metadata_uri)).run(sender = bob, valid = False, exception = "INVALID_METADATA")

    scenario.verify(items_tokens.data.metadata[""] == sp.utils.bytes_of_string("https://example.com"))
    minter.update_private_metadata(sp.record(collection = items_tokens.address, metadata_uri = valid_metadata_uri)).run(sender = bob)
    scenario.verify(items_tokens.data.metadata[""] == valid_metadata_uri)

    minter.update_settings([sp.variant("paused", True)]).run(sender = admin)
    minter.update_private_metadata(sp.record(collection = items_tokens.address, metadata_uri = valid_metadata_uri)).run(sender = bob, valid = False, exception = "ONLY_UNPAUSED")
    minter.update_settings([sp.variant("paused", False)]).run(sender = admin)

    token_registry.manage_private_collections([sp.variant("remove_collections", [items_tokens.address])]).run(sender = admin)

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
        sp.record(operator=token_registry.address, token_id=0),
        sp.record(operator=token_registry.address, token_id=1),
        sp.record(operator=token_registry.address, token_id=2),
        sp.record(operator=token_registry.address, token_id=3),
    ])).run(sender = alice)

    scenario.verify(sp.len(items_tokens.data.adhoc_operators) == 4)

    minter.clear_adhoc_operators_fa2([items_tokens.address]).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    minter.clear_adhoc_operators_fa2([items_tokens.address]).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    minter.clear_adhoc_operators_fa2([items_tokens.address]).run(sender = admin)

    scenario.verify(sp.len(items_tokens.data.adhoc_operators) == 0)

    scenario.table_of_contents()
