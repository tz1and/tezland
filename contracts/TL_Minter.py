import smartpy as sp

from tezosbuilders_contracts_smartpy.mixins.Administrable import Administrable
from tezosbuilders_contracts_smartpy.mixins.Pausable import Pausable
from tezosbuilders_contracts_smartpy.mixins.Upgradeable import Upgradeable
from contracts.mixins.Moderation import Moderation
from contracts.mixins.FA2_Administration import FA2_Administration

from contracts.legacy import FA2_legacy


def fa2_nft_mint(batch, contract):
    sp.set_type(batch, FA2_legacy.t_mint_nft_batch)
    sp.set_type(contract, sp.TAddress)
    c = sp.contract(
        FA2_legacy.t_mint_nft_batch,
        contract,
        entry_point='mint').open_some()
    sp.transfer(batch, sp.mutez(0), c)


#
# Minter contract.
# NOTE: should be pausable for code updates.
class TL_Minter(
    Administrable,
    Pausable,
    Moderation,
    FA2_Administration,
    Upgradeable,
    sp.Contract):
    def __init__(self, administrator, items_contract, places_contract, metadata,
        name="tz1and Minter", description="tz1and Items and Places minter", version="1.0.0", exception_optimization_level="default-line"):

        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")
        
        self.init_storage(
            items_contract = items_contract,
            places_contract = places_contract,
            metadata = metadata,
        )

        Administrable.__init__(self, administrator = administrator)
        Pausable.__init__(self)
        Moderation.__init__(self, moderation_contract = administrator)
        FA2_Administration.__init__(self)
        Upgradeable.__init__(self)

        self.generate_contract_metadata(name, description, version)

    def generate_contract_metadata(self, name, description, version):
        """Generate a metadata json file with all the contract's offchain views."""
        metadata_base = {
            "name": name,
            "description": description,
            "version": version,
            "interfaces": ["TZIP-016"],
            "authors": [
                "852Kerfunkle <https://github.com/852Kerfunkle>"
            ],
            "homepage": "https://www.tz1and.com",
            "source": {
                "tools": ["SmartPy"],
                "location": "https://github.com/tz1and",
            },
            "license": { "name": "MIT" }
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
    # Manager-only entry points
    #
    @sp.entry_point
    def pause_all_fa2(self, new_paused):
        """The admin can pause/unpause items and places contracts."""
        sp.set_type(new_paused, sp.TBool)
        self.onlyAdministrator()

        with sp.for_("fa2", [self.data.items_contract, self.data.places_contract]) as fa2:
            # call items contract
            set_paused_handle = sp.contract(sp.TBool, fa2, 
                entry_point = "set_pause").open_some()
                
            sp.transfer(new_paused, sp.mutez(0), set_paused_handle)

    @sp.entry_point
    def clear_adhoc_operators_all_fa2(self):
        """The admin can clear adhoc ops for items and places contracts."""
        self.onlyAdministrator()
    
        with sp.for_("fa2", [self.data.items_contract, self.data.places_contract]) as fa2:
            # call items contract
            set_paused_handle = sp.contract(FA2_legacy.t_adhoc_operator_params, fa2, 
                entry_point = "update_adhoc_operators").open_some()
                
            sp.transfer(sp.variant("clear_adhoc_operators", sp.unit),
                sp.mutez(0), set_paused_handle)

    @sp.entry_point(lazify = True)
    def mint_Place(self, params):
        sp.set_type(params, FA2_legacy.t_mint_nft_batch)

        self.onlyAdministrator()
        self.onlyUnpaused()

        fa2_nft_mint(
            params,
            self.data.places_contract
        )

    #
    # Public entry points
    #
    @sp.entry_point(lazify = True)
    def mint_Item(self, params):
        sp.set_type(params, sp.TRecord(
            to_ = sp.TAddress,
            amount = sp.TNat,
            royalties = sp.TNat,
            contributors = FA2_legacy.t_contributor_list,
            metadata = sp.TBytes
        ).layout(("to_", ("amount", ("royalties", ("contributors", "metadata"))))))

        self.onlyUnpaused()
        
        sp.verify((params.amount > 0) & (params.amount <= 10000) & ((params.royalties >= 0) & (params.royalties <= 250)),
            message = "PARAM_ERROR")

        FA2_legacy.fa2_fungible_royalties_mint(
            [sp.record(
                to_=params.to_,
                amount=params.amount,
                token=sp.variant("new", sp.record(
                    metadata={ '' : params.metadata },
                    royalties=sp.record(
                        royalties=params.royalties,
                        contributors=params.contributors)
                    )
                )
            )],
            self.data.items_contract
        )
