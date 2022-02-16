import smartpy as sp

whitelist_contract = sp.io.import_script_from_url("file:contracts/Whitelist.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")

class WhitelistTests(whitelist_contract.Whitelist):
    def __init__(self, manager):
        self.address_set = utils.Address_set()
        self.init_storage(
            manager = manager,
            whitelist_enabled = True,
            whitelist = self.address_set.make()
        )

    @sp.entry_point
    def testIsWhitelisted(self, whitelisted):
        sp.set_type(whitelisted, sp.TBool)
        sp.verify(self.isWhitelisted(sp.sender) == whitelisted)

    @sp.entry_point
    def testOnlyWhitelisted(self):
        self.onlyWhitelisted()

    @sp.entry_point
    def testOnlyManagerIfWhitelistEnabled(self):
        self.onlyManagerIfWhitelistEnabled()

    @sp.entry_point
    def testRemoveFromWhitelist(self, address):
        """NOTE: removeFromWhitelist is an inline-only function
        so no need to check if manager."""
        sp.set_type(address, sp.TAddress)
        self.removeFromWhitelist(address)

    @sp.entry_point
    def testIsManager(self, address):
        sp.set_type(address, sp.TAddress)
        sp.if ~self.isManager(address):
            sp.verify(False, "error")


@sp.add_test(name = "Whitelist_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("Whitelist contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

    scenario.h2("Test Whitelist")

    scenario.h3("Contract origination")
    whitelist = WhitelistTests(admin.address)
    scenario += whitelist

    scenario.verify(whitelist.data.manager == admin.address)

    #
    #
    scenario.h3("isWhitelisted")

    whitelist.testIsWhitelisted(False).run(sender = bob, valid = True)
    whitelist.testIsWhitelisted(True).run(sender = bob, valid = False)
    whitelist.testIsWhitelisted(False).run(sender = alice, valid = True)
    whitelist.testIsWhitelisted(True).run(sender = alice, valid = False)
    whitelist.testIsWhitelisted(False).run(sender = admin, valid = True)
    whitelist.testIsWhitelisted(True).run(sender = admin, valid = False)

    # add to whitelist
    whitelist.manage_whitelist([sp.variant("whitelist_add", [bob.address, admin.address])]).run(sender=admin)

    whitelist.testIsWhitelisted(False).run(sender = bob, valid = False)
    whitelist.testIsWhitelisted(True).run(sender = bob, valid = True)
    whitelist.testIsWhitelisted(False).run(sender = alice, valid = True)
    whitelist.testIsWhitelisted(True).run(sender = alice, valid = False)
    whitelist.testIsWhitelisted(False).run(sender = admin, valid = False)
    whitelist.testIsWhitelisted(True).run(sender = admin, valid = True)

    #
    #
    scenario.h3("onlyWhitelisted")

    whitelist.testOnlyWhitelisted().run(sender = bob, valid = True)
    whitelist.testOnlyWhitelisted().run(sender = alice, valid = False)
    whitelist.testOnlyWhitelisted().run(sender = admin, valid = True)

    # disable whitelisted
    whitelist.manage_whitelist([sp.variant("whitelist_enabled", False)]).run(sender=admin)

    whitelist.testOnlyWhitelisted().run(sender = bob, valid = True)
    whitelist.testOnlyWhitelisted().run(sender = alice, valid = True)
    whitelist.testOnlyWhitelisted().run(sender = admin, valid = True)

    # enabled whitelist and remove
    whitelist.manage_whitelist([sp.variant("whitelist_enabled", True)]).run(sender=admin)
    whitelist.manage_whitelist([sp.variant("whitelist_remove", [bob.address, admin.address])]).run(sender=admin)

    whitelist.testOnlyWhitelisted().run(sender = bob, valid = False)
    whitelist.testOnlyWhitelisted().run(sender = alice, valid = False)
    whitelist.testOnlyWhitelisted().run(sender = admin, valid = False)

    #
    #
    scenario.h3("onlyManagerIfWhitelistEnabled")

    whitelist.testOnlyManagerIfWhitelistEnabled().run(sender = bob, valid = False)
    whitelist.testOnlyManagerIfWhitelistEnabled().run(sender = alice, valid = False)
    whitelist.testOnlyManagerIfWhitelistEnabled().run(sender = admin, valid = True)

    whitelist.manage_whitelist([sp.variant("whitelist_enabled", False)]).run(sender=admin)

    whitelist.testOnlyManagerIfWhitelistEnabled().run(sender = bob, valid = True)
    whitelist.testOnlyManagerIfWhitelistEnabled().run(sender = alice, valid = True)
    whitelist.testOnlyManagerIfWhitelistEnabled().run(sender = admin, valid = True)

    #
    #
    scenario.h3("removeFromWhitelist")

    whitelist.manage_whitelist([sp.variant("whitelist_add", [bob.address, admin.address])]).run(sender=admin)
    scenario.verify(whitelist.data.whitelist.contains(bob.address))
    scenario.verify(~whitelist.data.whitelist.contains(alice.address))
    scenario.verify(whitelist.data.whitelist.contains(admin.address))

    whitelist.testRemoveFromWhitelist(bob.address).run(sender=admin, valid=True)
    scenario.verify(~whitelist.data.whitelist.contains(bob.address))
    whitelist.testRemoveFromWhitelist(alice.address).run(sender=admin, valid=True)
    scenario.verify(~whitelist.data.whitelist.contains(alice.address))
    whitelist.testRemoveFromWhitelist(admin.address).run(sender=admin, valid=True)
    scenario.verify(~whitelist.data.whitelist.contains(admin.address))

    #
    #
    scenario.h3("manage_whitelist")

    whitelist.manage_whitelist([sp.variant("whitelist_add", [bob.address, admin.address])]).run(sender=admin)
    scenario.verify(whitelist.data.whitelist.contains(bob.address))
    scenario.verify(~whitelist.data.whitelist.contains(alice.address))
    scenario.verify(whitelist.data.whitelist.contains(admin.address))

    whitelist.manage_whitelist([sp.variant("whitelist_remove", [bob.address, admin.address])]).run(sender=admin)
    scenario.verify(~whitelist.data.whitelist.contains(bob.address))
    scenario.verify(~whitelist.data.whitelist.contains(alice.address))
    scenario.verify(~whitelist.data.whitelist.contains(admin.address))

    whitelist.manage_whitelist([sp.variant("whitelist_enabled", False)]).run(sender=admin)
    scenario.verify(whitelist.data.whitelist_enabled == False)

    whitelist.manage_whitelist([sp.variant("whitelist_enabled", True)]).run(sender=admin)
    scenario.verify(whitelist.data.whitelist_enabled == True)

    whitelist.manage_whitelist([sp.variant("whitelist_enabled", False)]).run(sender=admin)
    scenario.verify(whitelist.data.whitelist_enabled == False)

    #
    # views
    scenario.h3("views")

    scenario.h4("whitelist_enabled")
    scenario.verify(whitelist.is_whitelist_enabled() == False)
    whitelist.manage_whitelist([sp.variant("whitelist_enabled", True)]).run(sender=admin)
    scenario.verify(whitelist.is_whitelist_enabled() == True)

    scenario.h4("is_whitelisted")
    scenario.verify(whitelist.is_whitelisted(bob.address) == False)
    scenario.verify(whitelist.is_whitelisted(alice.address) == False)
    scenario.verify(whitelist.is_whitelisted(admin.address) == False)

    whitelist.manage_whitelist([sp.variant("whitelist_add", [bob.address, admin.address])]).run(sender=admin)
    scenario.verify(whitelist.is_whitelisted(bob.address) == True)
    scenario.verify(whitelist.is_whitelisted(alice.address) == False)
    scenario.verify(whitelist.is_whitelisted(admin.address) == True)
