import smartpy as sp

from tezosbuilders_contracts_smartpy.utils import Utils


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
                ("moderation_contract", sp.TOption(sp.TAddress), lambda x : Utils.ifSomeRun(x, lambda y: Utils.onlyContract(y)))
            )
        else:
            def set_moderation_contract(self, moderation_contract):
                """Set moderation contract."""
                self.onlyAdministrator()
                Utils.ifSomeRun(moderation_contract, lambda y: Utils.onlyContract(y))
                self.data.moderation_contract = moderation_contract

            self.set_moderation_contract = sp.entry_point(set_moderation_contract, parameter_type=sp.TOption(sp.TAddress))
