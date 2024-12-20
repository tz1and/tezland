import smartpy as sp

from tz1and_contracts_smartpy.mixins.Administrable import Administrable
from contracts.legacy.mixins import Upgradeable


class UpgradeableTest(
    Administrable,
    Upgradeable.Upgradeable,
    sp.Contract):
    def __init__(self, administrator):
        sp.Contract.__init__(self)
        self.init_storage(
            counter = sp.int(0)
        )
        Administrable.__init__(self, administrator = administrator)
        Upgradeable.Upgradeable.__init__(self)

    @sp.entry_point(lazify = True)
    def test_entry(self, params):
        sp.set_type(params.val, sp.TInt)
        self.data.counter += params.val

    @sp.entry_point(lazify = True)
    def another_entry(self, params):
        sp.set_type(params.val, sp.TInt)
        self.data.counter *= params.val


def test_entry_update(self, params):
    sp.set_type(params.val, sp.TInt)
    self.data.counter -= params.val

def another_entry_update(self, params):
    sp.set_type(params.val, sp.TInt)
    self.data.counter = params.val


@sp.add_test(name = "Upgradeable_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    # create upgrade contract
    upgrade = UpgradeableTest(admin.address)
    scenario += upgrade

    scenario.verify_equal(upgrade.upgradeable_entrypoints, ['another_entry', 'test_entry'])

    # test entry
    upgrade.test_entry(val = sp.int(2)).run(sender = alice)
    scenario.verify(upgrade.data.counter == sp.int(2))

    upgrade.another_entry(val = sp.int(2)).run(sender = alice)
    scenario.verify(upgrade.data.counter == sp.int(4))

    # update
    upgrade_test_entry = sp.record(ep_name = sp.variant('test_entry', sp.unit), new_code = sp.utils.wrap_entry_point("test_entry", test_entry_update))
    upgrade_another_entry = sp.record(ep_name = sp.variant('another_entry', sp.unit), new_code = sp.utils.wrap_entry_point("another_entry", another_entry_update))

    upgrade.update_ep(upgrade_test_entry).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    upgrade.update_ep(upgrade_another_entry).run(sender = alice, valid = False, exception = "ONLY_ADMIN")

    upgrade.update_ep(upgrade_test_entry).run(sender = admin)
    upgrade.update_ep(upgrade_another_entry).run(sender = admin)

    # test updated entrypoints
    upgrade.test_entry(val = sp.int(5)).run(sender = alice)
    scenario.verify(upgrade.data.counter == sp.int(-1))

    upgrade.another_entry(val = sp.int(1337)).run(sender = alice)
    scenario.verify(upgrade.data.counter == sp.int(1337))
