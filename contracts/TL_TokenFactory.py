import smartpy as sp

from tz1and_contracts_smartpy.mixins.Administrable import Administrable
from tz1and_contracts_smartpy.mixins.Pausable import Pausable
from tz1and_contracts_smartpy.mixins.Upgradeable import Upgradeable
from tz1and_contracts_smartpy.mixins.ContractMetadata import ContractMetadata
from tz1and_contracts_smartpy.mixins.MetaSettings import MetaSettings

from contracts import TL_TokenRegistry, Tokens
from tz1and_contracts_smartpy.utils import Utils
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
    def __init__(self, administrator, registry, minter, blacklist, proxy_parent, metadata, paused=False, exception_optimization_level="default-line"):
        sp.Contract.__init__(self)

        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")

        administrator = sp.set_type_expr(administrator, sp.TAddress)
        registry = sp.set_type_expr(registry, sp.TAddress)
        minter = sp.set_type_expr(minter, sp.TAddress)
        proxy_parent = sp.set_type_expr(proxy_parent, sp.TAddress)

        # NOTE: args don't matter here since we set storage on origination.
        if EnvUtils.inTests():
            print(f"\x1b[35;20mWARNING: Using ItemCollectionProxyBase in TokenFactory for testing\x1b[0m")
            self.collection_contract = Tokens.ItemCollectionProxyBase(parent = proxy_parent,
                metadata = metadata, admin = administrator, blacklist = blacklist)
        else:
            self.collection_contract = Tokens.ItemCollectionProxyChild(parent = proxy_parent,
                metadata = metadata, admin = administrator, blacklist = blacklist)
        
        self.init_storage()

        self.addMetaSettings([
            ("registry", registry, sp.TAddress, lambda x : Utils.onlyContract(x)),
            ("minter", minter, sp.TAddress, lambda x : Utils.onlyContract(x)),
            ("proxy_parent", proxy_parent, sp.TAddress, lambda x : Utils.onlyContract(x))
        ])

        Administrable.__init__(self, administrator = administrator, include_views = False)
        Pausable.__init__(self, include_views = False, paused = paused)
        ContractMetadata.__init__(self, metadata = metadata)
        MetaSettings.__init__(self)
        Upgradeable.__init__(self)

        self.generateContractMetadata("tz1and TokenFactory", "tz1and token factory",
            authors=["852Kerfunkle <https://github.com/852Kerfunkle>"],
            source_location="https://github.com/tz1and",
            homepage="https://www.tz1and.com", license="UNLICENSED")


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
            administrator = self.data.settings.minter,
            metadata = sp.big_map({"": metadata_uri}),
            # Just the default values
            adhoc_operators = sp.set(),
            last_token_id = 0,
            ledger = sp.big_map(),
            operators = sp.big_map(),
            #paused = False,
            proposed_administrator = sp.none,
            token_extra = sp.big_map(),
            token_metadata = sp.big_map(),
            parent = self.data.settings.proxy_parent
        ))

        # Add private collection in token registry
        manage_collections_handle = sp.contract(
            TL_TokenRegistry.t_manage_collections,
            self.data.settings.registry, 
            entry_point = "manage_collections").open_some()

        sp.transfer([
            sp.variant("add_private", {
                originated_token: sp.record(
                    owner = sp.sender,
                    royalties_type = TL_TokenRegistry.royaltiesTz1andV2
                )}
            )], sp.mutez(0), manage_collections_handle)
