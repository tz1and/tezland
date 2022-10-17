import smartpy as sp

FA2_proxy = sp.io.import_script_from_url("file:contracts/FA2_proxy.py")


@sp.add_test(name = "FA2_proxy_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("FA2_proxy contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

    scenario.h2("Test FA2_proxy")

    scenario.h3("Contract origination")
    scenario.h4("base")
    base = FA2_proxy.FA2ProxyBase(sp.utils.metadata_of_url("ipfs://example"),
        admin.address, admin.address)
    scenario += base

    scenario.h4("parent")
    parent = FA2_proxy.FA2ProxyParent(sp.utils.metadata_of_url("ipfs://example"),
        admin.address, admin.address)
    scenario += parent

    scenario.h4("child")
    child = FA2_proxy.FA2ProxyChild(sp.utils.metadata_of_url("ipfs://example"),
        admin.address, parent.address)
    scenario += child

    #
    # update_fees
    #
    scenario.h3("update_fees")

    scenario.show(parent.get_ep_lambda(sp.variant("mint", sp.unit)))

    child.mint([sp.record(
            token=sp.variant("new", sp.record(
                metadata={"": sp.utils.bytes_of_string("test_metadata")},
                royalties=sp.record(
                    royalties=sp.nat(150),
                    contributors=[
                        sp.record(address=admin.address, role=sp.variant("minter", sp.unit), relative_royalties=sp.nat(600)),
                        sp.record(address=bob.address, role=sp.variant("minter", sp.unit), relative_royalties=sp.nat(200)),
                        sp.record(address=alice.address, role=sp.variant("custom", "test"), relative_royalties=sp.nat(200))
                    ]
                ))),
            to_=alice.address, amount=1000
        )
    ]).run(sender=admin)