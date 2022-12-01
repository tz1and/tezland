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
    collections_key = sp.test_account("Collections")
    scenario = sp.test_scenario()

    scenario.h1("TokenFactory Tests")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h1("Accounts")
    scenario.show([admin, alice, bob])

    # create registry contract
    scenario.h1("Create test env")

    scenario.h2("TokenRegistry")
    registry = token_registry_contract.TL_TokenRegistry(admin.address, collections_key.public_key,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += registry

    scenario.h2("Minter")
    minter = minter_contract.TL_Minter_v2(admin.address, registry.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    # create token_factory contract
    scenario.h1("Test TokenFactory")
    token_factory = token_factory_contract.TL_TokenFactory(admin.address, registry.address, minter.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += token_factory
    scenario.register(token_factory.collection_contract)

    # registry permissions
    registry.manage_permissions([sp.variant("add_permissions", sp.set([token_factory.address]))]).run(sender=admin)

    # test update_minter
    scenario.h2("update_settings")

    # minter
    scenario.verify(token_factory.data.minter == minter.address)

    # test minter setting failiure cases
    for t in [(bob, "ONLY_ADMIN"), (alice, "ONLY_ADMIN"), (admin, "NOT_CONTRACT")]:
        sender, exception = t
        token_factory.update_settings([sp.variant("minter", alice.address)]).run(sender=sender, valid=False, exception=exception)

    token_factory.update_settings([sp.variant("minter", token_factory.address)]).run(sender=admin)
    scenario.verify(token_factory.data.minter == token_factory.address)
    token_factory.update_settings([sp.variant("minter", minter.address)]).run(sender=admin)
    scenario.verify(token_factory.data.minter == minter.address)

    # registry
    scenario.verify(token_factory.data.registry == registry.address)

    # test registry setting failiure cases
    for t in [(bob, "ONLY_ADMIN"), (alice, "ONLY_ADMIN"), (admin, "NOT_CONTRACT")]:
        sender, exception = t
        token_factory.update_settings([sp.variant("registry", alice.address)]).run(sender=sender, valid=False, exception=exception)

    token_factory.update_settings([sp.variant("registry", token_factory.address)]).run(sender=admin)
    scenario.verify(token_factory.data.registry == token_factory.address)
    token_factory.update_settings([sp.variant("registry", registry.address)]).run(sender=admin)
    scenario.verify(token_factory.data.registry == registry.address)

    # test create_token
    scenario.h2("create_token")
    token_factory.create_token(sp.utils.bytes_of_string("")).run(sender=admin, valid=False, exception="INVALID_METADATA")
    token_factory.create_token(sp.utils.bytes_of_string("https://newtoken.com")).run(sender=admin, valid=False, exception="INVALID_METADATA")
    token_factory.create_token(sp.utils.bytes_of_string("ipfs://newtoken.com")).run(sender=admin, valid=False, exception="INVALID_METADATA")
    token_factory.create_token(sp.utils.bytes_of_string("ipfs://QmbWqxBEKC3P8tqsKc98xmWNzrzDtRLMiMPL8wBuTGsMn")).run(sender=admin, valid=False, exception="INVALID_METADATA")

    token_factory.create_token(sp.utils.bytes_of_string("ipfs://QmbWqxBEKC3P8tqsKc98xmWNzrzDtRLMiMPL8wBuTGsMnR")).run(sender=admin)
    dyn_collection_token = scenario.dynamic_contract(0, token_factory.collection_contract)
    scenario.verify_equal(registry.is_registered(sp.set([dyn_collection_token.address])), sp.set([dyn_collection_token.address]))
    scenario.verify(registry.data.collections.get(dyn_collection_token.address).collection_type == token_registry_contract.collectionPrivate)
    scenario.verify(registry.get_collection_info(dyn_collection_token.address).ownership.is_some())
    scenario.verify(registry.is_private_owner_or_collab(sp.record(collection = dyn_collection_token.address, address = admin.address)) == sp.bounded("owner"))

    token_factory.update_settings([sp.variant("paused", True)]).run(sender = admin)
    token_factory.create_token(sp.utils.bytes_of_string("ipfs://QmbWqxBEKC3P8tqsKc98xmWNzrzDtRLMiMPL8wBuTGsMnR")).run(sender=admin, valid=False, exception="ONLY_UNPAUSED")
    token_factory.update_settings([sp.variant("paused", False)]).run(sender = admin)

    # TODO: check FA2 ownership, check if collection can be minted with minter, etc...

    scenario.table_of_contents()
