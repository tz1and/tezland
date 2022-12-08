import smartpy as sp

from contracts import TL_LegacyRoyalties, TL_TokenRegistry, FA2
from contracts.legacy import FA2_legacy
from contracts.utils import EnvUtils


t_get_royalties_type = sp.TRecord(
    token_key = TL_LegacyRoyalties.t_token_key,
    royalties_type = TL_TokenRegistry.t_royalties_bounded
).layout(("token_key", "royalties_type"))


@EnvUtils.view_helper
def getRoyalties(royalties_adaper, token_key, royalties_type) -> sp.Expr:
    return sp.view("get_royalties", sp.set_type_expr(royalties_adaper, sp.TAddress),
        sp.set_type_expr(sp.record(token_key = token_key, royalties_type = royalties_type), t_get_royalties_type),
        t = FA2.t_royalties_interop)


#
# Royalties adapter contract.
class TL_RoyaltiesAdapterLegacyAndV1(sp.Contract):
    def __init__(self, legacy_royalties, metadata, exception_optimization_level="default-line"):
        sp.Contract.__init__(self)

        self.add_flag("exceptions", exception_optimization_level)
        #self.add_flag("erase-comments")

        legacy_royalties = sp.set_type_expr(legacy_royalties, sp.TAddress)

        self.init_storage(
            legacy_royalties = legacy_royalties
        )

        self.generate_contract_metadata()


    def generate_contract_metadata(self):
        """Generate a metadata json file with all the contract's offchain views."""
        metadata_base = {
            "name": 'tz1and RoyaltiesAdapterLegacyAndV1',
            "description": 'tz1and royalties adapter',
            "version": "1.0.0",
            "interfaces": ["TZIP-016"],
            "authors": [
                "852Kerfunkle <https://github.com/852Kerfunkle>"
            ],
            "homepage": "https://www.tz1and.com",
            "source": {
                "tools": ["SmartPy"],
                "location": "https://github.com/tz1and",
            },
            "license": { "name": "UNLICENSED" }
        }
        offchain_views = []
        for f in dir(self):
            attr = getattr(self, f)
            if isinstance(attr, sp.OnOffchainView):
                # Include onchain views as tip 16 offchain views
                offchain_views.append(attr)
        metadata_base["views"] = offchain_views
        self.init_metadata("metadata_base", metadata_base)


    @sp.entry_point
    def default(self):
        sp.failwith(sp.unit)


    @sp.onchain_view(pure=True)
    def get_royalties(self, params):
        """Gets token royalties and/or validate signed royalties."""
        sp.set_type(params, t_get_royalties_type)

        # Type 1 = tz1and v1 royalties.
        with sp.if_(params.royalties_type == TL_TokenRegistry.royaltiesTz1andV1):
            # Convert V1 royalties to V2.
            royalties = sp.compute(FA2_legacy.getRoyalties(params.token_key.fa2, params.token_key.id).open_some(sp.unit))
            royalties_v2 = sp.local("royalties_v2", sp.record(total = 1000, shares = {}), FA2.t_royalties_interop)

            with sp.for_("contributor", royalties.contributors) as contributor:
                existing_share = royalties_v2.value.shares.get(contributor.address, sp.nat(0))
                new_share = existing_share + (contributor.relative_royalties * royalties.royalties / 1000)
                royalties_v2.value.shares[contributor.address] = new_share

            sp.result(royalties_v2.value)
        with sp.else_():
            # Type 0 = Registry does not know about this token's royalties.
            with sp.if_(params.royalties_type == TL_TokenRegistry.royaltiesLegacy):
                # Get royalties from legacy royalties contract.
                sp.result(TL_LegacyRoyalties.getRoyalties(self.data.legacy_royalties, params.token_key).open_some(sp.unit))
            with sp.else_():
                sp.failwith(sp.unit)
