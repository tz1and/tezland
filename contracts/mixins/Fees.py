import smartpy as sp

from tz1and_contracts_smartpy.mixins.MetaSettings import MetaSettings
from tz1and_contracts_smartpy.utils import Settings

default_fees = 35
max_fees = 150

# Required mixins: Administrable
class Fees:
    def __init__(self, fees_to):
        if isinstance(self, MetaSettings):
            self.addMetaSettings([
                # Fees must be < 10%.
                ("fees", default_fees, sp.TNat, lambda x: sp.verify(x <= max_fees, message = "FEE_ERROR")),
                ("fees_to", fees_to, sp.TAddress, None)
            ])
        else:
            self.update_initial_storage(
                settings = sp.record(
                    **Settings.getPrevSettingsFields(self),
                    fees = sp.nat(default_fees),
                    fees_to = sp.set_type_expr(fees_to, sp.TAddress))
            )

            def update_fees(self, fees):
                """Call to set fees in permille or fee recipient.
                Fees must be <= than 60 permille.
                """
                sp.set_type(fees, sp.TNat)
                self.onlyAdministrator()
                sp.verify(fees <= max_fees, message = "FEE_ERROR") # let's not get greedy
                self.data.settings.fees = fees

            def update_fees_to(self, fees_to):
                """Set fee recipient.
                """
                sp.set_type(fees_to, sp.TAddress)
                self.onlyAdministrator()
                self.data.settings.fees_to = fees_to

            self.update_fees = sp.entry_point(update_fees, parameter_type=sp.TNat)
            self.update_fees_to = sp.entry_point(update_fees_to, parameter_type=sp.TAddress)

