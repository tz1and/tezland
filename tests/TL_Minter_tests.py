import smartpy as sp

minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter.py")
places_contract = sp.io.import_script_from_url("file:contracts/TL_Places.py")
fa2_contract = sp.io.import_script_from_url("file:contracts/FA2.py")

@sp.add_test(name = "TL_Minter_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("Places Contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

    # create a FA2 contract for testing
    scenario.h2("Create test env")
    items_tokens = fa2_contract.FA2(config = fa2_contract.items_config(),
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    # create minter contract
    scenario.h2("Test Minter")
    minter = minter_contract.TL_Minter(admin.address, items_tokens.address) #admin.address, 
    scenario += minter

    # set items_tokens administrator to minter contract
    items_tokens.set_administrator(minter.address).run(sender = admin)

    # test manager stuff
    scenario.h3("set_manager")
    scenario.verify(minter.data.manager == admin.address)
    minter.set_manager(alice.address).run(sender = admin)
    scenario.verify(minter.data.manager == alice.address)
    minter.set_manager(admin.address).run(sender = alice)

    #scenario += minter.add_manager(bob.address).run(sender = bob, valid = False)

    # test set_paused
    scenario.h3("set_paused")
    minter.set_paused(True).run(sender = bob, valid = False)
    minter.set_paused(False).run(sender = alice, valid = False)
    minter.set_paused(True).run(sender = admin)
    scenario.verify(minter.data.paused == True)
    minter.set_paused(False).run(sender = admin)
    scenario.verify(minter.data.paused == False)

    # test minting
    scenario.h3("mint_Item")
    minter.mint_Item(address = bob.address,
        amount = 4,
        royalties = 250,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    minter.mint_Item(address = alice.address,
        amount = 25,
        royalties = 250,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)

    minter.set_paused(True).run(sender = admin)

    minter.mint_Item(address = alice.address,
        amount = 25,
        royalties = 250,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice, valid = False)

    minter.set_paused(False).run(sender = admin)

    # test get_royalties view
    scenario.h3("get_royalties")
    scenario.p("It's a view")
    view_res = minter.get_royalties(0)
    scenario.verify(view_res.royalties == 250)
    scenario.verify(view_res.creator == bob.address)

    # test regain admin
    scenario.h3("regain_admin_Items")
    minter.regain_admin_Items().run(sender = admin, valid = False)
    minter.set_paused(True).run(sender = admin)
    minter.regain_admin_Items().run(sender = bob, valid = False)
    minter.regain_admin_Items().run(sender = admin) # admin can only be regained if paused
    minter.set_paused(False).run(sender = admin)

    scenario.table_of_contents()
