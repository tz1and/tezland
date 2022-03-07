import smartpy as sp

pause_mixin = sp.io.import_script_from_url("file:contracts/Pausable.py")
fa2_admin = sp.io.import_script_from_url("file:contracts/FA2_Administration.py")
upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")

# TODO: allow minting multiple places?

#
# Minter contract.
# NOTE: should be pausable for code updates.
class TL_Minter(
    pause_mixin.Pausable,
    fa2_admin.FA2_Administration,
    upgradeable_mixin.Upgradeable,
    sp.Contract):
    def __init__(self, administrator, items_contract, places_contract, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")
        
        self.init_storage(
            items_contract = items_contract,
            places_contract = places_contract,
            metadata = metadata,
            )
        pause_mixin.Pausable.__init__(self, administrator = administrator)
        fa2_admin.FA2_Administration.__init__(self, administrator = administrator)
        upgradeable_mixin.Upgradeable.__init__(self, administrator = administrator,
            entrypoints = ['mint_Item', 'mint_Place'])

    #
    # Manager-only entry points
    #
    @sp.entry_point
    def pause_all_fa2(self, new_paused):
        """The admin can pause/unpause items and places contracts"""
        sp.set_type(new_paused, sp.TBool)
        self.onlyAdministrator()

        with sp.for_("fa2", [self.data.items_contract, self.data.places_contract]) as fa2:
            # call items contract
            set_paused_handle = sp.contract(sp.TBool, fa2, 
                entry_point = "set_pause").open_some()
                
            sp.transfer(new_paused, sp.mutez(0), set_paused_handle)

    @sp.entry_point(lazify = True)
    def mint_Place(self, params):
        sp.set_type(params, sp.TRecord(
            address = sp.TAddress,
            metadata = sp.TBytes
        ).layout(("address", "metadata")))

        self.onlyAdministrator()
        self.onlyUnpaused()

        utils.fa2_nft_mint(
            [sp.record(
                to_=params.address,
                metadata={ '' : params.metadata }
            )],
            self.data.places_contract
        )

    #
    # Public entry points
    #
    @sp.entry_point(lazify = True)
    def mint_Item(self, params):
        sp.set_type(params, sp.TRecord(
            address = sp.TAddress,
            amount = sp.TNat,
            royalties = sp.TNat,
            contributors = FA2.t_contributor_map,
            metadata = sp.TBytes
        ).layout(("address", ("amount", ("royalties", ("contributors", "metadata"))))))

        self.onlyUnpaused()
        
        sp.verify((params.amount > 0) & (params.amount <= 10000) & ((params.royalties >= 0) & (params.royalties <= 250)),
            message = "PARAM_ERROR")

        utils.fa2_fungible_royalties_mint(
            [sp.record(
                to_=params.address,
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
