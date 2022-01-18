import smartpy as sp

pausable_contract = sp.io.import_script_from_url("file:contracts/Pausable.py")

# TODO: distinction between manager and admin?

class TL_Minter(pausable_contract.Pausable):
    def __init__(self, manager, items_contract, places_contract, metadata):
        self.init_storage(
            manager = manager,
            items_contract = items_contract,
            item_id = sp.nat(0),
            places_contract = places_contract,
            metadata = metadata,
            place_id = sp.nat(0),
            paused = False,
            royalties = sp.big_map(tkey=sp.TNat, tvalue=sp.TRecord(creator=sp.TAddress, royalties=sp.TNat))
            )

    # This lets the manager regain admin to the items FA2 contract.
    @sp.entry_point
    def regain_admin_Items(self):
        self.onlyPaused()
        self.onlyManager()

        c = sp.contract(
            sp.TAddress,
            self.data.items_contract, 
            entry_point = "set_administrator").open_some()
            
        sp.transfer(
            self.data.manager, 
            sp.mutez(0), 
            c)

    # This lets the manager regain admin to the places FA2 contract.
    @sp.entry_point
    def regain_admin_Places(self):
        self.onlyPaused()
        self.onlyManager()

        c = sp.contract(
            sp.TAddress,
            self.data.places_contract, 
            entry_point = "set_administrator").open_some()
            
        sp.transfer(
            self.data.manager, 
            sp.mutez(0), 
            c)

    @sp.entry_point(lazify = True)
    def mint_Item(self, params):
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
            token_id=self.data.item_id,
            metadata={ '' : params.metadata }
            ), 
            sp.mutez(0), 
            c)
        
        self.data.royalties[self.data.item_id] = sp.record(creator=sp.sender, royalties=params.royalties)
        self.data.item_id += 1

    @sp.entry_point(lazify = True)
    def mint_Place(self, params):
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
            token_id=self.data.place_id,
            metadata={ '' : params.metadata }
            ), 
            sp.mutez(0), 
            c)
        
        self.data.place_id += 1

    @sp.onchain_view()
    def get_royalties(self, id):
        # sp.result is used to return the view result (the contract storage in this case)
        sp.result(self.data.royalties[id])

    #
    # Update code
    #
    @sp.entry_point
    def update_mint_Item(self, new_code):
        self.onlyManager()
        sp.set_entry_point("mint_Item", new_code)

    @sp.entry_point
    def update_mint_Place(self, new_code):
        self.onlyManager()
        sp.set_entry_point("mint_Place", new_code)

# A a compilation target (produces compiled code)
#sp.add_compilation_target("TL_Minter", TL_Minter(
    #sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV"), # Manager
#    sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV") # Items
#    ))
