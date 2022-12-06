import smartpy as sp

from contracts import TL_Minter, DistrictDAO, TL_World_v2, Tokens
from contracts.utils import Utils


# TODO: test royalties, fees, issuer being paid, lol


@sp.add_test(name = "DistrictDAO_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    carol = sp.test_account("Carol")
    scenario = sp.test_scenario()

    scenario.h1("DistrictDAO Tests")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h1("Accounts")
    scenario.show([admin, alice, bob, carol])

    #
    # create all kinds of contracts for testing
    #
    scenario.h1("Create test env")
    scenario.h2("items")
    items_tokens = Tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += items_tokens

    scenario.h2("places")
    places_tokens = Tokens.tz1andPlaces(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += places_tokens

    scenario.h2("minter")
    minter = TL_Minter.TL_Minter(admin.address, items_tokens.address, places_tokens.address,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += minter

    scenario.h2("dao")
    dao_token = Tokens.tz1andDAO(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += dao_token

    scenario.h2("some other FA2 token")
    other_token = Tokens.tz1andItems(
        metadata = sp.utils.metadata_of_url("https://example.com"),
        admin = admin.address)
    scenario += other_token

    scenario.h2("preparation")
    items_tokens.transfer_administrator(minter.address).run(sender = admin)
    places_tokens.transfer_administrator(minter.address).run(sender = admin)
    minter.accept_fa2_administrator([items_tokens.address, places_tokens.address]).run(sender = admin)

    # mint some item tokens for testing
    scenario.h3("minting items")
    minter.mint_Item(to_ = bob.address,
        amount = 4,
        royalties = 250,
        contributors = [ sp.record(address=bob.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = bob)

    minter.mint_Item(to_ = alice.address,
        amount = 25,
        royalties = 250,
        contributors = [ sp.record(address=alice.address, relative_royalties=sp.nat(1000), role=sp.variant("minter", sp.unit)) ],
        metadata = sp.utils.bytes_of_string("test_metadata")).run(sender = alice)

    item_bob = sp.nat(0)
    item_alice = sp.nat(1)

    # mint some place tokens for testing
    scenario.h3("minting places")
    minter.mint_Place([
        sp.record(
            to_ = bob.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        ),
        sp.record(
            to_ = alice.address,
            metadata = {'': sp.utils.bytes_of_string("test_metadata")}
        )
    ]).run(sender = admin)

    place_bob = sp.record(
        place_contract = places_tokens.address,
        lot_id = sp.nat(0)
    )
    place_alice = sp.record(
        place_contract = places_tokens.address,
        lot_id = sp.nat(1)
    )

    # create World contract
    scenario.h2("world")
    world = TL_World_v2.TL_World_v2(admin.address, items_tokens.address, places_tokens.address, dao_token.address,
        metadata = sp.utils.metadata_of_url("https://example.com"), name = "Test World", description = "A world for testing")
    scenario += world

    #
    # Test DistrictDAO
    #
    scenario.h1("Test DistrictDAO")

    scenario.h2("Originate DistrictDAO contract")
    #world_contract, items_contract, places_contract, dao_contract, metadata, district_number
    dao = DistrictDAO.DistrictDAO(admin.address, world.address, items_tokens.address, places_tokens.address, dao_token.address, 1,
        metadata = sp.utils.metadata_of_url("https://example.com"))
    scenario += dao

    #
    # the end.
    scenario.table_of_contents()