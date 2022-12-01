import smartpy as sp


# Mixins required: Administrable
class Moderation:
    """Mixin to add moderation_contract address to a contract's storage.
    
    Can then later be used through add moderation functions through upgrades."""
    def __init__(self, moderation_contract):
        self.update_initial_storage(
            moderation_contract = moderation_contract
        )

    @sp.entry_point
    def set_moderation_contract(self, moderation_contract):
        """Set moderation contract.
        """
        sp.set_type(moderation_contract, sp.TAddress)
        self.onlyAdministrator()
        self.data.moderation_contract = moderation_contract
