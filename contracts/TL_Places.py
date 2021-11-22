# The (market)places contract.
#
# Each marketplace belongs to a lot (an FA2 token that is the "land").
# Items (another type of token) can be stored on your (market)place, either to sell
# or just to build something nice.

import smartpy as sp

manager_contract = sp.io.import_script_from_url("file:contracts/Manageable.py")

class TL_Places(manager_contract.Manageable):
    def __init__(self, manager, token, minter):
        self.init_storage(
            manager = manager,
            token = token,
            minter = minter,
            fees = sp.nat(25),
            # some information about the place
            places = sp.big_map(tkey=sp.TBytes, tvalue=sp.TRecord(
                counter=sp.TNat,
                owner=sp.TAddress
                )),
            # since we can't have nested bigmaps, we store the items as a map from (mapid, itemid)
            # we can search for part of the key in better call dev
            stored_items=sp.big_map(tkey=sp.TPair(sp.TBytes, sp.TNat), tvalue=sp.TRecord(
                #issuer=sp.TAddress, # Obviously the owner of the lot
                item_amount=sp.TNat, # number of objects to store.
                item_id=sp.TNat, # object id
                for_sale=sp.TBool, # Available to be sold?
                xtz_per_item=sp.TMutez, # 0 if not for sale.
                #royalties=sp.TNat, # royalties come from the minter via on-chain view
                #creator=sp.TAddress # same as above
                item_data=sp.TBytes # we store the transforms as bytes. 4 floats for quat, 1 float scale, 3 floats pos = 32 bytes
                # TODO: store transform as half floats? could be worth it...
                ))
            )

    @sp.entry_point
    def set_fees(self, fees):
        sp.set_type(fees, sp.TNat)
        self.onlyManager()
        sp.verify(fees <= 60) # let's not get greedy
        self.data.fees = fees

    @sp.entry_point(lazify = True)
    def new_place(self, lot_id):
        sp.set_type(lot_id, sp.TBytes)

         # skip if it exists. we don't want to overwrite nested big maps.
        sp.if self.data.places.contains(lot_id):
            sp.failwith("place exists")
        # insert new place
        sp.else:
            self.data.places[lot_id] = sp.record(
                counter = 0,
                owner=sp.sender,
                #stored_items = sp.big_map(tkey=sp.TNat, tvalue=sp.TRecord(
                #    item_amount = sp.TNat,
                #    item_id = sp.TNat,
                #    for_sale = sp.TBool,
                #    xtz_per_item = sp.TMutez))
                )

    @sp.entry_point(lazify = True)
    def place_item(self, params):
        sp.set_type(params.lot_id, sp.TBytes)
        sp.set_type(params.token_id, sp.TNat)
        sp.set_type(params.token_amount, sp.TNat)
        sp.set_type(params.xtz_per_token, sp.TMutez)
        sp.set_type(params.item_data, sp.TBytes)

        sp.verify(sp.len(params.item_data) == 16, message = "DATA_LEN")

        # get the place
        this_place = self.data.places[params.lot_id]

        # make sure place is owned
        sp.verify(sp.sender == this_place.owner, message = "NOT_OWNER")

        # Make sure item is owned.
        item_balance = sp.view("get_balance_oc",
            self.data.token,
            sp.record(owner = sp.sender, token_id = params.token_id),
            t = sp.TNat).open_some()
        sp.verify(item_balance >= params.token_amount, message = "ITEM_NOT_OWNED")

        self.data.stored_items[sp.pair(params.lot_id, this_place.counter)] = sp.record(
            item_amount = params.token_amount,
            item_id = params.token_id,
            for_sale = True,
            xtz_per_item = params.xtz_per_token,
            item_data = params.item_data)

        this_place.counter += 1

    @sp.entry_point(lazify = True)
    def place_items(self, params):
        sp.set_type(params.item_list, sp.TList(sp.TRecord(
            token_id=sp.TNat,
            token_amount=sp.TNat,
            xtz_per_token=sp.TMutez,
            item_data=sp.TBytes)))
        sp.set_type(params.lot_id, sp.TBytes)

        # get the place
        this_place = self.data.places[params.lot_id]

        # make sure place is owned
        sp.verify(sp.sender == this_place.owner, message = "NOT_OWNER")

        sp.for curr in params.item_list:
            sp.verify(sp.len(curr.item_data) == 16, message = "DATA_LEN")

            # Make sure item is owned.
            item_balance = sp.view("get_balance_oc",
                self.data.token,
                sp.record(owner = sp.sender, token_id = curr.token_id),
                t = sp.TNat).open_some()
            sp.verify(item_balance >= curr.token_amount, message = "ITEM_NOT_OWNED")

            self.data.stored_items[sp.pair(params.lot_id, this_place.counter)] = sp.record(
                item_amount = curr.token_amount,
                item_id = curr.token_id,
                for_sale = True,
                xtz_per_item = curr.xtz_per_token,
                item_data = curr.item_data)

            this_place.counter += 1

    @sp.entry_point(lazify = True)
    def remove_items(self, params):
        sp.set_type(params.lot_id, sp.TBytes)
        sp.set_type(params.item_list, sp.TList(sp.TNat))

        # get the place
        this_place = self.data.places[params.lot_id]

        # make sure place is owned
        sp.verify(sp.sender == this_place.owner, message = "NOT_OWNER")

        # remove the items
        sp.for curr in params.item_list:
            del self.data.stored_items[sp.pair(params.lot_id, curr)]

    @sp.entry_point(lazify = True)
    def remove_item(self, params):
        sp.set_type(params.lot_id, sp.TBytes)
        sp.set_type(params.item_id, sp.TNat)

        # get the place
        this_place = self.data.places[params.lot_id]

        # make sure place is owned
        sp.verify(sp.sender == this_place.owner, message = "NOT_OWNER")

        # remove the item
        del self.data.stored_items[sp.pair(params.lot_id, params.item_id)]

    @sp.entry_point(lazify = True)
    def get_item(self, params):
        sp.set_type(params.lot_id, sp.TBytes)
        sp.set_type(params.item_id, sp.TNat)

        # get the place
        this_place = self.data.places[params.lot_id]
        # get the item
        the_item = self.data.stored_items[sp.pair(params.lot_id, params.item_id)]

        # todo: make sure it's for sale, the transfered amount is correct, etc.
        sp.verify(the_item.for_sale == True, message = "NOT_FOR_SALE")
        sp.verify(the_item.xtz_per_item == sp.amount, message = "WRONG_AMOUNT")

        # send monies
        sp.if (the_item.xtz_per_item != sp.tez(0)):
            # get the royalties for this item
            item_royalties = sp.view("get_royalties",
                self.data.minter,
                the_item.item_id,
                t = sp.TRecord(creator=sp.TAddress, royalties=sp.TNat)).open_some()
            
            fee = sp.utils.mutez_to_nat(sp.amount) * (item_royalties.royalties + self.data.fees) / sp.nat(1000)
            royalties = item_royalties.royalties * fee / (item_royalties.royalties + self.data.fees)

            # send royalties to creator
            sp.send(item_royalties.creator, sp.utils.nat_to_mutez(royalties))
            # send management fees
            sp.send(self.data.manager, sp.utils.nat_to_mutez(abs(fee - royalties)))
            # send rest of the value to seller
            sp.send(this_place.owner, sp.amount - sp.utils.nat_to_mutez(fee))
        
        # transfer item to buyer
        self.fa2_transfer(self.data.token, this_place.owner, sp.sender, the_item.item_id, 1)
        
        # reduce the item count in storage or remove it.
        sp.if the_item.item_amount > 1:
            the_item.item_amount = sp.as_nat(the_item.item_amount - 1)
        sp.else:
            del self.data.stored_items[sp.pair(params.lot_id, params.item_id)]

    #
    # Update code
    #
    @sp.entry_point
    def update_new_place(self, new_code):
        self.onlyManager()
        sp.set_entry_point("new_place", new_code)

    @sp.entry_point
    def update_place_item(self, new_code):
        self.onlyManager()
        sp.set_entry_point("place_item", new_code)

    @sp.entry_point
    def update_place_items(self, new_code):
        self.onlyManager()
        sp.set_entry_point("place_items", new_code)

    @sp.entry_point
    def update_remove_item(self, new_code):
        self.onlyManager()
        sp.set_entry_point("remove_item", new_code)

    @sp.entry_point
    def update_remove_items(self, new_code):
        self.onlyManager()
        sp.set_entry_point("remove_items", new_code)

    @sp.entry_point
    def update_get_item(self, new_code):
        self.onlyManager()
        sp.set_entry_point("get_item", new_code)

    #
    # Misc
    #
    def fa2_transfer(self, fa2, from_, to_, item_id, item_amount):
        c = sp.contract(sp.TList(sp.TRecord(from_=sp.TAddress, txs=sp.TList(sp.TRecord(amount=sp.TNat, to_=sp.TAddress, token_id=sp.TNat).layout(("to_", ("token_id", "amount")))))), fa2, entry_point='transfer').open_some()
        sp.transfer(sp.list([sp.record(from_=from_, txs=sp.list([sp.record(amount=item_amount, to_=to_, token_id=item_id)]))]), sp.mutez(0), c)


# A a compilation target (produces compiled code)
#sp.add_compilation_target("TL_Places", TL_Places(
#    sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV"), # Manager
#    sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV"), # Token
#    sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV")  # Minter
#    ))