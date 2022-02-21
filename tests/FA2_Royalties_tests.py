import smartpy as sp

fa2_royalties = sp.io.import_script_from_url("file:contracts/FA2_Royalties.py")

class FA2_RoyaltiesTest(fa2_royalties.FA2_Royalties):
    def __init__(self):
        self.init_storage(
            token_extra=sp.big_map(tkey=sp.TNat, tvalue=sp.TRecord(
                royalty_info = fa2_royalties.FA2_Royalties.ROYALTIES_TYPE
            ))
        )

    @sp.entry_point
    def testValidateRoyalties(self, royalties):
        sp.set_type(royalties, fa2_royalties.FA2_Royalties.ROYALTIES_TYPE)
        self.validateRoyalties(royalties)

    @sp.entry_point
    def testSetRoyalties(self, params):
        sp.set_type(params.token_id, sp.TNat)
        sp.set_type(params.royalties, fa2_royalties.FA2_Royalties.ROYALTIES_TYPE)
        self.data.token_extra[params.token_id] = sp.record(royalty_info = params.royalties)


@sp.add_test(name = "FA2_Royalties_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    carol   = sp.test_account("Carol")
    scenario = sp.test_scenario()

    scenario.h1("FA2_Royalties contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

    scenario.h2("Test FA2_Royalties")

    scenario.h3("Contract origination")

    fa2_royalties = FA2_RoyaltiesTest()
    scenario += fa2_royalties

    scenario.h3("testValidateRoyalties")

    royalties_valid1 = sp.record(
        royalties=sp.nat(150),
        contributors= sp.map({
            admin.address: sp.record(relative_royalties=sp.nat(1000), role="minter")
        }))

    royalties_valid2 = sp.record(
        royalties=sp.nat(0),
        contributors= sp.map({
            admin.address: sp.record(relative_royalties=sp.nat(900), role="minter"),
            bob.address: sp.record(relative_royalties=sp.nat(100), role="creator")
        }))
    
    royalties_valid3 = sp.record(
        royalties=sp.nat(250),
        contributors= sp.map({
            admin.address: sp.record(relative_royalties=sp.nat(500), role="minter"),
            bob.address: sp.record(relative_royalties=sp.nat(250), role="creator"),
            alice.address: sp.record(relative_royalties=sp.nat(250), role="alice")
            
        }))

    fa2_royalties.testValidateRoyalties(royalties_valid1).run(sender = admin)
    fa2_royalties.testValidateRoyalties(royalties_valid2).run(sender = admin)
    fa2_royalties.testValidateRoyalties(royalties_valid3).run(sender = admin)

    royalties_invalid1 = sp.record(
        royalties=sp.nat(350),
        contributors= sp.map({
            admin.address: sp.record(relative_royalties=sp.nat(1000), role="minter")
        }))

    royalties_invalid2 = sp.record(
        royalties=sp.nat(0),
        contributors= sp.map({
            admin.address: sp.record(relative_royalties=sp.nat(900), role="minter"),
            bob.address: sp.record(relative_royalties=sp.nat(200), role="creator")
        }))
    
    royalties_invalid3 = sp.record(
        royalties=sp.nat(250),
        contributors= sp.map({
            admin.address: sp.record(relative_royalties=sp.nat(500), role="minter"),
            bob.address: sp.record(relative_royalties=sp.nat(250), role="creator"),
            alice.address: sp.record(relative_royalties=sp.nat(150), role="alice")
            
        }))

    royalties_invalid4 = sp.record(
        royalties=sp.nat(250),
        contributors= sp.map({
            admin.address: sp.record(relative_royalties=sp.nat(300), role="minter"),
            bob.address: sp.record(relative_royalties=sp.nat(250), role="creator"),
            alice.address: sp.record(relative_royalties=sp.nat(150), role="alice"),
            carol.address: sp.record(relative_royalties=sp.nat(300), role="carol")
            
        }))

    fa2_royalties.testValidateRoyalties(royalties_invalid1).run(sender = admin, valid = False, exception = "FA2_ROYALTIES_ERROR")
    fa2_royalties.testValidateRoyalties(royalties_invalid2).run(sender = admin, valid = False, exception = "FA2_ROYALTIES_ERROR")
    fa2_royalties.testValidateRoyalties(royalties_invalid3).run(sender = admin, valid = False, exception = "FA2_ROYALTIES_ERROR")
    fa2_royalties.testValidateRoyalties(royalties_invalid4).run(sender = admin, valid = False, exception = "FA2_ROYALTIES_ERROR")

    scenario.h3("testSetRoyalties")

    fa2_royalties.testSetRoyalties(token_id = sp.nat(0), royalties = royalties_valid1).run(sender = admin)
    scenario.verify(fa2_royalties.data.token_extra.contains(sp.nat(0)))

    fa2_royalties.testSetRoyalties(token_id = sp.nat(1), royalties = royalties_valid2).run(sender = admin)
    scenario.verify(fa2_royalties.data.token_extra.contains(sp.nat(1)))

    fa2_royalties.testSetRoyalties(token_id = sp.nat(2), royalties = royalties_valid3).run(sender = admin)
    scenario.verify(fa2_royalties.data.token_extra.contains(sp.nat(2)))

    scenario.h3("get_token_royalties")
    
    royalties1 = fa2_royalties.get_token_royalties(sp.nat(0))
    scenario.show(royalties1)
    scenario.verify(sp.len(royalties1.contributors) == 1)
    #scenario.verify(royalties1[0].address == admin.address)
    #scenario.verify(royalties1[0].pct == 1000)

    royalties2 = fa2_royalties.get_token_royalties(sp.nat(1))
    scenario.show(royalties2)
    scenario.verify(sp.len(royalties2.contributors) == 2)
    #scenario.verify(royalties22[0].address == admin.address)
    #scenario.verify(royalties22[0].pct == 900)
    #scenario.verify(royalties22[1].address == bob.address)
    #scenario.verify(royalties22[1].pct == 100)

    royalties3 = fa2_royalties.get_token_royalties(sp.nat(2))
    scenario.show(royalties3)
    scenario.verify(sp.len(royalties3.contributors) == 3)
    #scenario.verify(royalties2[0].address == admin.address)
    #scenario.verify(royalties2[0].pct == 500)
    #scenario.verify(royalties2[1].address == bob.address)
    #scenario.verify(royalties2[1].pct == 250)
    #scenario.verify(royalties2[2].address == alice.address)
    #scenario.verify(royalties2[2].pct == 250)

    royalties_non_existing = fa2_royalties.get_token_royalties(sp.nat(3))
    scenario.show(royalties_non_existing)
    scenario.verify(royalties_non_existing.royalties == 0)
    scenario.verify(sp.len(royalties_non_existing.contributors) == 0)