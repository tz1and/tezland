import smartpy as sp

utils = sp.io.import_script_from_url("file:contracts/utils/Utils.py")


# Mixins required: Administrable
class Moderation:
    """Mixin to add moderation_contract address to a contract's storage.
    
    Can then later be used through add moderation functions through upgrades."""
    def __init__(self):
        self.update_initial_storage(
            moderation_contract = sp.set_type_expr(sp.none, sp.TOption(sp.TAddress))
        )

        if hasattr(self, 'available_settings'):
            self.available_settings.append(
                ("moderation_contract", sp.TOption(sp.TAddress), lambda x : utils.ifSomeRun(x, lambda y: utils.onlyContract(y)))
            )
        else:
            def set_moderation_contract(self, moderation_contract):
                """Set moderation contract."""
                sp.set_type(moderation_contract, sp.TOption(sp.TAddress))
                self.onlyAdministrator()
                utils.ifSomeRun(moderation_contract, lambda y: utils.onlyContract(y))
                self.data.moderation_contract = moderation_contract

            self.set_moderation_contract = sp.entry_point(set_moderation_contract)
