import smartpy as sp

from contracts.mixins.Administrable import Administrable
from contracts.mixins import BasicPermissions


class BasicPermissionsTest(
    Administrable,
    BasicPermissions.BasicPermissions,
    sp.Contract):
    def __init__(self, administrator):
        Administrable.__init__(self, administrator = administrator)
        BasicPermissions.BasicPermissions.__init__(self)

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
