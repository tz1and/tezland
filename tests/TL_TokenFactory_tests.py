import smartpy as sp

token_factory_contract = sp.io.import_script_from_url("file:contracts/TL_TokenFactory.py")
token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter_v2.py")
tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")

@sp.add_test(name = "TL_TokenFactory_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("TokenFactory Tests")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h1("Accounts")
    scenario.show([admin, alice, bob])

    # create token_registry contract
    scenario.h1("Create test env")

    scenario.h2("TokenRegistry")
    token_registry = token_registry_contract.TL_TokenRegistry(admin.address,
        sp.bytes("0x00"), sp.bytes("0x00"),
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += token_registry

    scenario.h2("Minter")
    minter = minter_contract.TL_Minter(admin.address, token_registry.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    # create token_factory contract
    scenario.h1("Test TokenFactory")
    token_factory = token_factory_contract.TL_TokenFactory(admin.address, token_registry.address, minter.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += token_factory
    scenario.register(token_factory.collection_contract)

    # registry permissions
    token_registry.manage_permissions([sp.variant("add_permissions", [token_factory.address])]).run(sender=admin)

    # test update_minter
    scenario.h2("update_settings")

    # minter
    scenario.verify(token_factory.data.minter == minter.address)

    token_factory.update_settings([sp.variant("minter", alice.address)]).run(sender=bob, valid=False, exception="ONLY_ADMIN")
    token_factory.update_settings([sp.variant("minter", bob.address)]).run(sender=alice, valid=False, exception="ONLY_ADMIN")
    
    # TODO: test failiure of implicit accounts?
    #token_factory.update_token_registry(bob.address).run(sender=admin, valid=False, exception="ONLY_ADMIN")

    token_factory.update_settings([sp.variant("minter", alice.address)]).run(sender=admin)
    scenario.verify(token_factory.data.minter == alice.address)
    token_factory.update_settings([sp.variant("minter", minter.address)]).run(sender=admin)
    scenario.verify(token_factory.data.minter == minter.address)

    # token_registry
    scenario.verify(token_factory.data.token_registry == token_registry.address)

    token_factory.update_settings([sp.variant("token_registry", alice.address)]).run(sender=bob, valid=False, exception="ONLY_ADMIN")
    token_factory.update_settings([sp.variant("token_registry", bob.address)]).run(sender=alice, valid=False, exception="ONLY_ADMIN")
    
    # TODO: test failiure of implicit accounts?
    #token_factory.update_token_registry(bob.address).run(sender=admin, valid=False, exception="ONLY_ADMIN")

    token_factory.update_settings([sp.variant("token_registry", alice.address)]).run(sender=admin)
    scenario.verify(token_factory.data.token_registry == alice.address)
    token_factory.update_settings([sp.variant("token_registry", token_registry.address)]).run(sender=admin)
    scenario.verify(token_factory.data.token_registry == token_registry.address)

    # test create_token
    scenario.h2("create_token")
    token_factory.create_token(sp.utils.bytes_of_string("")).run(sender=admin, valid=False, exception="INVALID_METADATA")
    token_factory.create_token(sp.utils.bytes_of_string("https://newtoken.com")).run(sender=admin, valid=False, exception="INVALID_METADATA")
    token_factory.create_token(sp.utils.bytes_of_string("ipfs://newtoken.com")).run(sender=admin, valid=False, exception="INVALID_METADATA")
    token_factory.create_token(sp.utils.bytes_of_string("ipfs://QmbWqxBEKC3P8tqsKc98xmWNzrzDtRLMiMPL8wBuTGsMn")).run(sender=admin, valid=False, exception="INVALID_METADATA")

    token_factory.create_token(sp.utils.bytes_of_string("ipfs://QmbWqxBEKC3P8tqsKc98xmWNzrzDtRLMiMPL8wBuTGsMnR")).run(sender=admin)
    dyn_collection_token = scenario.dynamic_contract(0, token_factory.collection_contract)
    scenario.verify_equal(token_registry.is_registered(sp.record(fa2_list = [dyn_collection_token.address], merkle_proofs = sp.none)), {dyn_collection_token.address: True})
    scenario.verify_equal(token_registry.is_private_collection([dyn_collection_token.address]), {dyn_collection_token.address: True})
    scenario.verify_equal(token_registry.is_public_collection([dyn_collection_token.address]), {dyn_collection_token.address: False})
    scenario.verify(token_registry.is_private_owner(sp.record(collection = dyn_collection_token.address, address = admin.address)) == True)
    scenario.verify(token_registry.data.private_collections.contains(dyn_collection_token.address))

    token_factory.update_settings([sp.variant("paused", True)]).run(sender = admin)
    token_factory.create_token(sp.utils.bytes_of_string("ipfs://QmbWqxBEKC3P8tqsKc98xmWNzrzDtRLMiMPL8wBuTGsMnR")).run(sender=admin, valid=False, exception="ONLY_UNPAUSED")
    token_factory.update_settings([sp.variant("paused", False)]).run(sender = admin)

    # TODO: check FA2 ownership, check if collection can be minted with minter, etc...

    scenario.table_of_contents()
