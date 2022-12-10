import smartpy as sp

from contracts import FA2_proxy, TL_Blacklist, FA2


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

    scenario.h3("Test env")
    scenario.h4("Blacklist")
    blacklist = TL_Blacklist.TL_Blacklist(admin.address,
        sp.utils.metadata_of_url("ipfs://example"))
    scenario += blacklist

    scenario.h3("Contract origination")
    scenario.h4("base")
    base = FA2_proxy.FA2ProxyBase(sp.utils.metadata_of_url("ipfs://example"),
        admin.address, blacklist.address, admin.address)
    scenario += base

    scenario.h4("parent")
    parent = FA2_proxy.FA2ProxyParent(sp.utils.metadata_of_url("ipfs://example"),
        admin.address, blacklist.address, admin.address)
    scenario += parent

    scenario.h4("child")
    child = FA2_proxy.FA2ProxyChild(sp.utils.metadata_of_url("ipfs://example"),
        admin.address, blacklist.address, parent.address)
    scenario += child

    # Test updating eps, chaging parent, permissions.

    scenario.h3("Tests")
    scenario.h4("child: set_parent")

    # only admin can change parent!
    for acc in [alice, bob, admin]:
        child.set_parent(blacklist.address).run(
            sender=acc,
            valid=(True if acc is admin else False),
            exception=(None if acc is admin else "ONLY_ADMIN"))

    # can only change parent to a contract
    child.set_parent(bob.address).run(sender=admin, valid=False, exception="NOT_CONTRACT")
    child.set_parent(parent.address).run(sender=admin)

    scenario.h4("parent: update_ep")

    def test_transfer_update(self, params):
        sp.set_type(params, FA2.t_transfer_params)
        sp.failwith("FAIL")

    upgrade_transfer = sp.record(id = sp.contract_entrypoint_id(parent, "transfer"), new_code = sp.utils.wrap_entry_point("transfer", test_transfer_update))

    # only admin can upgrade entrypoints
    for acc in [alice, bob, admin]:
        parent.update_ep(upgrade_transfer).run(
            sender=acc,
            valid=(True if acc is admin else False),
            exception=(None if acc is admin else "ONLY_ADMIN"))

    #
    # mint. NOTE: breaks interpreter LOL
    #
#    scenario.h3("mint")
#
#    scenario.show(parent.get_ep_lambda(sp.variant("mint", sp.unit)))
#
#    child.default(sp.variant("mint", [sp.record(
#            token=sp.variant("new", sp.record(
#                metadata={"": sp.utils.bytes_of_string("test_metadata")},
#                royalties={})),
#            to_=alice.address, amount=1000
#        )
#    ])).run(sender=admin)