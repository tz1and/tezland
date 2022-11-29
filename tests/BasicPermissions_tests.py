import smartpy as sp

admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")
basic_permissions_mixin = sp.io.import_script_from_url("file:contracts/BasicPermissions.py")

class BasicPermissionsTest(
    admin_mixin.Administrable,
    basic_permissions_mixin.BasicPermissions,
    sp.Contract):
    def __init__(self, administrator):
        admin_mixin.Administrable.__init__(self, administrator = administrator)
        basic_permissions_mixin.BasicPermissions.__init__(self)

    # TODO: test inline helpers


@sp.add_test(name = "BasicPermissions_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("BasicPermissions contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

    scenario.h2("Test BasicPermissions")

    scenario.h3("Contract origination")
    basic_permissions = BasicPermissionsTest(admin.address)
    scenario += basic_permissions

    #
    # manage_permissions
    #
    scenario.h3("manage_permissions")

    # test manage_permissions
    scenario.verify(basic_permissions.data.permitted_accounts.contains(alice.address) == False)
    scenario.verify(basic_permissions.data.permitted_accounts.contains(bob.address) == False)

    basic_permissions.manage_permissions([sp.variant("add_permissions", sp.set([alice.address]))]).run(sender=bob, valid=False, exception="ONLY_ADMIN")
    basic_permissions.manage_permissions([sp.variant("add_permissions", sp.set([bob.address]))]).run(sender=alice, valid=False, exception="ONLY_ADMIN")

    basic_permissions.manage_permissions([sp.variant("add_permissions", sp.set([bob.address]))]).run(sender=admin)
    scenario.verify(basic_permissions.data.permitted_accounts.contains(alice.address) == False)
    scenario.verify(basic_permissions.data.permitted_accounts.contains(bob.address) == True)

    basic_permissions.manage_permissions([sp.variant("add_permissions", sp.set([alice.address]))]).run(sender=admin)
    scenario.verify(basic_permissions.data.permitted_accounts.contains(alice.address) == True)
    scenario.verify(basic_permissions.data.permitted_accounts.contains(bob.address) == True)

    basic_permissions.manage_permissions([sp.variant("remove_permissions", sp.set([bob.address, alice.address]))]).run(sender=admin)
    scenario.verify(basic_permissions.data.permitted_accounts.contains(alice.address) == False)
    scenario.verify(basic_permissions.data.permitted_accounts.contains(bob.address) == False)
