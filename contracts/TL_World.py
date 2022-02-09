# The World contract.
#
# Each lot belongs to a Place (an FA2 token that is the "land").
# Items (another type of token) can be stored on your Place, either to swap
# or just to build something nice.

import smartpy as sp

pausable_contract = sp.io.import_script_from_url("file:contracts/Pausable.py")

# Urgent
# TODO: consider different world permissions? "full access" (can remvoe everything) vs "limited access" (can only removing items placed, no place props)
# TODO: place minting: don't make consecutive token ids. exterior places start at 0, while interior places might start at 1000000000
# TODO: has_permission: should it skip the initial owner check? Maybe not. Depends on the next.
# TODO: use has_permission instead of check_owner_or_permission?
# TODO: test set_item_data
#
#
# Other
# TODO: think of some more tests for permission.
# TODO: send_if_value makes some slightly ugly code, investigate use of locals
# TODO: check if packing/unpacking michelson maps works well for script variables
# TODO: turn transferMap into a metaclass?


# For tz1and Item tokens.
itemRecordType = sp.TRecord(
    issuer=sp.TAddress, # Not obviously the owner of the lot, could have been sold/transfered after
    item_amount=sp.TNat, # number of fa2 tokens to store.
    token_id=sp.TNat, # the fa2 token id
    xtz_per_item=sp.TMutez, # 0 if not for sale.
    item_data=sp.TBytes, # we store the transforms as half floats. 4 floats for quat, 1 float scale, 3 floats pos = 16 bytes
    # NOTE: could store an animation index and all kinds of other stuff in item_data
)

# For any other tokens someone might want to exhibit. These are "place only".
otherTokenRecordType = sp.TRecord(
    issuer=sp.TAddress, # Not obviously the owner of the lot, could have been sold/transfered after
    item_amount=sp.TNat, # number of fa2 tokens to store.
    token_id=sp.TNat, # the fa2 token id
    xtz_per_item=sp.TMutez, # 0 if not for sale.
    item_data=sp.TBytes, # we store the transforms as half floats. 4 floats for quat, 1 float scale, 3 floats pos = 16 bytes
    fa2=sp.TAddress # store a fa2 token address
)

# NOTE: reccords in variants are immutable?
# See: https://gitlab.com/SmartPy/smartpy/-/issues/32
extensibleVariantType = sp.TVariant(
    item = itemRecordType,
    other = otherTokenRecordType,
    ext = sp.TBytes
)

itemStoreMapType = sp.TMap(sp.TNat, extensibleVariantType)
itemStoreMapLiteral = sp.map(tkey=sp.TNat, tvalue=extensibleVariantType)

updateItemListType = sp.TRecord(
    item_id=sp.TNat,
    item_data=sp.TBytes
)

placeItemListType = sp.TVariant(
    item = sp.TRecord(
        token_id=sp.TNat,
        token_amount=sp.TNat,
        xtz_per_token=sp.TMutez,
        item_data=sp.TBytes
    ),
    other = sp.TRecord(
        token_id=sp.TNat,
        token_amount=sp.TNat,
        xtz_per_token=sp.TMutez,
        item_data=sp.TBytes,
        fa2=sp.TAddress
    ),
    ext = sp.TBytes
)

defaultPlaceProps = sp.bytes('0x82b881')

itemDataMinLen = sp.nat(16)
placeDataMinLen = sp.nat(3)

transferListItemType = sp.TRecord(amount=sp.TNat, to_=sp.TAddress, token_id=sp.TNat).layout(("to_", ("token_id", "amount")))

class Error_message:
    def __init__(self):
        #self.prefix = "WORLD_"
        self.prefix = ""
    def make(self, s): return (self.prefix + s)
    def no_permission(self):        return self.make("NO_PERMISSION")
    def not_owner(self):            return self.make("NOT_OWNER")
    def fee_error(self):            return self.make("FEE_ERROR")
    def parameter_error(self):      return self.make("PARAM_ERROR")
    def data_length(self):          return self.make("DATA_LEN")
    def item_limit(self):           return self.make("ITEM_LIMIT")
    def token_not_permitted(self):  return self.make("TOKEN_NOT_PERMITTED")
    def not_for_sale(self):         return self.make("NOT_FOR_SALE")
    def wrong_amount(self):         return self.make("WRONG_AMOUNT")
    def wrong_item_type(self):      return self.make("WRONG_ITEM_TYPE")

#
# Lazy set of permitted FA2 tokens for 'other' type.
class Permitted_fa2_set:
    def make(self):
        return sp.big_map(tkey = sp.TAddress, tvalue = sp.TBool)
    def add(self, set, fa2, allow_swap):
        set[fa2] = allow_swap
    def remove(self, set, fa2):
        del set[fa2]
    def is_permitted(self, set, fa2):
        return set.contains(fa2)
    def is_swap_permitted(self, set, fa2):
        return set[fa2]

#
# Operator_set from FA2. Lazy set for place permissions.
class Permission_set:
    def key_type(self):
        return sp.TRecord(owner = sp.TAddress,
                          permission = sp.TAddress,
                          token_id = sp.TNat
                          ).layout(("owner", ("permission", "token_id")))

    def make(self):
        return sp.big_map(tkey = self.key_type(), tvalue = sp.TUnit)

    def make_key(self, owner, permission, token_id):
        metakey = sp.record(owner = owner,
                            permission = permission,
                            token_id = token_id)
        metakey = sp.set_type_expr(metakey, self.key_type())
        return metakey

    def add(self, set, owner, permission, token_id):
        set[self.make_key(owner, permission, token_id)] = sp.unit
    def remove(self, set, owner, permission, token_id):
        del set[self.make_key(owner, permission, token_id)]
    def is_member(self, set, owner, permission, token_id):
        return set.contains(self.make_key(owner, permission, token_id))

#
# Operator_param from Fa2. Defines type types for the update_permissions entry-point.
class Permission_param:
    def get_type(self):
        t = sp.TRecord(
            owner = sp.TAddress,
            permission = sp.TAddress,
            token_id = sp.TNat)
        return t
    def make(self, owner, permission, token_id):
        r = sp.record(owner = owner,
            permission = permission,
            token_id = token_id)
        return sp.set_type_expr(r, self.get_type())

#
# The World contract.
# NOTE: should be pausable for code updates and because other item fa2 tokens are out of our control.
class TL_World(pausable_contract.Pausable):
    def __init__(self, manager, items_contract, places_contract, minter, dao_contract, terminus, metadata):
        self.error_message = Error_message()
        self.permission_set = Permission_set()
        self.permission_param = Permission_param()
        self.permitted_fa2_set = Permitted_fa2_set()
        self.init_storage(
            manager = manager,
            paused = False,
            items_contract = items_contract,
            places_contract = places_contract,
            minter = minter,
            dao_contract = dao_contract,
            metadata = metadata,
            # in local testing, I could get up to 2000-3000 items per map before things started to fail,
            # so there's plenty of room ahead.
            terminus = terminus,
            entered = sp.bool(False),
            item_limit = sp.nat(32),
            fees = sp.nat(25),
            other_permitted_fa2 = self.permitted_fa2_set.make(),
            permissions = self.permission_set.make(),
            places = sp.big_map(tkey=sp.TNat, tvalue=sp.TRecord(
                counter=sp.TNat,
                interaction_counter=sp.TNat,
                place_props=sp.TBytes, # ground color, maybe other stuff later.
                stored_items=itemStoreMapType
                ))
            )

    #
    # Manager-only entry points
    #
    @sp.entry_point
    def set_fees(self, fees):
        sp.set_type(fees, sp.TNat)
        self.onlyManager()
        sp.verify(fees <= 60, message = self.error_message.fee_error()) # let's not get greedy
        self.data.fees = fees

    @sp.entry_point
    def set_item_limit(self, item_limit):
        sp.set_type(item_limit, sp.TNat)
        self.onlyManager()
        self.data.item_limit = item_limit

    @sp.entry_point
    def set_other_fa2_permitted(self, params):
        """Call to add/remove fa2 contract from
        token contracts permitted for 'other' type items."""
        # NOTE: NEVER add Items or Places, lol. Not going to verify,
        # should probably be.
        sp.set_type(params.fa2, sp.TAddress)
        sp.set_type(params.permitted, sp.TBool)
        sp.set_type(params.swap_permitted, sp.TBool)
        self.onlyManager()
        sp.if params.permitted == True:
            self.permitted_fa2_set.add(self.data.other_permitted_fa2, params.fa2, params.swap_permitted)
        sp.else:
            self.permitted_fa2_set.remove(self.data.other_permitted_fa2, params.fa2)

    #
    # Public entry points
    #
    @sp.entry_point
    def update_permissions(self, params):
        sp.set_type(params, sp.TList(
            sp.TVariant(
                add_permission = self.permission_param.get_type(),
                remove_permission = self.permission_param.get_type()
            )
        ))

        #self.onlyUnpaused() # Probably fine to run when paused.

        sp.for update in params:
            with update.match_cases() as arg:
                with arg.match("add_permission") as upd:
                    # Sender must be the owner
                    sp.verify(upd.owner == sp.sender, message = self.error_message.not_owner())
                    # Add permission
                    self.permission_set.add(self.data.permissions,
                        upd.owner,
                        upd.permission,
                        upd.token_id)
                with arg.match("remove_permission") as upd:
                    # Sender must be the owner
                    sp.verify(upd.owner == sp.sender, message = self.error_message.not_owner())
                    # Remove permission
                    self.permission_set.remove(self.data.permissions,
                        upd.owner,
                        upd.permission,
                        upd.token_id)

    # Don't use private lambda because we need to be able to update code
    def get_or_create_place(self, lot_id):
        #sp.set_type(lot_id, sp.TNat)
        # create new place if it doesn't exist
        sp.if self.data.places.contains(lot_id) == False:
            self.data.places[lot_id] = sp.record(
                counter = 0,
                interaction_counter = 0,
                place_props = defaultPlaceProps, # only set color by default.
                stored_items=itemStoreMapLiteral
                )
        return self.data.places[lot_id]

    # Don't use private lambda because we need to be able to update code
    def check_owner_or_permission(self, lot_id, owner):
        #sp.set_type(lot_id, sp.TNat)
        #sp.set_type(owner, sp.TOption(sp.TAddress))
        # if caller is not the owner, he must have permission.
        sp.if self.fa2_get_balance(self.data.places_contract, lot_id, sp.sender) != 1:
            # if owner is set, verify purpoted owner actually owns the
            # place and sender has permission.
            sp.if owner.is_some():
                sp.verify(self.fa2_get_balance(self.data.places_contract, lot_id, owner.open_some()) == 1,
                    message = self.error_message.no_permission())
                sp.verify(self.permission_set.is_member(self.data.permissions,
                    owner.open_some(),
                    sp.sender,
                    lot_id) == True, message = self.error_message.no_permission())
            # otherwise, sender is just not the owner.
            sp.else:
                sp.failwith("NOT_OWNER")

    @sp.entry_point(lazify = True)
    def set_place_props(self, params):
        sp.set_type(params.props, sp.TBytes)
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.owner, sp.TOption(sp.TAddress))

        self.onlyUnpaused()

        # caller must be owner or or have permission of place.
        self.check_owner_or_permission(params.lot_id, params.owner)

        # get the place
        this_place = self.get_or_create_place(params.lot_id)

        # currently we only store the color. 3 bytes.
        sp.verify(sp.len(params.props) >= placeDataMinLen, message = self.error_message.data_length())

        this_place.place_props = params.props
        this_place.interaction_counter += 1

    @sp.entry_point(lazify = True)
    def place_items(self, params):
        sp.set_type(params.item_list, sp.TList(placeItemListType))
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.owner, sp.TOption(sp.TAddress))

        self.onlyUnpaused()

        # caller must be owner or have permission of place.
        self.check_owner_or_permission(params.lot_id, params.owner)

        # get the place
        this_place = self.get_or_create_place(params.lot_id)

        sp.verify(sp.len(this_place.stored_items) + sp.len(params.item_list) <= self.data.item_limit, message = self.error_message.item_limit())

        # our token transfer map
        transferMap = sp.local("transferMap", sp.map(tkey = sp.TNat, tvalue = transferListItemType))

        sp.for curr in params.item_list:
            with curr.match_cases() as arg:
                with arg.match("item") as item:
                    sp.verify(sp.len(item.item_data) >= itemDataMinLen, message = self.error_message.data_length())

                    # transfer item to this contract
                    # do multi-transfer by building up a list of transfers

                    sp.if transferMap.value.contains(item.token_id):
                        transferMap.value[item.token_id].amount += item.token_amount
                    sp.else:
                        transferMap.value[item.token_id] = sp.record(amount=item.token_amount, to_=sp.self_address, token_id=item.token_id)

                    this_place.stored_items[this_place.counter] = sp.variant("item", sp.record(
                        issuer = sp.sender,
                        item_amount = item.token_amount,
                        token_id = item.token_id,
                        xtz_per_item = item.xtz_per_token,
                        item_data = item.item_data))

                with arg.match("other") as other:
                    sp.verify(sp.len(other.item_data) >= itemDataMinLen, message = self.error_message.data_length())
                    sp.verify((other.token_amount == sp.nat(1)) & (other.xtz_per_token == sp.tez(0)), message = self.error_message.parameter_error())

                    sp.verify(self.permitted_fa2_set.is_permitted(self.data.other_permitted_fa2, other.fa2),
                        message = self.error_message.token_not_permitted())

                    # transfer external token to this contract. Only support 1 token per placement. no selling.
                    self.fa2_transfer(other.fa2, sp.sender, sp.self_address, other.token_id, 1)

                    this_place.stored_items[this_place.counter] = sp.variant("other", sp.record(
                        issuer = sp.sender,
                        item_amount = sp.nat(1),
                        token_id = other.token_id,
                        xtz_per_item = sp.tez(0),
                        item_data = other.item_data,
                        fa2 = other.fa2))

                with arg.match("ext") as ext_data:
                    #sp.verify(sp.len(ext_data) == 16, message = self.error_message.data_length())
                    this_place.stored_items[this_place.counter] = sp.variant("ext", ext_data)

            this_place.counter += 1

        # only transfer if list has items
        sp.if sp.len(transferMap.value) > 0:
            self.fa2_transfer_multi(self.data.items_contract, sp.sender, transferMap.value.values())

    @sp.entry_point(lazify = True)
    def set_item_data(self, params):
        sp.set_type(params.update_list, sp.TList(updateItemListType))
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.owner, sp.TOption(sp.TAddress))

        self.onlyUnpaused()

        # get the place - must exist
        this_place = self.data.places[params.lot_id]

        # caller must be owner or have permission of place.
        self.check_owner_or_permission(params.lot_id, params.owner)

        sp.for curr in params.update_list:
            with this_place.stored_items[curr.item_id].match_cases() as arg:
                with arg.match("item") as the_item:
                    # TODO: if data min also applied to ext, this wasn't required
                    sp.verify(sp.len(curr.item_data) >= itemDataMinLen, message = self.error_message.data_length())
                    # sigh - variants are not mutable
                    item_var = sp.compute(the_item)
                    item_var.item_data = curr.item_data
                    this_place.stored_items[curr.item_id] = sp.variant("item", item_var)
                with arg.match("other") as other:
                    # TODO: if data min also applied to ext, this wasn't required
                    sp.verify(sp.len(curr.item_data) >= itemDataMinLen, message = self.error_message.data_length())
                    # sigh - variants are not mutable
                    other_var = sp.compute(other)
                    other_var.item_data = curr.item_data
                    this_place.stored_items[curr.item_id] = sp.variant("other", other_var)
                with arg.match("ext") as ext:
                    this_place.stored_items[curr.item_id] = sp.variant("ext", curr.item_data)

        this_place.interaction_counter += 1

    @sp.entry_point(lazify = True)
    def remove_items(self, params):
        sp.set_type(params.item_list, sp.TList(sp.TNat))
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.owner, sp.TOption(sp.TAddress))

        self.onlyUnpaused()

        # get the place - must exist
        this_place = self.data.places[params.lot_id]

        # caller must be owner or have permission of place.
        self.check_owner_or_permission(params.lot_id, params.owner)
        
        # TODO: Make it so issuer can remove their items, even if no permission or owner?

        # our token transfer map
        transferMap = sp.local("transferMap", sp.map(tkey = sp.TNat, tvalue = transferListItemType))

        # remove the items
        sp.for curr in params.item_list:
            with this_place.stored_items[curr].match_cases() as arg:
                with arg.match("item") as the_item:
                    # transfer all remaining items back to issuer
                    # do multi-transfer by building up a list of transfers
                    sp.if transferMap.value.contains(the_item.token_id):
                        transferMap.value[the_item.token_id].amount += the_item.item_amount
                    sp.else:
                        transferMap.value[the_item.token_id] = sp.record(amount=the_item.item_amount, to_=the_item.issuer, token_id=the_item.token_id)

                with arg.match("other") as the_other:
                    # transfer external token back to the issuer. Only support 1 token.
                    self.fa2_transfer(the_other.fa2, sp.self_address, the_other.issuer, the_other.token_id, 1)

                # nothing to do here with ext items. Just remove them.
            
            del this_place.stored_items[curr]

        this_place.interaction_counter += 1

        # only transfer if list has items
        sp.if sp.len(transferMap.value) > 0:
            self.fa2_transfer_multi(self.data.items_contract, sp.self_address, transferMap.value.values())

    @sp.entry_point(lazify = True)
    def get_item(self, params):
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.item_id, sp.TNat)

        self.onlyUnpaused()

        # get the place
        this_place = self.data.places[params.lot_id]

        # get the item from storage. get_item is only supposed to work for the item variant.
        the_item = sp.local("the_item", this_place.stored_items[params.item_id].open_variant("item",
            message = self.error_message.wrong_item_type()))

        # make sure it's for sale, the transfered amount is correct, etc.
        sp.verify(the_item.value.xtz_per_item > sp.mutez(0), message = self.error_message.not_for_sale())
        sp.verify(the_item.value.xtz_per_item == sp.amount, message = self.error_message.wrong_amount())

        # send monies
        sp.if the_item.value.xtz_per_item != sp.tez(0):
            # get the royalties for this item
            item_royalties = sp.compute(self.minter_get_item_royalties(the_item.value.token_id))
            
            fee = sp.compute(sp.utils.mutez_to_nat(sp.amount) * (item_royalties.royalties + self.data.fees) / sp.nat(1000))
            royalties = sp.compute(item_royalties.royalties * fee / (item_royalties.royalties + self.data.fees))

            # send royalties to creator
            self.send_if_value(item_royalties.creator, sp.utils.nat_to_mutez(royalties))
            # send management fees
            self.send_if_value(self.data.manager, sp.utils.nat_to_mutez(abs(fee - royalties)))
            # send rest of the value to seller
            self.send_if_value(the_item.value.issuer, sp.amount - sp.utils.nat_to_mutez(fee))

            sp.if (sp.now < self.data.terminus):
                # Assuming 6 decimals, like tez.
                user_share = sp.compute(sp.utils.mutez_to_nat(sp.amount) / 2)
                # Only distribute dao if anything is to be distributed.
                sp.if user_share > 0:
                    manager_share = sp.utils.mutez_to_nat(sp.amount) * sp.nat(250) / sp.nat(1000)
                    self.dao_distribute([
                        sp.record(to_=sp.sender, amount=user_share),
                        sp.record(to_=the_item.value.issuer, amount=user_share),
                        sp.record(to_=self.data.manager, amount=manager_share)
                    ])
        
        # transfer item to buyer
        self.fa2_transfer(self.data.items_contract, sp.self_address, sp.sender, the_item.value.token_id, 1)
        
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
    @sp.onchain_view()
    def get_place_data(self, lot_id):
        sp.set_type(lot_id, sp.TNat)
        sp.if self.data.places.contains(lot_id) == False:
            sp.result(sp.record(
                stored_items = itemStoreMapLiteral,
                place_props = defaultPlaceProps))
        sp.else:
            sp.result(sp.record(
                stored_items = self.data.places[lot_id].stored_items,
                place_props = self.data.places[lot_id].place_props))

    @sp.onchain_view()
    def get_place_seqnum(self, lot_id):
        sp.set_type(lot_id, sp.TNat)
        sp.if self.data.places.contains(lot_id) == False:
            sp.result(sp.sha3(sp.pack(sp.pair(
                sp.nat(0),
                sp.nat(0)
            ))))
        sp.else:
            this_place = self.data.places[lot_id]
            sp.result(sp.sha3(sp.pack(sp.pair(
                this_place.interaction_counter,
                this_place.counter
            ))))

    @sp.onchain_view()
    def get_item_limit(self):
        sp.result(self.data.item_limit)

    @sp.onchain_view()
    def is_other_fa2_permitted(self, fa2):
        """Returns if an fa2 token is permitted for the
        'other' type."""
        sp.set_type(fa2, sp.TAddress)
        sp.result(self.permitted_fa2_set.is_permitted(self.data.other_permitted_fa2, fa2))

    @sp.onchain_view()
    def has_permission(self, query):
        sp.set_type(query,
            sp.TRecord(lot_id = sp.TNat,
                owner = sp.TAddress,
                permittee = sp.TAddress))
        
        # if permittee is the owner, he has permission.
        sp.if self.fa2_get_balance(self.data.places_contract, query.lot_id, query.permittee) > 0:
            sp.result(False)
        sp.else:
            # otherwise, make sure the purpoted owner is actually the owner and permissions are set.
            sp.if self.fa2_get_balance(self.data.places_contract, query.lot_id, query.owner) > 0:
                sp.result(self.permission_set.is_member(self.data.permissions,
                    query.owner,
                    query.permittee,
                    query.lot_id))
            sp.else:
                sp.result(False)

    #
    # Update code
    #
    @sp.entry_point
    def upgrade_code_set_place_props(self, new_code):
        self.onlyManager()
        sp.set_entry_point("set_place_props", new_code)

    @sp.entry_point
    def upgrade_code_place_items(self, new_code):
        self.onlyManager()
        sp.set_entry_point("place_items", new_code)

    @sp.entry_point
    def upgrade_code_set_item_data(self, new_code):
        self.onlyManager()
        sp.set_entry_point("set_item_data", new_code)

    @sp.entry_point
    def upgrade_code_remove_items(self, new_code):
        self.onlyManager()
        sp.set_entry_point("remove_items", new_code)

    @sp.entry_point
    def upgrade_code_get_item(self, new_code):
        self.onlyManager()
        sp.set_entry_point("get_item", new_code)

    #
    # Misc
    #
    def fa2_transfer(self, fa2, from_, to_, token_id, item_amount):
        self.fa2_transfer_multi(fa2, from_, sp.list([sp.record(amount=item_amount, to_=to_, token_id=token_id)]))

    def fa2_transfer_multi(self, fa2, from_, transfer_list):
        c = sp.contract(sp.TList(sp.TRecord(from_=sp.TAddress, txs=sp.TList(transferListItemType))), fa2, entry_point='transfer').open_some()
        sp.transfer(sp.list([sp.record(from_=from_, txs=transfer_list)]), sp.mutez(0), c)

    # Not used, World now has it's own operators set.
    #def fa2_is_operator(self, fa2, token_id, owner, operator):
    #    return sp.view("is_operator", fa2,
    #        sp.set_type_expr(
    #            sp.record(token_id = token_id, owner = owner, operator = operator),
    #            sp.TRecord(
    #                token_id = sp.TNat,
    #                owner = sp.TAddress,
    #                operator = sp.TAddress
    #            ).layout(("owner", ("operator", "token_id")))),
    #        t = sp.TBool).open_some()

    def fa2_get_balance(self, fa2, token_id, owner):
        return sp.view("get_balance", fa2,
            sp.set_type_expr(
                sp.record(owner = owner, token_id = token_id),
                sp.TRecord(
                    owner = sp.TAddress,
                    token_id = sp.TNat
                ).layout(("owner", "token_id"))),
            t = sp.TNat).open_some()

    def minter_get_item_royalties(self, token_id):
        return sp.view("get_item_royalties",
            self.data.minter,
            token_id,
            t = sp.TRecord(creator=sp.TAddress, royalties=sp.TNat)).open_some()

    def dao_distribute(self, recipients):
        recipientType = sp.TList(sp.TRecord(to_=sp.TAddress, amount=sp.TNat))
        #sp.set_type(recipients, recipientType)
        c = sp.contract(
            recipientType,
            self.data.dao_contract,
            entry_point='distribute').open_some()
        sp.transfer(recipients, sp.mutez(0), c)

    def send_if_value(self, to, amount):
        sp.if amount > sp.tez(0):
            sp.send(to, amount)


# A a compilation target (produces compiled code)
#sp.add_compilation_target("TL_World", TL_World(
#    sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV"), # Manager
#    sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV"), # Token
#    sp.address("tz1UQpm4CRWUTY9GBxmU8bWR8rxMHCu7jxjV")  # Minter
#    ))