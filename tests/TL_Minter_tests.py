import smartpy as sp

minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter.py")
fa2_contract = sp.io.import_script_from_url("file:contracts/FA2.py")

@sp.add_test(name = "TL_Minter_tests", profile = True)
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
    items_tokens = fa2_contract.FA2(config = fa2_contract.items_config(),
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    places_tokens = fa2_contract.FA2(config = fa2_contract.places_config(),
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += places_tokens

    # create minter contract
    scenario.h1("Test Minter")
    minter = minter_contract.TL_Minter(admin.address, items_tokens.address, places_tokens.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    # set items_tokens and places_tokens administrator to minter contract
    items_tokens.set_administrator(minter.address).run(sender = admin)
    places_tokens.set_administrator(minter.address).run(sender = admin)

    # test admin stuff
    scenario.h2("transfer_administrator")
    scenario.verify(minter.data.administrator == admin.address)
    minter.transfer_administrator(alice.address).run(sender = admin)
    minter.accept_administrator().run(sender = alice)
    scenario.verify(minter.data.administrator == alice.address)
    minter.transfer_administrator(admin.address).run(sender = alice)
    minter.accept_administrator().run(sender = admin)

    # test set_paused
    scenario.h2("set_paused")
    minter.set_paused(True).run(sender = bob, valid = False)
    minter.set_paused(False).run(sender = alice, valid = False)
    minter.set_paused(True).run(sender = admin)
    scenario.verify(minter.data.paused == True)
    minter.set_paused(False).run(sender = admin)
    scenario.verify(minter.data.paused == False)

    # test Item minting
    scenario.h2("mint_Item")
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

    # test Place minting
    scenario.h2("mint_Place")
    minter.mint_Place(address = bob.address,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob, valid = False)

    minter.mint_Place(address = alice.address,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice, valid = False)

    minter.mint_Place(address = admin.address,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = admin)

    minter.set_paused(True).run(sender = admin)

    minter.mint_Place(address = admin.address,
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = admin, valid = False)

    minter.set_paused(False).run(sender = admin)

    # test get_item_royalties view
    scenario.h2("get_item_royalties")
    scenario.p("It's a view")
    view_res = minter.get_item_royalties(sp.nat(0))
    scenario.verify(view_res.royalties == 250)
    scenario.verify(view_res.creator == bob.address)

    # test set_paused_tokens
    scenario.h2("set_paused_tokens")

    # check tokens are unpaused to begin with
    scenario.verify(items_tokens.data.paused == False)
    scenario.verify(places_tokens.data.paused == False)

    minter.set_paused_tokens(True).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    minter.set_paused_tokens(True).run(sender = admin)

    # check tokens are paused
    scenario.verify(items_tokens.data.paused == True)
    scenario.verify(places_tokens.data.paused == True)

    minter.set_paused_tokens(False).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    minter.set_paused_tokens(False).run(sender = admin)

    # check tokens are unpaused
    scenario.verify(items_tokens.data.paused == False)
    scenario.verify(places_tokens.data.paused == False)

    # test regain admin
    #scenario.h2("regain_admin_Items")
    #minter.regain_admin_Items().run(sender = admin, valid = False)
    #minter.set_paused(True).run(sender = admin)
    #minter.regain_admin_Items().run(sender = bob, valid = False)
    #minter.regain_admin_Items().run(sender = admin) # admin can only be regained if paused
    #minter.set_paused(False).run(sender = admin)

    #scenario.h2("regain_admin_Places")
    #minter.regain_admin_Places().run(sender = admin, valid = False)
    #minter.set_paused(True).run(sender = admin)
    #minter.regain_admin_Places().run(sender = bob, valid = False)
    #minter.regain_admin_Places().run(sender = admin) # admin can only be regained if paused
    #minter.set_paused(False).run(sender = admin)

    scenario.table_of_contents()
