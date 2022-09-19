import smartpy as sp

token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")

@sp.add_test(name = "TL_TokenRegistry_tests", profile = True)
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

    # create a FA2 contract for testing
    scenario.h1("Create test env")
    items_tokens = tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    places_tokens = tokens.tz1andPlaces(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += places_tokens

    # create token_registry contract
    scenario.h1("Test TokenRegistry")
    token_registry = token_registry_contract.TL_TokenRegistry(admin.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += token_registry

    # test admin stuff
    scenario.h2("transfer_administrator")
    scenario.verify(token_registry.data.administrator == admin.address)
    token_registry.transfer_administrator(alice.address).run(sender = admin)
    token_registry.accept_administrator().run(sender = alice)
    scenario.verify(token_registry.data.administrator == alice.address)
    token_registry.transfer_administrator(admin.address).run(sender = alice)
    token_registry.accept_administrator().run(sender = admin)

    # test manage_permissions
    scenario.verify(token_registry.data.permitted.contains(alice.address) == False)
    scenario.verify(token_registry.data.permitted.contains(bob.address) == False)

    token_registry.manage_permissions([sp.variant("add_permission", bob.address)]).run(sender=admin)
    scenario.verify(token_registry.data.permitted.contains(alice.address) == False)
    scenario.verify(token_registry.data.permitted.contains(bob.address) == True)

    token_registry.manage_permissions([sp.variant("add_permission", alice.address)]).run(sender=admin)
    scenario.verify(token_registry.data.permitted.contains(alice.address) == True)
    scenario.verify(token_registry.data.permitted.contains(bob.address) == True)

    token_registry.manage_permissions([sp.variant("remove_permission", bob.address), sp.variant("remove_permission", alice.address)]).run(sender=admin)
    scenario.verify(token_registry.data.permitted.contains(alice.address) == False)
    scenario.verify(token_registry.data.permitted.contains(bob.address) == False)

    token_registry.manage_permissions([sp.variant("add_permission", bob.address)]).run(sender=admin)

    # test register_fa2
    token_registry.register_fa2([items_tokens.address]).run(sender=alice, valid=False, exception="NOT_PERMITTED")

    scenario.verify(token_registry.data.registered.contains(items_tokens.address) == False)
    token_registry.register_fa2([items_tokens.address]).run(sender=bob)
    scenario.verify(token_registry.data.registered.contains(items_tokens.address) == True)

    scenario.verify(token_registry.data.registered.contains(places_tokens.address) == False)
    token_registry.register_fa2([places_tokens.address]).run(sender=admin)
    scenario.verify(token_registry.data.registered.contains(places_tokens.address) == True)

    # test unregister_fa2
    token_registry.unregister_fa2([items_tokens.address]).run(sender=bob, valid=False, exception="ONLY_ADMIN")
    token_registry.unregister_fa2([items_tokens.address]).run(sender=alice, valid=False, exception="ONLY_ADMIN")

    scenario.verify(token_registry.data.registered.contains(places_tokens.address) == True)
    token_registry.unregister_fa2([places_tokens.address]).run(sender=admin)
    scenario.verify(token_registry.data.registered.contains(places_tokens.address) == False)

    # TODO: test views

    scenario.table_of_contents()
