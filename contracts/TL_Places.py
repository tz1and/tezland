# The (market)places contract.
#
# Each marketplace belongs to a place (an FA2 token that is the "land").
# Items (another type of token) can be stored on your (market)place, either to sell
# or just to build something nice.

import smartpy as sp

manager_contract = sp.io.import_script_from_url("file:contracts/Manageable.py")

itemRecordType = sp.TRecord(
    issuer=sp.TAddress, # Not obviously the owner of the lot, could have been sold/transfered after
    item_amount=sp.TNat, # number of objects to store.
    item_id=sp.TNat, # object id
    xtz_per_item=sp.TMutez, # 0 if not for sale.
    item_data=sp.TBytes # we store the transforms as half floats. 4 floats for quat, 1 float scale, 3 floats pos = 16 bytes
    # TODO: store an animation index?
    )

# TODO: reccords in variants are immutable?
# Create an issue in gitlab: is it a smartpy limitation?
extensibleVariantType = sp.TVariant(
    item = itemRecordType,
    ext = sp.TBytes
)

itemStoreMapType = sp.TMap(sp.TNat, extensibleVariantType)

itemStoreMapLiteral = sp.map(tkey=sp.TNat, tvalue=extensibleVariantType)

transferListItemType = sp.TRecord(amount=sp.TNat, to_=sp.TAddress, token_id=sp.TNat).layout(("to_", ("token_id", "amount")))

# TODO: make pausable?
class TL_Places(manager_contract.Manageable):
    def __init__(self, manager, items_contract, places_contract, minter):
        self.init_storage(
            manager = manager,
            items_contract = items_contract,
            places_contract = places_contract,
            minter = minter,
            # in local testing, I could get up to 2000-3000 items per map before things started to fail,
            # so there's plenty of room ahead.
            item_limit = sp.nat(64),
            fees = sp.nat(25),
            # basically only holds the per-marketplace counter.
            # TODO: I suppose it doesn't even need to be per-place
            places = sp.big_map(tkey=sp.TBytes, tvalue=sp.TRecord(
                counter=sp.TNat,
                interactionCounter=sp.TNat,
                # TODO: place ground color maybe?
                stored_items=itemStoreMapType
                ))
            )

    @sp.entry_point
    def set_fees(self, fees):
        sp.set_type(fees, sp.TNat)
        self.onlyManager()
        sp.verify(fees <= 60, message = "FEE_ERROR") # let's not get greedy
        self.data.fees = fees

    @sp.entry_point
    def set_item_limit(self, item_limit):
        sp.set_type(item_limit, sp.TNat)
        self.onlyManager()
        self.data.item_limit = item_limit

    def get_or_create_place(self, place_hash):
        # create new place if it doesn't exist
        sp.if self.data.places.contains(place_hash) == False:
            self.data.places[place_hash] = sp.record(
                counter = 0,
                interactionCounter = 0,
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

        # todo: test item limit!!!!
        sp.verify(sp.len(this_place.stored_items) + sp.len(params.item_list) <= self.data.item_limit, message = "ITEM_LIMIT")

        # make sure caller owns place
        sp.verify(self.fa2_get_balance(self.data.places_contract, params.lot_id, sp.sender) == 1, message = "NOT_OWNER")

        # our token transfer list
        # TODO: could also build up a map and convert it to a list with map.values()
        transferList = sp.local("transferList", sp.list([], t = transferListItemType))

        sp.for curr in params.item_list:
            sp.verify(sp.len(curr.item_data) == 16, message = "DATA_LEN")

            # transfer item to this contract
            # do multi-transfer by building up a list of transfers
            transferList.value.push(sp.record(amount=curr.token_amount, to_=sp.self_address, token_id=curr.token_id))

            this_place.stored_items[this_place.counter] = sp.variant("item", sp.record(
                issuer = sp.sender,
                item_amount = curr.token_amount,
                item_id = curr.token_id,
                xtz_per_item = curr.xtz_per_token,
                item_data = curr.item_data))

            this_place.counter += 1 # TODO: use sp.local for counter

        self.fa2_transfer_multi(self.data.items_contract, sp.sender, transferList.value)

    @sp.entry_point(lazify = True)
    def remove_items(self, params):
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.item_list, sp.TList(sp.TNat))

        # get the place
        place_hash = sp.local("place_hash", sp.sha3(sp.pack(params.lot_id)))
        this_place = self.data.places[place_hash.value]

        # make sure caller owns place
        sp.verify(self.fa2_get_balance(self.data.places_contract, params.lot_id, sp.sender) == 1, message = "NOT_OWNER")

        # our token transfer list
        # TODO: could also build up a map and convert it to a list with map.values()
        transferList = sp.local("transferList", sp.list([], t = transferListItemType))

        # remove the items
        sp.for curr in params.item_list:
            with this_place.stored_items[curr].match_cases() as arg:
                with arg.match("item") as the_item:
                    # transfer all remaining items back to issuer
                    # do multi-transfer by building up a list of transfers
                    transferList.value.push(sp.record(amount=the_item.item_amount, to_=the_item.issuer, token_id=the_item.item_id))
                # nothing to do here with ext items.
            
            del this_place.stored_items[curr]

        this_place.interactionCounter += 1

        self.fa2_transfer_multi(self.data.items_contract, sp.self_address, transferList.value)

    # TODO: allow getting multiple items? could make the code too complicated.
    @sp.entry_point(lazify = True)
    def get_item(self, params):
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.item_id, sp.TNat)

        # get the place
        place_hash = sp.local("place_hash", sp.sha3(sp.pack(params.lot_id)))
        this_place = self.data.places[place_hash.value]
        # get the item from storage. get_item is only supposed to work for the item variant.
        the_item = sp.local("the_item", this_place.stored_items[params.item_id].open_variant("item"))

        # make sure it's for sale, the transfered amount is correct, etc.
        sp.verify(the_item.value.xtz_per_item > sp.mutez(0), message = "NOT_FOR_SALE")
        sp.verify(the_item.value.xtz_per_item == sp.amount, message = "WRONG_AMOUNT")

        # send monies
        sp.if (the_item.value.xtz_per_item != sp.tez(0)):
            # get the royalties for this item
            item_royalties = sp.local("item_royalties", self.minter_get_royalties(the_item.value.item_id))
            
            fee = sp.local("fee", sp.utils.mutez_to_nat(sp.amount) * (item_royalties.value.royalties + self.data.fees) / sp.nat(1000))
            royalties = sp.local("royalties", item_royalties.value.royalties * fee.value / (item_royalties.value.royalties + self.data.fees))

            # send royalties to creator
            sp.send(item_royalties.value.creator, sp.utils.nat_to_mutez(royalties.value))
            # send management fees
            sp.send(self.data.manager, sp.utils.nat_to_mutez(abs(fee.value - royalties.value)))
            # send rest of the value to seller
            sp.send(the_item.value.issuer, sp.amount - sp.utils.nat_to_mutez(fee.value))
        
        # transfer item to buyer
        self.fa2_transfer(self.data.items_contract, sp.self_address, sp.sender, the_item.value.item_id, 1)
        
        # reduce the item count in storage or remove it.
        sp.if the_item.value.item_amount > 1:
            the_item.value.item_amount = sp.as_nat(the_item.value.item_amount - 1)
            this_place.stored_items[params.item_id] = sp.variant("item", the_item.value)
        sp.else:
            del this_place.stored_items[params.item_id]

        this_place.interactionCounter += 1

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
                this_place.interactionCounter,
                this_place.counter
            ))))

    @sp.onchain_view()
    def get_item_limit(self):
        sp.result(self.data.item_limit)

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
        # TODO: build transferlist and call fa2_transfer_multi
        c = sp.contract(sp.TList(sp.TRecord(from_=sp.TAddress, txs=sp.TList(transferListItemType))), fa2, entry_point='transfer').open_some()
        sp.transfer(sp.list([sp.record(from_=from_, txs=sp.list([sp.record(amount=item_amount, to_=to_, token_id=item_id)]))]), sp.mutez(0), c)

    def fa2_transfer_multi(self, fa2, from_, transfer_list):
        c = sp.contract(sp.TList(sp.TRecord(from_=sp.TAddress, txs=sp.TList(transferListItemType))), fa2, entry_point='transfer').open_some()
        sp.transfer(sp.list([sp.record(from_=from_, txs=transfer_list)]), sp.mutez(0), c)

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