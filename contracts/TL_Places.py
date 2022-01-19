# The (market)places contract.
#
# Each marketplace belongs to a place (an FA2 token that is the "land").
# Items (another type of token) can be stored on your (market)place, either to sell
# or just to build something nice.

from ast import operator
import smartpy as sp

manager_contract = sp.io.import_script_from_url("file:contracts/Manageable.py")

# TODO: distinction between manager and admin?
# TODO: put error messages into functions?
# TODO: test operator stuff!
# TODO: don't use place hash?

itemRecordType = sp.TRecord(
    issuer=sp.TAddress, # Not obviously the owner of the lot, could have been sold/transfered after
    item_amount=sp.TNat, # number of objects to store.
    item_id=sp.TNat, # object id
    xtz_per_item=sp.TMutez, # 0 if not for sale.
    item_data=sp.TBytes # we store the transforms as half floats. 4 floats for quat, 1 float scale, 3 floats pos = 16 bytes
    # TODO: store an animation index in data?
)

# TODO: reccords in variants are immutable?
# Create an issue in gitlab: is it a smartpy limitation?
extensibleVariantType = sp.TVariant(
    item = itemRecordType,
    ext = sp.TBytes
)

itemStoreMapType = sp.TMap(sp.TNat, extensibleVariantType)
itemStoreMapLiteral = sp.map(tkey=sp.TNat, tvalue=extensibleVariantType)

placeItemType = sp.TVariant(
    item = sp.TRecord(
        token_id=sp.TNat,
        token_amount=sp.TNat,
        xtz_per_token=sp.TMutez,
        item_data=sp.TBytes
    ),
    ext = sp.TBytes
)

defaultPlaceProps = sp.bytes('0x82b881')

transferListItemType = sp.TRecord(amount=sp.TNat, to_=sp.TAddress, token_id=sp.TNat).layout(("to_", ("token_id", "amount")))

# TODO: make pausable?
class TL_Places(manager_contract.Manageable):
    def __init__(self, manager, items_contract, places_contract, minter, metadata):
        self.init_storage(
            manager = manager,
            items_contract = items_contract,
            places_contract = places_contract,
            minter = minter,
            metadata = metadata,
            # in local testing, I could get up to 2000-3000 items per map before things started to fail,
            # so there's plenty of room ahead.
            item_limit = sp.nat(64),
            fees = sp.nat(25),
            places = sp.big_map(tkey=sp.TBytes, tvalue=sp.TRecord(
                counter=sp.TNat,
                interaction_counter=sp.TNat,
                place_props=sp.TBytes, # ground color, maybe other stuff later.
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

    # Don't use private lambda because we need to be able to update code
    def get_or_create_place(self, lot_id):
        sp.set_type(lot_id, sp.TNat)

        place_hash = sp.compute(sp.sha3(sp.pack(lot_id)))
        # create new place if it doesn't exist
        sp.if self.data.places.contains(place_hash) == False:
            self.data.places[place_hash] = sp.record(
                counter = 0,
                interaction_counter = 0,
                place_props = defaultPlaceProps, # only set color by default.
                stored_items=itemStoreMapLiteral
                )
        return self.data.places[place_hash]

    # Don't use private lambda because we need to be able to update code
    def get_place(self, lot_id):
        sp.set_type(lot_id, sp.TNat)

        # still want to use a local here because this returns an expression
        # that maybe be computed over and over
        place_hash = sp.compute(sp.sha3(sp.pack(lot_id)))
        return self.data.places[place_hash]

    # Don't use private lambda because we need to be able to update code
    def check_owner_or_operator(self, lot_id, owner):
        sp.set_type(lot_id, sp.TNat)
        sp.set_type(owner, sp.TOption(sp.TAddress))
        
        # caller must be owner or operator of place.
        sp.if self.fa2_get_balance(self.data.places_contract, lot_id, sp.sender) != 1:
            sp.verify(self.fa2_is_operator(
                self.data.places_contract, lot_id,
                owner.open_some(message = "PARAM_ERROR"),
                sp.sender) == True, message = "NOT_OPERATOR")

    @sp.entry_point(lazify = True)
    def set_place_props(self, params):
        sp.set_type(params.props, sp.TBytes)
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.owner, sp.TOption(sp.TAddress))

        # caller must be owner or operator of place.
        self.check_owner_or_operator(params.lot_id, params.owner)

        # get the place
        this_place = self.get_or_create_place(params.lot_id)

        # currently we only store the color. 3 bytes.
        sp.verify(sp.len(params.props) == 3, message = "DATA_LEN")

        this_place.place_props = params.props
        this_place.interaction_counter += 1

    @sp.entry_point(lazify = True)
    def place_items(self, params):
        sp.set_type(params.item_list, sp.TList(placeItemType))
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.owner, sp.TOption(sp.TAddress))

        # caller must be owner or operator of place.
        self.check_owner_or_operator(params.lot_id, params.owner)

        # get the place
        this_place = self.get_or_create_place(params.lot_id)

        sp.verify(sp.len(this_place.stored_items) + sp.len(params.item_list) <= self.data.item_limit, message = "ITEM_LIMIT")

        # our token transfer map
        transferMap = sp.local("transferMap", sp.map(tkey = sp.TNat, tvalue = transferListItemType))

        sp.for curr in params.item_list:
            with curr.match_cases() as arg:
                with arg.match("item") as item:
                    sp.verify(sp.len(item.item_data) == 16, message = "DATA_LEN")

                    # transfer item to this contract
                    # do multi-transfer by building up a list of transfers

                    sp.if transferMap.value.contains(item.token_id):
                        transferMap.value[item.token_id].amount += item.token_amount
                    sp.else:
                        transferMap.value[item.token_id] = sp.record(amount=item.token_amount, to_=sp.self_address, token_id=item.token_id)

                    this_place.stored_items[this_place.counter] = sp.variant("item", sp.record(
                        issuer = sp.sender,
                        item_amount = item.token_amount,
                        item_id = item.token_id,
                        xtz_per_item = item.xtz_per_token,
                        item_data = item.item_data))

                with arg.match("ext") as ext_data:
                    # TDOD: limit data len?
                    #sp.verify(sp.len(ext_data) == 16, message = "DATA_LEN")
                    this_place.stored_items[this_place.counter] = sp.variant("ext", ext_data)

            this_place.counter += 1

        # only transfer if list has items
        sp.if sp.len(transferMap.value) > 0:
            self.fa2_transfer_multi(self.data.items_contract, sp.sender, transferMap.value.values())

    @sp.entry_point(lazify = True)
    def remove_items(self, params):
        sp.set_type(params.item_list, sp.TList(sp.TNat))
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.owner, sp.TOption(sp.TAddress))

        # get the place
        this_place = self.get_place(params.lot_id)

        # caller must be owner or operator of place.
        self.check_owner_or_operator(params.lot_id, params.owner)
        
        # TODO: Best make it so issuer can remove their items, even if not operator or owner.

        # our token transfer map
        transferMap = sp.local("transferMap", sp.map(tkey = sp.TNat, tvalue = transferListItemType))

        # remove the items
        sp.for curr in params.item_list:
            with this_place.stored_items[curr].match_cases() as arg:
                with arg.match("item") as the_item:
                    # transfer all remaining items back to issuer
                    # do multi-transfer by building up a list of transfers
                    sp.if transferMap.value.contains(the_item.item_id):
                        transferMap.value[the_item.item_id].amount += the_item.item_amount
                    sp.else:
                        transferMap.value[the_item.item_id] = sp.record(amount=the_item.item_amount, to_=the_item.issuer, token_id=the_item.item_id)
                # nothing to do here with ext items.
            
            del this_place.stored_items[curr]

        this_place.interaction_counter += 1

        # only transfer if list has items
        sp.if sp.len(transferMap.value) > 0:
            self.fa2_transfer_multi(self.data.items_contract, sp.self_address, transferMap.value.values())

    # TODO: allow getting multiple items? could make the code too complicated.
    @sp.entry_point(lazify = True)
    def get_item(self, params):
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.item_id, sp.TNat)

        # get the place
        this_place = self.get_place(params.lot_id)

        # get the item from storage. get_item is only supposed to work for the item variant.
        the_item = sp.local("the_item", this_place.stored_items[params.item_id].open_variant("item"))

        # make sure it's for sale, the transfered amount is correct, etc.
        sp.verify(the_item.value.xtz_per_item > sp.mutez(0), message = "NOT_FOR_SALE")
        sp.verify(the_item.value.xtz_per_item == sp.amount, message = "WRONG_AMOUNT")

        # send monies
        sp.if (the_item.value.xtz_per_item != sp.tez(0)):
            # get the royalties for this item
            item_royalties = sp.compute(self.minter_get_royalties(the_item.value.item_id))
            
            fee = sp.compute(sp.utils.mutez_to_nat(sp.amount) * (item_royalties.royalties + self.data.fees) / sp.nat(1000))
            royalties = sp.compute(item_royalties.royalties * fee / (item_royalties.royalties + self.data.fees))

            # send royalties to creator
            sp.send(item_royalties.creator, sp.utils.nat_to_mutez(royalties))
            # send management fees
            sp.send(self.data.manager, sp.utils.nat_to_mutez(abs(fee - royalties)))
            # send rest of the value to seller
            sp.send(the_item.value.issuer, sp.amount - sp.utils.nat_to_mutez(fee))
        
        # transfer item to buyer
        self.fa2_transfer(self.data.items_contract, sp.self_address, sp.sender, the_item.value.item_id, 1)
        
        # reduce the item count in storage or remove it.
        sp.if the_item.value.item_amount > 1:
            the_item.value.item_amount = sp.as_nat(the_item.value.item_amount - 1)
            this_place.stored_items[params.item_id] = sp.variant("item", the_item.value)
        sp.else:
            del this_place.stored_items[params.item_id]

        this_place.interaction_counter += 1

    #
    # Views
    #
    # TODO: rename to get_place_data?
    @sp.onchain_view()
    def get_stored_items(self, lot_id):
        sp.set_type(lot_id, sp.TNat)
        place_hash = sp.compute(sp.sha3(sp.pack(lot_id)))
        sp.if self.data.places.contains(place_hash) == False:
            sp.result(sp.record(
                stored_items = itemStoreMapLiteral,
                place_props = defaultPlaceProps))
        sp.else:
            sp.result(sp.record(
                stored_items = self.data.places[place_hash].stored_items,
                place_props = self.data.places[place_hash].place_props))

    @sp.onchain_view()
    def get_place_seqnum(self, lot_id):
        sp.set_type(lot_id, sp.TNat)
        place_hash = sp.compute(sp.sha3(sp.pack(lot_id)))
        sp.if self.data.places.contains(place_hash) == False:
            sp.result(sp.sha3(sp.pack(sp.pair(
                sp.nat(0),
                sp.nat(0)
            ))))
        sp.else:
            this_place = self.data.places[place_hash]
            sp.result(sp.sha3(sp.pack(sp.pair(
                this_place.interaction_counter,
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
        self.fa2_transfer_multi(fa2, from_, sp.list([sp.record(amount=item_amount, to_=to_, token_id=item_id)]))

    def fa2_transfer_multi(self, fa2, from_, transfer_list):
        c = sp.contract(sp.TList(sp.TRecord(from_=sp.TAddress, txs=sp.TList(transferListItemType))), fa2, entry_point='transfer').open_some()
        sp.transfer(sp.list([sp.record(from_=from_, txs=transfer_list)]), sp.mutez(0), c)

    def fa2_is_operator(self, fa2, token_id, owner, operator):
        return sp.view("is_operator", fa2,
            sp.set_type_expr(
                sp.record(token_id = token_id, owner = owner, operator = operator),
                sp.TRecord(
                    token_id = sp.TNat,
                    owner = sp.TAddress,
                    operator = sp.TAddress
                ).layout(("owner", ("operator", "token_id")))),
            t = sp.TBool).open_some()

    def fa2_get_balance(self, fa2, token_id, owner):
        return sp.view("get_balance", fa2,
            sp.set_type_expr(
                sp.record(owner = owner, token_id = token_id),
                sp.TRecord(
                    owner = sp.TAddress,
                    token_id = sp.TNat
                ).layout(("owner", "token_id"))),
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