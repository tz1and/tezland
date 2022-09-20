import smartpy as sp

token_factory_contract = sp.io.import_script_from_url("file:contracts/TL_TokenFactory.py")
token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")

@sp.add_test(name = "TL_TokenFactory_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("Minter Tests")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h1("Accounts")
    scenario.show([admin, alice, bob])

    # create token_registry contract
    scenario.h1("Test TokenRegistry")
    token_registry = token_registry_contract.TL_TokenRegistry(admin.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += token_registry

    # create token_factory contract
    scenario.h1("Test TokenFactory")
    token_factory = token_factory_contract.TL_TokenFactory(admin.address, token_registry.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += token_factory

    # registry permissions
    token_registry.manage_permissions([sp.variant("add_permission", token_factory.address)]).run(sender=admin)

    # test update_token_registry
    scenario.verify(token_factory.data.token_registry == token_registry.address)

    token_factory.update_token_registry(alice.address).run(sender=bob, valid=False, exception="ONLY_ADMIN")
    token_factory.update_token_registry(bob.address).run(sender=alice, valid=False, exception="ONLY_ADMIN")
    
    # TODO: test failiure of implicit accounts?
    #token_factory.update_token_registry(bob.address).run(sender=admin, valid=False, exception="ONLY_ADMIN")

    token_factory.update_token_registry(alice.address).run(sender=admin)
    scenario.verify(token_factory.data.token_registry == alice.address)
    token_factory.update_token_registry(token_registry.address).run(sender=admin)
    scenario.verify(token_factory.data.token_registry == token_registry.address)

    # test create_token

    token_factory.create_token(sp.record(metadata = sp.utils.metadata_of_url("https://newtoken.com"))).run(sender=admin)
    # NOTE: Not sure how to get the originated contract fromthe op. Does this address change?
    scenario.verify(token_registry.data.registered.contains(sp.address("KT1TezoooozzSmartPyzzDYNAMiCzzpLu4LU")))

    scenario.table_of_contents()
