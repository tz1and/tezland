import smartpy as sp

from contracts import TL_TokenRegistry, TL_LegacyRoyalties, TL_RoyaltiesAdapterLegacyAndV1, FA2
from contracts.utils import EnvUtils


@EnvUtils.view_helper
def getRoyalties(royalties_adaper, token_key) -> sp.Expr:
    return sp.view("get_royalties", sp.set_type_expr(royalties_adaper, sp.TAddress),
        sp.set_type_expr(token_key, TL_LegacyRoyalties.t_token_key),
        t = FA2.t_royalties_interop)


#
# Royalties adapter contract.
class TL_RoyaltiesAdapter(sp.Contract):
    def __init__(self, registry, v1_and_legacy_adapter, exception_optimization_level="default-line"):
        sp.Contract.__init__(self)

        self.add_flag("exceptions", exception_optimization_level)
        #self.add_flag("erase-comments")

        registry = sp.set_type_expr(registry, sp.TAddress)
        v1_and_legacy_adapter = sp.set_type_expr(v1_and_legacy_adapter, sp.TAddress)

        self.init_storage(
            registry = registry,
            v1_and_legacy_adapter = v1_and_legacy_adapter
        )


    @sp.entry_point
    def default(self):
        sp.failwith(sp.unit)


    @sp.onchain_view(pure=True)
    def get_royalties(self, token_key):
        """Gets token royalties and/or validate signed royalties."""
        sp.set_type(token_key, TL_LegacyRoyalties.t_token_key)

        royalties_type = sp.compute(TL_TokenRegistry.getRoyaltiesType(self.data.registry, token_key.fa2).open_some(sp.unit))

        with sp.if_(royalties_type == TL_TokenRegistry.royaltiesTz1andV2):
            # Just return V2 royalties.
            sp.result(FA2.getRoyalties(token_key.fa2, token_key.id).open_some(sp.unit))
        with sp.else_():
            # Call the V1 and legacy adapter.
            sp.result(TL_RoyaltiesAdapterLegacyAndV1.getRoyalties(self.data.v1_and_legacy_adapter,
                token_key, royalties_type).open_some(sp.unit))
