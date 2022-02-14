import smartpy as sp

pausable_contract = sp.io.import_script_from_url("file:contracts/Pausable.py")

#
# Minter contract.
# NOTE: should be pausable for code updates.
class TL_Minter(pausable_contract.Pausable):
    def __init__(self, manager, items_contract, places_contract, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")
        #self.add_flag("initial-cast")
        self.init_storage(
            manager = manager,
            items_contract = items_contract,
            item_id_counter = sp.nat(0),
            places_contract = places_contract,
            metadata = metadata,
            place_id_counter = sp.nat(0),
            paused = False,
            royalties = sp.big_map(tkey=sp.TNat, tvalue=sp.TRecord(creator=sp.TAddress, royalties=sp.TNat))
            )

    #
    # Manager-only entry points
    #
    # NOTE: I'm not sure this should ever be needed, to be honest.
    @sp.entry_point
    def set_paused_tokens(self, new_paused):
        """The manager can pause/unpause items and places contracts"""
        sp.set_type(new_paused, sp.TBool)
        self.onlyManager()

        # call items contract
        itemsc = sp.contract(sp.TBool, self.data.items_contract, 
            entry_point = "set_pause").open_some()
            
        sp.transfer(new_paused, sp.mutez(0), itemsc)

        # call places contract
        placesc = sp.contract(sp.TBool, self.data.places_contract, 
            entry_point = "set_pause").open_some()
            
        sp.transfer(new_paused, sp.mutez(0), placesc)

    # NOTE: I don't see why this would ever be needed.
    #@sp.entry_point
    #def regain_admin_Items(self):
    #    """This lets the manager regain admin to the items FA2 contract."""
    #    self.onlyPaused()
    #    self.onlyManager()
    #
    #    c = sp.contract(
    #        sp.TAddress,
    #        self.data.items_contract, 
    #        entry_point = "set_administrator").open_some()
    #        
    #    sp.transfer(
    #        self.data.manager, 
    #        sp.mutez(0), 
    #        c)

    #@sp.entry_point
    #def regain_admin_Places(self):
    #    """This lets the manager regain admin to the places FA2 contract."""
    #    self.onlyPaused()
    #    self.onlyManager()
    #
    #    c = sp.contract(
    #        sp.TAddress,
    #        self.data.places_contract, 
    #        entry_point = "set_administrator").open_some()
    #        
    #    sp.transfer(
    #        self.data.manager, 
    #        sp.mutez(0), 
    #        c)

    @sp.entry_point(lazify = True)
    def mint_Place(self, params):
        sp.set_type(params.address, sp.TAddress)
        sp.set_type(params.metadata, sp.TBytes)

        self.onlyManager()
        self.onlyUnpaused()
        
        c = sp.contract(
            sp.TRecord(
            address=sp.TAddress,
            amount=sp.TNat,
            token_id=sp.TNat,
            metadata=sp.TMap(sp.TString, sp.TBytes)
            ),
            self.data.places_contract, 
            entry_point = "mint").open_some()
            
        sp.transfer(
            sp.record(
            address=params.address,
            amount=1,
            token_id=self.data.place_id_counter,
            metadata={ '' : params.metadata }
            ), 
            sp.mutez(0), 
            c)
        
        self.data.place_id_counter += 1

    #
    # Public entry points
    #
    @sp.entry_point(lazify = True)
    def mint_Item(self, params):
        sp.set_type(params.address, sp.TAddress)
        sp.set_type(params.amount, sp.TNat)
        sp.set_type(params.royalties, sp.TNat)
        sp.set_type(params.metadata, sp.TBytes)

        self.onlyUnpaused()
        
        sp.verify((params.amount > 0) & (params.amount <= 10000) & ((params.royalties >= 0) & (params.royalties <= 250)),
            message = "PARAM_ERROR")
        
        c = sp.contract(
            sp.TRecord(
            address=sp.TAddress,
            amount=sp.TNat,
            token_id=sp.TNat,
            metadata=sp.TMap(sp.TString, sp.TBytes)
            ),
            self.data.items_contract, 
            entry_point = "mint").open_some()
            
        sp.transfer(
            sp.record(
            address=params.address,
            amount=params.amount,
            token_id=self.data.item_id_counter,
            metadata={ '' : params.metadata }
            ), 
            sp.mutez(0), 
            c)
        
        self.data.royalties[self.data.item_id_counter] = sp.record(creator=sp.sender, royalties=params.royalties)
        self.data.item_id_counter += 1

    #
    # Views
    #
    @sp.onchain_view()
    def get_item_royalties(self, token_id):
        sp.set_type(token_id, sp.TNat)
        # sp.result is used to return the view result (the contract storage in this case)
        sp.result(self.data.royalties[token_id])

    #
    # Update code
    #
    @sp.entry_point
    def upgrade_code_mint_Item(self, new_code):
        self.onlyManager()
        sp.set_entry_point("mint_Item", new_code)

    @sp.entry_point
    def upgrade_code_mint_Place(self, new_code):
        self.onlyManager()
        sp.set_entry_point("mint_Place", new_code)

# A a compilation target (produces compiled code)
#sp.add_compilation_target("TL_Minter", TL_Minter(
    #sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV"), # Manager
#    sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV") # Items
#    ))
