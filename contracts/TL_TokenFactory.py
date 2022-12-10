import smartpy as sp

from tezosbuilders_contracts_smartpy.mixins.Administrable import Administrable
from tezosbuilders_contracts_smartpy.mixins.Pausable import Pausable
from tezosbuilders_contracts_smartpy.mixins.Upgradeable import Upgradeable
from tezosbuilders_contracts_smartpy.mixins.ContractMetadata import ContractMetadata
from tezosbuilders_contracts_smartpy.mixins.MetaSettings import MetaSettings

from contracts import TL_TokenRegistry, FA2_proxy
from tezosbuilders_contracts_smartpy.utils import Utils
from contracts.utils import EnvUtils


#
# TokenFactory contract.
# NOTE: should be pausable for code updates.
class TL_TokenFactory(
    Administrable,
    ContractMetadata,
    Pausable,
    MetaSettings,
    Upgradeable,
    sp.Contract):
    def __init__(self, administrator, registry, minter, blacklist, proxy_parent, metadata, exception_optimization_level="default-line"):
        sp.Contract.__init__(self)

        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")

        administrator = sp.set_type_expr(administrator, sp.TAddress)
        registry = sp.set_type_expr(registry, sp.TAddress)
        minter = sp.set_type_expr(minter, sp.TAddress)
        proxy_parent = sp.set_type_expr(proxy_parent, sp.TAddress)

        # NOTE: args don't matter here since we set storage on origination.
        if EnvUtils.inTests():
            print(f"\x1b[35;20mWARNING: Using FA2ProxyBase in TokenFactory for testing\x1b[0m")
            self.collection_contract = FA2_proxy.FA2ProxyBase(metadata, administrator, blacklist, proxy_parent)
        else:
            self.collection_contract = FA2_proxy.FA2ProxyChild(metadata, administrator, blacklist, proxy_parent)
        
        self.init_storage(
            registry = registry,
            minter = minter,
            proxy_parent = proxy_parent
        )

        self.available_settings = [
            ("registry", sp.TAddress, lambda x : Utils.onlyContract(x)),
            ("minter", sp.TAddress, lambda x : Utils.onlyContract(x)),
            ("proxy_parent", sp.TAddress, lambda x : Utils.onlyContract(x))
        ]

        Administrable.__init__(self, administrator = administrator, include_views = False)
        Pausable.__init__(self, include_views = False)
        ContractMetadata.__init__(self, metadata = metadata)
        MetaSettings.__init__(self)
        Upgradeable.__init__(self)

        self.generate_contract_metadata()


    def generate_contract_metadata(self):
        """Generate a metadata json file with all the contract's offchain views."""
        metadata_base = {
            "name": 'tz1and TokenFactory',
            "description": 'tz1and token registry',
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


    #
    # Public entry points
    #
    @sp.entry_point(lazify = True)
    def create_token(self, metadata_uri):
        """Originate an FA2 token contract"""
        sp.set_type(metadata_uri, sp.TBytes)

        self.onlyUnpaused()

        Utils.validateIpfsUri(metadata_uri)

        # Originate FA2
        originated_token = sp.create_contract(contract = self.collection_contract, storage = sp.record(
            # The storage we need to modify
            administrator = self.data.minter,
            metadata = sp.big_map({"": metadata_uri}),
            # Just the default values
            adhoc_operators = sp.set(),
            last_token_id = 0,
            ledger = sp.big_map(),
            operators = sp.big_map(),
            paused = False,
            proposed_administrator = sp.none,
            token_extra = sp.big_map(),
            token_metadata = sp.big_map(),
            parent = self.data.proxy_parent
        ))

        # Add private collection in token registry
        manage_collections_handle = sp.contract(
            TL_TokenRegistry.t_manage_collections,
            self.data.registry, 
            entry_point = "manage_collections").open_some()

        sp.transfer([
            sp.variant("add_private", {
                originated_token: sp.record(
                    owner = sp.sender,
                    royalties_type = TL_TokenRegistry.royaltiesTz1andV2
                )}
            )], sp.mutez(0), manage_collections_handle)
