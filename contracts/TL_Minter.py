import smartpy as sp

pausable_contract = sp.io.import_script_from_url("file:contracts/Pausable.py")
fa2_admin = sp.io.import_script_from_url("file:contracts/FA2_Administration.py")
fa2_royalties = sp.io.import_script_from_url("file:contracts/FA2_Royalties.py")
upgradeable = sp.io.import_script_from_url("file:contracts/Upgradeable.py")


#
# Minter contract.
# NOTE: should be pausable for code updates.
class TL_Minter(pausable_contract.Pausable, fa2_admin.FA2_Administration, upgradeable.Upgradeable):
    def __init__(self, administrator, items_contract, places_contract, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")
        #self.add_flag("initial-cast")
        self.init_storage(
            items_contract = items_contract,
            item_id_counter = sp.nat(0),
            places_contract = places_contract,
            metadata = metadata,
            place_id_counter = sp.nat(0),
            )
        pausable_contract.Pausable.__init__(self, administrator = administrator)
        fa2_admin.FA2_Administration.__init__(self, administrator = administrator)
        upgradeable.Upgradeable.__init__(self, administrator = administrator,
            entrypoints = ['mint_Item', 'mint_Place'])

    #
    # Manager-only entry points
    #
    @sp.entry_point
    def pause_all_fa2(self, new_paused):
        """The admin can pause/unpause items and places contracts"""
        sp.set_type(new_paused, sp.TBool)
        self.onlyAdministrator()

        sp.for fa2 in [self.data.items_contract, self.data.places_contract]:
            # call items contract
            set_paused_handle = sp.contract(sp.TBool, fa2, 
                entry_point = "set_paused").open_some()
                
            sp.transfer(new_paused, sp.mutez(0), set_paused_handle)

    @sp.entry_point(lazify = True)
    def mint_Place(self, params):
        sp.set_type(params, sp.TRecord(
            address = sp.TAddress,
            metadata = sp.TBytes
        ).layout(("address", "metadata")))

        self.onlyAdministrator()
        self.onlyUnpaused()
        
        c = sp.contract(
            sp.TRecord(
                address=sp.TAddress,
                amount=sp.TNat,
                token_id=sp.TNat,
                metadata=sp.TMap(sp.TString, sp.TBytes)
            ).layout(("address", ("amount", ("token_id", "metadata")))),
            self.data.places_contract, 
            entry_point = "mint").open_some()
            
        sp.transfer(
            sp.record(
                address=params.address,
                amount=1,
                token_id=self.data.place_id_counter,
                metadata={ '' : params.metadata }), 
            sp.mutez(0), 
            c)
        
        self.data.place_id_counter += 1

    #
    # Public entry points
    #
    @sp.entry_point(lazify = True)
    def mint_Item(self, params):
        sp.set_type(params, sp.TRecord(
            address = sp.TAddress,
            amount = sp.TNat,
            royalties = sp.TNat,
            contributors = fa2_royalties.FA2_Royalties.CONTRIBUTOR_MAP_TYPE,
            metadata = sp.TBytes
        ).layout(("address", ("amount", ("royalties", ("contributors", "metadata"))))))

        self.onlyUnpaused()
        
        sp.verify((params.amount > 0) & (params.amount <= 10000) & ((params.royalties >= 0) & (params.royalties <= 250)),
            message = "PARAM_ERROR")
        
        c = sp.contract(
            sp.TRecord(
                address=sp.TAddress,
                amount=sp.TNat,
                token_id=sp.TNat,
                metadata=sp.TMap(sp.TString, sp.TBytes),
                royalties=fa2_royalties.FA2_Royalties.ROYALTIES_TYPE
            ).layout(("address", ("amount", ("token_id", ("metadata", "royalties"))))),
            self.data.items_contract, 
            entry_point = "mint").open_some()
            
        sp.transfer(
            sp.record(
                address=params.address,
                amount=params.amount,
                token_id=self.data.item_id_counter,
                metadata={ '' : params.metadata },
                royalties=sp.record(
                    royalties=params.royalties,
                    contributors=params.contributors)), 
            sp.mutez(0), 
            c)
        
        self.data.item_id_counter += 1
