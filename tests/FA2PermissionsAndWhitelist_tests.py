import smartpy as sp

tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")
permitted_fa2 = sp.io.import_script_from_url("file:contracts/FA2PermissionsAndWhitelist.py")


class FA2PermissionsAndWhitelistTest(permitted_fa2.FA2PermissionsAndWhitelist, sp.Contract):
    def __init__(self, administrator):
        permitted_fa2.FA2PermissionsAndWhitelist.__init__(self, administrator = administrator)

    # test helpers
    @sp.entry_point
    def testGetPermittedFA2Props(self, fa2, expected):
        props = self.getPermittedFA2Props(fa2)
        sp.verify_equal(props, expected)

    @sp.entry_point
    def testIsWhitelistedForFA2(self, fa2, user, expected):
        sp.verify(self.isWhitelistedForFA2(fa2, user) == expected)

    @sp.entry_point
    def testOnlyWhitelistedForFA2(self, fa2, user):
        self.onlyWhitelistedForFA2(fa2, user)

    # TODO: removeFromFA2Whitelist


@sp.add_test(name = "FA2PermissionsAndWhitelist_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    carol   = sp.test_account("Carol")
    scenario = sp.test_scenario()

    scenario.h1("FA2PermissionsAndWhitelist contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

    scenario.h2("Test FA2PermissionsAndWhitelist")

    scenario.h3("Contract origination")

    permitted = FA2PermissionsAndWhitelistTest(admin.address)
    scenario += permitted

    scenario.h4("some other FA2 token")
    other_token = tokens.tz1andPlaces_v2(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += other_token

    #
    # test permitted managing
    scenario.h3("manage_permitted_fa2")
    permitted_props = sp.record(
        whitelist_enabled = True,
        whitelist_admin = admin.address)
    add_permitted = sp.list([sp.variant("add_permitted",
        sp.record(
            fa2 = other_token.address,
            props = permitted_props))])

    remove_permitted = sp.list([sp.variant("remove_permitted", other_token.address)])

    # no permission
    permitted.manage_permitted_fa2(add_permitted).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    scenario.verify(permitted.data.permitted_fa2.contains(other_token.address) == False)

    # add
    permitted.manage_permitted_fa2(add_permitted).run(sender = admin)
    scenario.verify(permitted.data.permitted_fa2.contains(other_token.address) == True)
    scenario.verify(permitted.data.permitted_fa2[other_token.address].whitelist_enabled == True)
    scenario.verify(permitted.data.permitted_fa2[other_token.address].whitelist_admin == admin.address)

    # remove
    permitted.manage_permitted_fa2(remove_permitted).run(sender = admin)
    scenario.verify(permitted.data.permitted_fa2.contains(other_token.address) == False)
    scenario.verify(sp.is_failing(permitted.data.permitted_fa2[other_token.address]))

    #
    # test permitted managing
    scenario.h3("manage_whitelist")
    # TODO

    #
    # test view
    scenario.h3("get_fa2_permitted view")
    scenario.verify(sp.is_failing(permitted.get_fa2_permitted(other_token.address)))
    permitted.manage_permitted_fa2(add_permitted).run(sender = admin)
    scenario.verify(permitted.get_fa2_permitted(other_token.address) == sp.record(whitelist_enabled = True, whitelist_admin = admin.address))

    # TODO: is_whitelisted

    #
    # test utility functions
    scenario.h3("testGetPermittedFA2Props")
    permitted.testGetPermittedFA2Props(fa2 = other_token.address, expected = permitted_props).run(sender = admin)
    permitted.manage_permitted_fa2(remove_permitted).run(sender = admin)
    permitted.testGetPermittedFA2Props(fa2 = other_token.address, expected = permitted_props).run(sender = admin, valid = False, exception = "TOKEN_NOT_PERMITTED")

    whitelist_keys = [sp.record(fa2=other_token.address, user=bob.address), sp.record(fa2=other_token.address, user=carol.address)]
    whitelist_add = [sp.variant("whitelist_add", whitelist_keys)]
    whitelist_remove = [sp.variant("whitelist_remove", whitelist_keys)]

    scenario.h3("testIsWhitelistedForFA2")
    permitted.testIsWhitelistedForFA2(fa2=other_token.address, user=bob.address, expected=False).run(sender=admin)
    permitted.testIsWhitelistedForFA2(fa2=other_token.address, user=carol.address, expected=False).run(sender=admin)
    permitted.testIsWhitelistedForFA2(fa2=other_token.address, user=alice.address, expected=False).run(sender=admin)
    permitted.manage_whitelist(whitelist_add).run(sender=admin)
    permitted.testIsWhitelistedForFA2(fa2=other_token.address, user=bob.address, expected=True).run(sender=admin)
    permitted.testIsWhitelistedForFA2(fa2=other_token.address, user=carol.address, expected=True).run(sender=admin)
    permitted.testIsWhitelistedForFA2(fa2=other_token.address, user=alice.address, expected=False).run(sender=admin)
    permitted.manage_whitelist(whitelist_remove).run(sender=admin)
    permitted.testIsWhitelistedForFA2(fa2=other_token.address, user=bob.address, expected=False).run(sender=admin)
    permitted.testIsWhitelistedForFA2(fa2=other_token.address, user=carol.address, expected=False).run(sender=admin)
    permitted.testIsWhitelistedForFA2(fa2=other_token.address, user=alice.address, expected=False).run(sender=admin)

    scenario.h3("testOnlyWhitelistedForFA2")
    permitted.manage_permitted_fa2(add_permitted).run(sender = admin)
    permitted.testOnlyWhitelistedForFA2(fa2=other_token.address, user=bob.address).run(sender=admin, valid=False, exception="ONLY_WHITELISTED")
    permitted.testOnlyWhitelistedForFA2(fa2=other_token.address, user=carol.address).run(sender=admin, valid=False, exception="ONLY_WHITELISTED")
    permitted.testOnlyWhitelistedForFA2(fa2=other_token.address, user=alice.address).run(sender=admin, valid=False, exception="ONLY_WHITELISTED")
    permitted.manage_whitelist(whitelist_add).run(sender=admin)
    permitted.testOnlyWhitelistedForFA2(fa2=other_token.address, user=bob.address).run(sender=admin)
    permitted.testOnlyWhitelistedForFA2(fa2=other_token.address, user=carol.address).run(sender=admin)
    permitted.testOnlyWhitelistedForFA2(fa2=other_token.address, user=alice.address).run(sender=admin, valid=False, exception="ONLY_WHITELISTED")
    permitted.manage_whitelist(whitelist_remove).run(sender=admin)
    permitted.testOnlyWhitelistedForFA2(fa2=other_token.address, user=bob.address).run(sender=admin, valid=False, exception="ONLY_WHITELISTED")
    permitted.testOnlyWhitelistedForFA2(fa2=other_token.address, user=carol.address).run(sender=admin, valid=False, exception="ONLY_WHITELISTED")
    permitted.testOnlyWhitelistedForFA2(fa2=other_token.address, user=alice.address).run(sender=admin, valid=False, exception="ONLY_WHITELISTED")
    permitted.manage_permitted_fa2(remove_permitted).run(sender = admin)
    permitted.testOnlyWhitelistedForFA2(fa2=other_token.address, user=bob.address).run(sender=admin, valid=False, exception="TOKEN_NOT_PERMITTED")
    permitted.testOnlyWhitelistedForFA2(fa2=other_token.address, user=carol.address).run(sender=admin, valid=False, exception="TOKEN_NOT_PERMITTED")
    permitted.testOnlyWhitelistedForFA2(fa2=other_token.address, user=alice.address).run(sender=admin, valid=False, exception="TOKEN_NOT_PERMITTED")