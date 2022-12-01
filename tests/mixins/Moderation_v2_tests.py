import smartpy as sp

Administrable = sp.io.import_script_from_url("file:contracts/mixins/Administrable.py").Administrable
MetaSettings = sp.io.import_script_from_url("file:contracts/mixins/MetaSettings.py").MetaSettings
mod_mixin = sp.io.import_script_from_url("file:contracts/mixins/Moderation_v2.py")


class ModerationTest(
    Administrable,
    mod_mixin.Moderation,
    sp.Contract):
    def __init__(self, administrator):
        Administrable.__init__(self, administrator = administrator)
        mod_mixin.Moderation.__init__(self)


class ModerationTestMetaSettings(
    ModerationTest,
    MetaSettings):
    def __init__(self, administrator):
        self.available_settings = []

        ModerationTest.__init__(self, administrator = administrator)
        MetaSettings.__init__(self)


@sp.add_test(name = "Moderation_v2_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("Moderation contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

    scenario.h2("Test Moderation")

    scenario.h3("Contract origination")
    moderation = ModerationTest(admin.address)
    scenario += moderation

    scenario.h3("set_moderation_contract")

    # Check default
    scenario.verify(moderation.data.moderation_contract == sp.none)

    # Check failure cases.
    for t in [(bob, moderation.address, "ONLY_ADMIN"), (admin, bob.address, "NOT_CONTRACT")]:
        sender, set_address, exception = t
        moderation.set_moderation_contract(sp.some(set_address)).run(sender = sender, valid = False, exception = exception)

    moderation.set_moderation_contract(sp.some(moderation.address)).run(sender = admin)
    scenario.verify(moderation.data.moderation_contract == sp.some(moderation.address))
    moderation.set_moderation_contract(sp.none).run(sender = admin)
    scenario.verify(moderation.data.moderation_contract == sp.none)

    # test meta settings
    scenario.h2("Test Moderation - MetaSettings")

    scenario.h3("Contract origination")
    moderation_meta = ModerationTestMetaSettings(admin.address)
    scenario += moderation_meta

    scenario.h3("update_settings")

    # Check default
    scenario.verify(moderation_meta.data.moderation_contract == sp.none)

    # Check failure cases.
    for t in [(bob, moderation_meta.address, "ONLY_ADMIN"), (admin, bob.address, "NOT_CONTRACT")]:
        sender, set_address, exception = t
        moderation_meta.update_settings([sp.variant("moderation_contract", sp.some(set_address))]).run(sender = sender, valid = False, exception = exception)

    moderation_meta.update_settings([sp.variant("moderation_contract", sp.some(moderation_meta.address))]).run(sender = admin)
    scenario.verify(moderation_meta.data.moderation_contract == sp.some(moderation_meta.address))
    moderation_meta.update_settings([sp.variant("moderation_contract", sp.none)]).run(sender = admin)
    scenario.verify(moderation_meta.data.moderation_contract == sp.none)