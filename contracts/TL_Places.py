# The (market)places contract.
#
# Each marketplace belongs to a place (an FA2 token that is the "land").
# Items (another type of token) can be stored on your (market)place, either to sell
# or just to build something nice.

import smartpy as sp

manager_contract = sp.io.import_script_from_url("file:contracts/Manageable.py")

itemStoreMapType = sp.TMap(sp.TNat, sp.TRecord(
    issuer=sp.TAddress, # Not obviously the owner of the lot, could have been sold/transfered after
    item_amount=sp.TNat, # number of objects to store.
    item_id=sp.TNat, # object id
    xtz_per_item=sp.TMutez, # 0 if not for sale.
    item_data=sp.TBytes # we store the transforms as bytes. 4 floats for quat, 1 float scale, 3 floats pos = 32 bytes
    # TODO: store transform as half floats? could be worth it...
    ))

itemStoreMapLiteral = sp.map(tkey=sp.TNat, tvalue=sp.TRecord(
    issuer=sp.TAddress, # Not obviously the owner of the lot, could have been sold/transfered after
    item_amount=sp.TNat, # number of objects to store.
    item_id=sp.TNat, # object id
    xtz_per_item=sp.TMutez, # 0 if not for sale.
    item_data=sp.TBytes # we store the transforms as bytes. 4 floats for quat, 1 float scale, 3 floats pos = 32 bytes
    # TODO: store transform as half floats? could be worth it...
    ))

class TL_Places(manager_contract.Manageable):
    def __init__(self, manager, items_contract, places_contract, minter):
        self.init_storage(
            manager = manager,
            items_contract = items_contract,
            places_contract = places_contract,
            minter = minter,
            fees = sp.nat(25),
            # basically only holds the per-marketplace counter.
            # TODO: I suppose it doesn't even need to be per-place
            places = sp.big_map(tkey=sp.TBytes, tvalue=sp.TRecord(
                counter=sp.TNat,
                stored_items=itemStoreMapType
                ))
            )

    @sp.entry_point
    def set_fees(self, fees):
        sp.set_type(fees, sp.TNat)
        self.onlyManager()
        sp.verify(fees <= 60, message = "FEE_ERROR") # let's not get greedy
        self.data.fees = fees

    def get_or_create_place(self, place_hash):
        # create new place if it doesn't exist
        sp.if self.data.places.contains(place_hash) == False:
            self.data.places[place_hash] = sp.record(
                counter = 0,
                stored_items=itemStoreMapLiteral
                )
        return self.data.places[place_hash]

    @sp.entry_point(lazify = True)
    def place_items(self, params):
        sp.set_type(params.item_list, sp.TList(sp.TRecord(
            token_id=sp.TNat,
            token_amount=sp.TNat,
            xtz_per_token=sp.TMutez,
            item_data=sp.TBytes)))
        sp.set_type(params.lot_id, sp.TNat)

        # get the place
        place_hash = sp.local("place_hash", sp.sha3(sp.pack(params.lot_id)))
        this_place = self.get_or_create_place(place_hash.value)

        # todo: limit the number of stored items per lot. maybe... 64 initially?
        # in local testing, I could get up to 2000-3000 items per map before things started to fail,
        # so there's plenty of room ahead.

        # make sure caller owns place
        sp.verify(self.fa2_get_balance(self.data.places_contract, params.lot_id, sp.sender) == 1, message = "NOT_OWNER")

        sp.for curr in params.item_list:
            sp.verify(sp.len(curr.item_data) == 16, message = "DATA_LEN")

            # Make sure item is owned.
            sp.verify(self.fa2_get_balance(self.data.items_contract, curr.token_id, sp.sender) >= curr.token_amount,
                message = "ITEM_NOT_OWNED")

            this_place.stored_items[this_place.counter] = sp.record(
                issuer = sp.sender,
                item_amount = curr.token_amount,
                item_id = curr.token_id,
                xtz_per_item = curr.xtz_per_token,
                item_data = curr.item_data)

            this_place.counter += 1 # TODO: use sp.local for counter

    @sp.entry_point(lazify = True)
    def remove_items(self, params):
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.item_list, sp.TList(sp.TNat))

        # get the place
        place_hash = sp.local("place_hash", sp.sha3(sp.pack(params.lot_id)))
        this_place = self.data.places[place_hash.value]

        # make sure caller owns place
        sp.verify(self.fa2_get_balance(self.data.places_contract, params.lot_id, sp.sender) == 1, message = "NOT_OWNER")

        # remove the items
        sp.for curr in params.item_list:
            del this_place.stored_items[curr]

    @sp.entry_point(lazify = True)
    def get_item(self, params):
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.item_id, sp.TNat)

        # get the place
        place_hash = sp.local("place_hash", sp.sha3(sp.pack(params.lot_id)))
        this_place = self.data.places[place_hash.value]
        # get the item
        the_item = this_place.stored_items[params.item_id]

        # make sure it's for sale, the transfered amount is correct, etc.
        sp.verify(the_item.xtz_per_item > sp.mutez(0), message = "NOT_FOR_SALE")
        sp.verify(the_item.xtz_per_item == sp.amount, message = "WRONG_AMOUNT")

        # send monies
        sp.if (the_item.xtz_per_item != sp.tez(0)):
            # get the royalties for this item
            item_royalties = sp.local("item_royalties", self.minter_get_royalties(the_item.item_id))
            
            fee = sp.local("fee", sp.utils.mutez_to_nat(sp.amount) * (item_royalties.value.royalties + self.data.fees) / sp.nat(1000))
            royalties = sp.local("royalties", item_royalties.value.royalties * fee.value / (item_royalties.value.royalties + self.data.fees))

            # send royalties to creator
            sp.send(item_royalties.value.creator, sp.utils.nat_to_mutez(royalties.value))
            # send management fees
            sp.send(self.data.manager, sp.utils.nat_to_mutez(abs(fee.value - royalties.value)))
            # send rest of the value to seller
            sp.send(the_item.issuer, sp.amount - sp.utils.nat_to_mutez(fee.value))
        
        # transfer item to buyer
        self.fa2_transfer(self.data.items_contract, the_item.issuer, sp.sender, the_item.item_id, 1)
        
        # reduce the item count in storage or remove it.
        sp.if the_item.item_amount > 1:
            the_item.item_amount = sp.as_nat(the_item.item_amount - 1)
        sp.else:
            del this_place.stored_items[params.item_id]

    #
    # Views
    #
    @sp.onchain_view()
    def get_stored_items(self, lot_id):
        sp.set_type(lot_id, sp.TNat)
        place_hash = sp.local("place_hash", sp.sha3(sp.pack(lot_id)))
        sp.if self.data.places.contains(place_hash.value) == False:
            sp.result(itemStoreMapLiteral)
        sp.else:
            sp.result(self.data.places[place_hash.value].stored_items)

    @sp.onchain_view()
    def get_place_seqnum(self, lot_id):
        sp.set_type(lot_id, sp.TNat)
        place_hash = sp.local("place_hash", sp.sha3(sp.pack(lot_id)))
        sp.if self.data.places.contains(place_hash.value) == False:
            sp.result(sp.sha3(sp.pack(sp.pair(
                sp.nat(0),
                sp.nat(0)
            ))))
        sp.else:
            this_place = self.data.places[place_hash.value]
            sp.result(sp.sha3(sp.pack(sp.pair(
                sp.len(this_place.stored_items),
                this_place.counter
            ))))

    #
    # Update code
    #
    @sp.entry_point
    def update_place_items(self, new_code):
        self.onlyManager()
        sp.set_entry_point("place_items", new_code)

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

    def fa2_get_balance(self, fa2, token_id, owner):
        return sp.view("get_balance", fa2,
            sp.record(owner = owner, token_id = token_id),
            t = sp.TNat).open_some()

    def minter_get_royalties(self, item_id):
        return sp.view("get_royalties",
            self.data.minter,
            item_id,
            t = sp.TRecord(creator=sp.TAddress, royalties=sp.TNat)).open_some()


# A a compilation target (produces compiled code)
#sp.add_compilation_target("TL_Places", TL_Places(
#    sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV"), # Manager
#    sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV"), # Token
#    sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV")  # Minter
#    ))