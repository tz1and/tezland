import smartpy as sp

registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
legacy_royalties_contract = sp.io.import_script_from_url("file:contracts/TL_LegacyRoyalties.py")
royalties_adapter_legacy_contract = sp.io.import_script_from_url("file:contracts/TL_RoyaltiesAdapterLegacyAndV1.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")
FA2_legacy = sp.io.import_script_from_url("file:contracts/legacy/FA2_legacy.py")


# TODO: layer adapters for other tokens!
# TODO: test adapters


def getTokenRoyalties(royalties_adaper: sp.TAddress, fa2: sp.TAddress, token_id: sp.TNat):
    sp.set_type(royalties_adaper, sp.TAddress)
    sp.set_type(fa2, sp.TAddress)
    sp.set_type(token_id, sp.TNat)
    return sp.compute(sp.view("get_token_royalties", royalties_adaper,
        sp.set_type_expr(
            sp.record(fa2=fa2, id=token_id),
            legacy_royalties_contract.t_token_key),
        t = FA2.t_royalties_interop).open_some())


#
# Royalties adapter contract.
class TL_RoyaltiesAdapter(sp.Contract):
    def __init__(self, registry, v1_and_legacy_adapter, metadata, exception_optimization_level="default-line"):

        self.add_flag("exceptions", exception_optimization_level)
        #self.add_flag("erase-comments")

        registry = sp.set_type_expr(registry, sp.TAddress)
        v1_and_legacy_adapter = sp.set_type_expr(v1_and_legacy_adapter, sp.TAddress)

        self.init_storage(
            registry = registry,
            v1_and_legacy_adapter = v1_and_legacy_adapter
        )

        self.generate_contract_metadata()


    def generate_contract_metadata(self):
        """Generate a metadata json file with all the contract's offchain views."""
        metadata_base = {
            "name": 'tz1and RoyaltiesAdapter',
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
    def get_token_royalties(self, params):
        """Gets token royalties and/or validate signed royalties."""
        sp.set_type(params, legacy_royalties_contract.t_token_key)

        royalties_type = sp.local("royalties_type", sp.view("get_royalties_type", self.data.registry,
            params.fa2, t = registry_contract.t_royalties_bounded).open_some(sp.unit))

        with sp.if_(royalties_type.value == registry_contract.royaltiesTz1andV2):
            # Just return V2 royalties.
            sp.result(FA2.get_token_royalties(params.fa2, params.id, sp.unit))
        with sp.else_():
            # Call the V1 and legacy adapter.
            sp.result(sp.view("get_token_royalties", self.data.v1_and_legacy_adapter,
                sp.set_type_expr(
                    sp.record(token_key = params, royalties_type = royalties_type.value),
                    royalties_adapter_legacy_contract.t_get_token_royalties_type),
                t = FA2.t_royalties_interop).open_some(sp.unit))
