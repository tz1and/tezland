import smartpy as sp

tokens = sp.io.import_script_from_url("file:contracts/Tokens.py")
allowed_place_tokens = sp.io.import_script_from_url("file:contracts/AllowedPlaceTokens.py")

class AllowedPlaceTokensTest(allowed_place_tokens.AllowedPlaceTokens, sp.Contract):
    def __init__(self, administrator):
        allowed_place_tokens.AllowedPlaceTokens.__init__(self, administrator = administrator)

    # test helpers
    @sp.entry_point
    def testOnlyAllowedPlaceTokens(self, fa2):
        self.onlyAllowedPlaceTokens(fa2)

    @sp.entry_point
    def testIsAllowedPlaceToken(self, params):
        sp.set_type(params, sp.TRecord(fa2 = sp.TAddress, expected = sp.TBool))
        sp.verify(self.isAllowedPlaceToken(params.fa2) == params.expected, "unexpected result")

    @sp.entry_point
    def testGetAllowedPlaceTokenLimits(self, params):
        sp.set_type(params, sp.TRecord(fa2 = sp.TAddress, expected = allowed_place_tokens.allowedPlaceLimitsType))
        sp.verify(self.getAllowedPlaceTokenLimits(params.fa2) == params.expected, "unexpected result")


@sp.add_test(name = "AllowedPlaceTokens_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    carol   = sp.test_account("Carol")
    scenario = sp.test_scenario()

    scenario.h1("AllowedPlaceTokens contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

    scenario.h2("Test AllowedPlaceTokens")

    scenario.h3("Contract origination")

    allowedPlaceTokens = AllowedPlaceTokensTest(admin.address)
    scenario += allowedPlaceTokens

    scenario.h4("some other FA2 token")
    other_token = tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += other_token

    # test set allowed
    scenario.h3("set_allowed_place_token")
    test_place_limits = sp.record(chunk_limit = 1, chunk_item_limit = 64)
    add_allowed = sp.list([sp.variant("add", {other_token.address: test_place_limits})])
    remove_allowed = sp.list([sp.variant("remove", sp.set([other_token.address]))])

    # no permission
    allowedPlaceTokens.set_allowed_place_token(add_allowed).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    scenario.verify(allowedPlaceTokens.data.place_tokens.contains(other_token.address) == False)

    # add
    allowedPlaceTokens.set_allowed_place_token(add_allowed).run(sender = admin)
    scenario.verify(allowedPlaceTokens.data.place_tokens.contains(other_token.address) == True)
    scenario.verify(allowedPlaceTokens.data.place_tokens[other_token.address] == test_place_limits)

    # remove
    allowedPlaceTokens.set_allowed_place_token(remove_allowed).run(sender = admin)
    scenario.verify(allowedPlaceTokens.data.place_tokens.contains(other_token.address) == False)
    scenario.verify(sp.is_failing(allowedPlaceTokens.data.place_tokens[other_token.address]))

    # test views
    scenario.h3("is_allowed_place_token view")
    scenario.verify(allowedPlaceTokens.is_allowed_place_token(other_token.address) == False)
    allowedPlaceTokens.set_allowed_place_token(add_allowed).run(sender = admin)
    scenario.verify(allowedPlaceTokens.is_allowed_place_token(other_token.address) == True)

    scenario.h3("get_allowed_place_token_limits view")
    scenario.verify(allowedPlaceTokens.get_allowed_place_token_limits(other_token.address) == test_place_limits)
    allowedPlaceTokens.set_allowed_place_token(remove_allowed).run(sender = admin)
    scenario.verify(sp.is_failing(allowedPlaceTokens.get_allowed_place_token_limits(other_token.address)))

    scenario.h3("testIsAllowedPlaceToken")
    allowedPlaceTokens.testIsAllowedPlaceToken(sp.record(fa2 = other_token.address, expected = False)).run(sender = admin)
    allowedPlaceTokens.set_allowed_place_token(add_allowed).run(sender = admin)
    allowedPlaceTokens.testIsAllowedPlaceToken(sp.record(fa2 = other_token.address, expected = True)).run(sender = admin)

    scenario.h3("testOnlyAllowedPlaceTokens")
    allowedPlaceTokens.testOnlyAllowedPlaceTokens(other_token.address).run(sender = admin)
    allowedPlaceTokens.set_allowed_place_token(remove_allowed).run(sender = admin)
    allowedPlaceTokens.testOnlyAllowedPlaceTokens(other_token.address).run(sender = admin, valid = False, exception = "PLACE_TOKEN_NOT_ALLOWED")

    scenario.h3("testGetAllowedPlaceTokenLimits")
    allowedPlaceTokens.testGetAllowedPlaceTokenLimits(sp.record(fa2 = other_token.address, expected = test_place_limits)).run(sender = admin, valid = False, exception = "PLACE_TOKEN_NOT_ALLOWED")
    allowedPlaceTokens.set_allowed_place_token(add_allowed).run(sender = admin)
    allowedPlaceTokens.testGetAllowedPlaceTokenLimits(sp.record(fa2 = other_token.address, expected = test_place_limits)).run(sender = admin)
