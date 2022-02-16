# The World contract.
#
# Each lot belongs to a Place (an FA2 token that is the "land").
# Items (another type of token) can be stored on your Place, either to swap
# or just to build something nice.

import smartpy as sp

pausable_contract = sp.io.import_script_from_url("file:contracts/Pausable.py")
fees_contract = sp.io.import_script_from_url("file:contracts/Fees.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")

# Urgent
# TODO: Test place counter thoroughly!
# TODO: look into adding royalties into FA2
# TODO: place_items issuer override for "gifting" items by way of putting them in their place (if they have permission).
# TODO: think of some more tests for permission.
# TODO: start distribution of DAO token at a later date.
#
#
# Other
# TODO: sorting out the splitting of dao and team (probably with a proxy contract)
# TODO: proxy contract will also be some kind of multisig for all the only-admin things (pausing operation)
# TODO: research storage deserialisation limits
# TODO: check if packing/unpacking michelson maps works well for script variables
# TODO: turn transferMap into a metaclass?


# Some notes:
# - Place minting assumes consecutive ids, so place names will not match token_ids. Exteriors and interiors will count separately. I can live with that.
# - use abs instead sp.as_nat. as_nat can throw, abs doesn't.

# For tz1and Item tokens.
itemRecordType = sp.TRecord(
    item_amount=sp.TNat, # number of fa2 tokens to store.
    token_id=sp.TNat, # the fa2 token id
    xtz_per_item=sp.TMutez, # 0 if not for sale.
    item_data=sp.TBytes, # we store the transforms as half floats. 4 floats for quat, 1 float scale, 3 floats pos = 16 bytes
    # NOTE: could store an animation index and all kinds of other stuff in item_data
)

# For any other tokens someone might want to exhibit. These are "place only".
otherTokenRecordType = sp.TRecord(
    item_amount=sp.TNat, # number of fa2 tokens to store.
    token_id=sp.TNat, # the fa2 token id
    xtz_per_item=sp.TMutez, # 0 if not for sale.
    item_data=sp.TBytes, # we store the transforms as half floats. 4 floats for quat, 3 floats pos, 1 float scale = 16 bytes
    fa2=sp.TAddress # store a fa2 token address
)

# NOTE: reccords in variants are immutable?
# See: https://gitlab.com/SmartPy/smartpy/-/issues/32
# TODO: could have this be a record where item_data is common + variant with ext as Unit
extensibleVariantType = sp.TVariant(
    item = itemRecordType,
    other = otherTokenRecordType,
    ext = sp.TBytes
)

itemStoreMapType = sp.TMap(sp.TNat, extensibleVariantType)
itemStoreType = sp.TMap(sp.TAddress, itemStoreMapType)
itemStoreMapLiteral = sp.map(tkey=sp.TNat, tvalue=extensibleVariantType)
itemStoreLiteral = sp.map(tkey=sp.TAddress, tvalue=itemStoreMapType)

class Item_store_map:
    def make(self):
        return itemStoreLiteral
    def get(self, map, issuer):
        return map[issuer]
    def get_or_create(self, map, issuer):
        sp.if ~map.contains(issuer):
            map[issuer] = itemStoreMapLiteral
        return map[issuer]
        #items[counter] = place_item
    #def set_issuer_map(self, map, counter, issuer, place_item):
    #def remove(self, map, issuer, item_id):
    #    items = map.get(issuer, default_value = itemStoreMapLiteral)
    #    del items[item_id]

defaultPlaceProps = sp.bytes('0x82b881')

placeStorageType = sp.TRecord(
    next_id=sp.TNat,
    item_counter=sp.TNat,
    interaction_counter=sp.TNat,
    place_props=sp.TBytes,
    stored_items=itemStoreType
)

placeStorageDefault = sp.record(
    next_id = sp.nat(0),
    item_counter = sp.nat(0),
    interaction_counter = sp.nat(0),
    place_props = defaultPlaceProps, # only set color by default.
    stored_items=itemStoreLiteral
)

class Place_store_map:
    def make(self):
        return sp.big_map(tkey=sp.TNat, tvalue=placeStorageType)
    def get(self, map, lot_id):
        return map.get(lot_id)
    def get_or_create(self, map, lot_id):
        sp.if ~map.contains(lot_id):
            map[lot_id] = placeStorageDefault
        return map[lot_id]

updateItemListType = sp.TRecord(
    item_id=sp.TNat,
    item_data=sp.TBytes
)

placeItemListType = sp.TVariant(
    item = sp.TRecord(
        token_id=sp.TNat,
        token_amount=sp.TNat,
        mutez_per_token=sp.TMutez,
        item_data=sp.TBytes
    ),
    other = sp.TRecord(
        token_id=sp.TNat,
        token_amount=sp.TNat,
        mutez_per_token=sp.TMutez,
        item_data=sp.TBytes,
        fa2=sp.TAddress
    ),
    ext = sp.TBytes
)

itemDataMinLen = sp.nat(16)
placeDataMinLen = sp.nat(3)

# permissions are in octal, like unix.
# can be any combination of these.
# remove and modify own items in all places is always given. to prevent abuse.
permissionNone       = sp.nat(0) # no permissions
permissionPlaceItems = sp.nat(1) # can place items
permissionModifyAll  = sp.nat(2) # can edit and remove all items
permissionProps      = sp.nat(4) # can edit place props
permissionCanSell    = sp.nat(8) # can place items that are for sale. # TODO: not implemented.
permissionFull       = sp.nat(15) # has full permissions.

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
class Permitted_fa2_map:
    def make(self):
        return sp.big_map(tkey = sp.TAddress, tvalue = sp.TBool)
    def add(self, set, fa2, allow_swap):
        set[fa2] = allow_swap
    def remove(self, set, fa2):
        del set[fa2]
    def is_permitted(self, set, fa2):
        return set.contains(fa2)
    def is_swap_permitted(self, set, fa2):
        return set.get(fa2, default_value = False)

#
# Operator_set from FA2. Lazy set for place permissions.
class Permission_map:
    def key_type(self):
        return sp.TRecord(owner = sp.TAddress,
                          permittee = sp.TAddress,
                          token_id = sp.TNat
                          ).layout(("owner", ("permittee", "token_id")))

    def make(self):
        return sp.big_map(tkey = self.key_type(), tvalue = sp.TNat)

    def make_key(self, owner, permittee, token_id):
        metakey = sp.record(owner = owner,
                            permittee = permittee,
                            token_id = token_id)
        metakey = sp.set_type_expr(metakey, self.key_type())
        return metakey

    def add(self, set, owner, permittee, token_id, perm):
        set[self.make_key(owner, permittee, token_id)] = perm
    def remove(self, set, owner, permittee, token_id):
        del set[self.make_key(owner, permittee, token_id)]
    def is_member(self, set, owner, permittee, token_id):
        return set.contains(self.make_key(owner, permittee, token_id))
    def get_octal(self, set, owner, permittee, token_id):
        return set.get(self.make_key(owner, permittee, token_id), default_value = permissionNone)

#
# Operator_param from Fa2. Defines type types for the set_permissions entry-point.
class Permission_param:
    def get_add_type(self):
        t = sp.TRecord(
            owner = sp.TAddress,
            permittee = sp.TAddress,
            token_id = sp.TNat,
            perm = sp.TNat)
        return t
    def make_add(self, owner, permittee, token_id, perm):
        r = sp.record(owner = owner,
            permittee = permittee,
            token_id = token_id,
            perm = perm)
        return sp.set_type_expr(r, self.get_add_type())
    def get_remove_type(self):
        t = sp.TRecord(
            owner = sp.TAddress,
            permittee = sp.TAddress,
            token_id = sp.TNat)
        return t
    def make_remove(self, owner, permittee, token_id):
        r = sp.record(owner = owner,
            permittee = permittee,
            token_id = token_id)
        return sp.set_type_expr(r, self.get_remove_type())

#
# The World contract.
# NOTE: should be pausable for code updates and because other item fa2 tokens are out of our control.
class TL_World(pausable_contract.Pausable, fees_contract.Fees):
    def __init__(self, manager, items_contract, places_contract, minter, dao_contract, terminus, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")
        #self.add_flag("initial-cast")
        self.error_message = Error_message()
        self.permission_map = Permission_map()
        self.permission_param = Permission_param()
        self.permitted_fa2_map = Permitted_fa2_map()
        self.place_store_map = Place_store_map()
        self.item_store_map = Item_store_map()
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
            max_permission = permissionFull, # must be (power of 2)-1
            fees = sp.nat(25),
            fees_to = manager,
            other_permitted_fa2 = self.permitted_fa2_map.make(),
            permissions = self.permission_map.make(),
            places = self.place_store_map.make()
        )

    #
    # Manager-only entry points
    #
    @sp.entry_point
    def update_item_limit(self, item_limit):
        sp.set_type(item_limit, sp.TNat)
        self.onlyManager()
        self.data.item_limit = item_limit

    @sp.entry_point
    def update_max_permission(self, max_permission):
        sp.set_type(max_permission, sp.TNat)
        self.onlyManager()
        sp.verify(utils.isPowerOfTwoMinusOne(max_permission), message=self.error_message.parameter_error())
        self.data.max_permission = max_permission

    @sp.entry_point
    def set_other_fa2_permitted(self, params):
        # TODO: remwrite as list of variant!
        """Call to add/remove fa2 contract from
        token contracts permitted for 'other' type items."""
        # NOTE: NEVER add Items or Places, lol. Not going to verify,
        # should probably be.
        sp.set_type(params.fa2, sp.TAddress)
        sp.set_type(params.permitted, sp.TBool)
        sp.set_type(params.swap_permitted, sp.TBool)
        self.onlyManager()
        sp.if params.permitted == True:
            self.permitted_fa2_map.add(self.data.other_permitted_fa2, params.fa2, params.swap_permitted)
        sp.else:
            self.permitted_fa2_map.remove(self.data.other_permitted_fa2, params.fa2)

    #
    # Public entry points
    #
    @sp.entry_point
    def set_permissions(self, params):
        sp.set_type(params, sp.TList(
            sp.TVariant(
                add_permission = self.permission_param.get_add_type(),
                remove_permission = self.permission_param.get_remove_type()
            )
        ))

        #self.onlyUnpaused() # Probably fine to run when paused.

        sp.for update in params:
            with update.match_cases() as arg:
                with arg.match("add_permission") as upd:
                    # Sender must be the owner
                    sp.verify(upd.owner == sp.sender, message = self.error_message.not_owner())
                    sp.verify((upd.perm > permissionNone) & (upd.perm <= self.data.max_permission), message = self.error_message.parameter_error())
                    # Add permission
                    self.permission_map.add(self.data.permissions,
                        upd.owner,
                        upd.permittee,
                        upd.token_id,
                        upd.perm)
                with arg.match("remove_permission") as upd:
                    # Sender must be the owner
                    sp.verify(upd.owner == sp.sender, message = self.error_message.not_owner())
                    # Remove permission
                    self.permission_map.remove(self.data.permissions,
                        upd.owner,
                        upd.permittee,
                        upd.token_id)

    # Don't use private lambda because we need to be able to update code
    # Also, duplicating code is cheaper at runtime.
    def get_permissions_inline(self, lot_id, owner, permittee):
        permission = sp.local("permission", permissionNone)
        # if permittee is the owner, he has full permission.
        sp.if self.fa2_get_balance(self.data.places_contract, lot_id, permittee) > 0:
            permission.value = self.data.max_permission
        sp.else:
            # otherwise, make sure the purpoted owner is actually the owner and permissions are set.
            sp.if owner.is_some() & (self.fa2_get_balance(self.data.places_contract, lot_id, owner.open_some()) > 0):
                permission.value = sp.compute(self.permission_map.get_octal(self.data.permissions,
                    owner.open_some(),
                    permittee,
                    lot_id))
        return permission.value

    @sp.entry_point(lazify = True)
    def set_place_props(self, params):
        sp.set_type(params.props, sp.TBytes)
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.owner, sp.TOption(sp.TAddress))

        self.onlyUnpaused()

        # caller must be owner or or have full permissions.
        permissions = self.get_permissions_inline(params.lot_id, params.owner, sp.sender)
        sp.verify(permissions & permissionProps == permissionProps, message = self.error_message.no_permission())

        # get the place
        this_place = self.place_store_map.get_or_create(self.data.places, params.lot_id)

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

        # caller must be owner or have place item permissions.
        permissions = self.get_permissions_inline(params.lot_id, params.owner, sp.sender)
        sp.verify(permissions & permissionPlaceItems == permissionPlaceItems, message = self.error_message.no_permission())

        # get the place
        this_place = self.place_store_map.get_or_create(self.data.places, params.lot_id)

        item_store = self.item_store_map.get_or_create(this_place.stored_items, sp.sender)

        # make sure item limit is not exceeded.
        sp.verify(this_place.item_counter + sp.len(params.item_list) <= self.data.item_limit, message = self.error_message.item_limit())

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

                    item_store[this_place.next_id] = sp.variant("item", sp.record(
                        item_amount = item.token_amount,
                        token_id = item.token_id,
                        xtz_per_item = item.mutez_per_token,
                        item_data = item.item_data))

                with arg.match("other") as other:
                    sp.verify(sp.len(other.item_data) >= itemDataMinLen, message = self.error_message.data_length())
                    sp.verify((other.token_amount == sp.nat(1)) & (other.mutez_per_token == sp.tez(0)), message = self.error_message.parameter_error())

                    sp.verify(self.permitted_fa2_map.is_permitted(self.data.other_permitted_fa2, other.fa2),
                        message = self.error_message.token_not_permitted())

                    # transfer external token to this contract. Only support 1 token per placement. no selling.
                    self.fa2_transfer(other.fa2, sp.sender, sp.self_address, other.token_id, 1)

                    item_store[this_place.next_id] = sp.variant("other", sp.record(
                        item_amount = sp.nat(1),
                        token_id = other.token_id,
                        xtz_per_item = sp.tez(0),
                        item_data = other.item_data,
                        fa2 = other.fa2))

                with arg.match("ext") as ext_data:
                    #sp.verify(sp.len(ext_data) == 16, message = self.error_message.data_length())
                    item_store[this_place.next_id] = sp.variant("ext", ext_data)

            this_place.next_id += 1
            this_place.item_counter += 1

        # only transfer if list has items
        sp.if sp.len(transferMap.value) > 0:
            self.fa2_transfer_multi(self.data.items_contract, sp.sender, transferMap.value.values())

    @sp.entry_point(lazify = True)
    def set_item_data(self, params):
        sp.set_type(params.update_map, sp.TMap(sp.TAddress, sp.TList(updateItemListType)))
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.owner, sp.TOption(sp.TAddress))

        self.onlyUnpaused()

        # get the place - must exist
        this_place = self.place_store_map.get(self.data.places, params.lot_id)

        # caller must be owner or have ModifyAll or ModifyOwn permissions.
        permissions = self.get_permissions_inline(params.lot_id, params.owner, sp.sender)
        hasModifyAll = permissions & permissionModifyAll == permissionModifyAll

        # if ModifyAll permission is not given, make sure update map only contains sender items
        sp.if ~hasModifyAll:
            sp.for remove_key in params.update_map.keys():
                sp.verify(remove_key == sp.sender, message = self.error_message.no_permission())

        # update items
        sp.for issuer in params.update_map.keys():
            update_list = params.update_map[issuer]
            # get item store - must exist
            item_store = self.item_store_map.get(this_place.stored_items, issuer)
            
            sp.for update in update_list:
                with item_store[update.item_id].match_cases() as arg:
                    with arg.match("item") as the_item:
                        # TODO: if data min also applied to ext, this wasn't required
                        sp.verify(sp.len(update.item_data) >= itemDataMinLen, message = self.error_message.data_length())
                        # sigh - variants are not mutable
                        item_var = sp.compute(the_item)
                        item_var.item_data = update.item_data
                        item_store[update.item_id] = sp.variant("item", item_var)
                    with arg.match("other") as other:
                        # TODO: if data min also applied to ext, this wasn't required
                        sp.verify(sp.len(update.item_data) >= itemDataMinLen, message = self.error_message.data_length())
                        # sigh - variants are not mutable
                        other_var = sp.compute(other)
                        other_var.item_data = update.item_data
                        item_store[update.item_id] = sp.variant("other", other_var)
                    with arg.match("ext") as ext:
                        item_store[update.item_id] = sp.variant("ext", update.item_data)

        this_place.interaction_counter += 1

    @sp.entry_point(lazify = True)
    def remove_items(self, params):
        sp.set_type(params.remove_map, sp.TMap(sp.TAddress, sp.TList(sp.TNat)))
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.owner, sp.TOption(sp.TAddress))

        self.onlyUnpaused()

        # get the place - must exist
        this_place = self.place_store_map.get(self.data.places, params.lot_id)

        # caller must be owner or have ModifyAll or ModifyOwn permissions.
        permissions = self.get_permissions_inline(params.lot_id, params.owner, sp.sender)
        hasModifyAll = permissions & permissionModifyAll == permissionModifyAll

        # if ModifyAll permission is not given, make sure remove map only contains sender items.
        sp.if ~hasModifyAll:
            sp.for remove_key in params.remove_map.keys():
                sp.verify(remove_key == sp.sender, message = self.error_message.no_permission())

        # our token transfer map
        transferMap = sp.local("transferMap", sp.map(tkey = sp.TNat, tvalue = transferListItemType))

        # remove items
        sp.for issuer in params.remove_map.keys():
            item_list = params.remove_map[issuer]
            # get item store - must exist
            item_store = self.item_store_map.get(this_place.stored_items, issuer)
            
            sp.for curr in item_list:
                with item_store[curr].match_cases() as arg:
                    with arg.match("item") as the_item:
                        # transfer all remaining items back to issuer
                        # do multi-transfer by building up a list of transfers
                        sp.if transferMap.value.contains(the_item.token_id):
                            transferMap.value[the_item.token_id].amount += the_item.item_amount
                        sp.else:
                            transferMap.value[the_item.token_id] = sp.record(amount=the_item.item_amount, to_=issuer, token_id=the_item.token_id)

                    with arg.match("other") as the_other:
                        # transfer external token back to the issuer. Only support 1 token.
                        self.fa2_transfer(the_other.fa2, sp.self_address, issuer, the_other.token_id, 1)

                    # nothing to do here with ext items. Just remove them.
                
                del item_store[curr]
                this_place.item_counter = abs(this_place.item_counter - 1)

        this_place.interaction_counter += 1

        # only transfer if list has items
        sp.if sp.len(transferMap.value) > 0:
            self.fa2_transfer_multi(self.data.items_contract, sp.self_address, transferMap.value.values())

    @sp.entry_point(lazify = True)
    def get_item(self, params):
        sp.set_type(params.lot_id, sp.TNat)
        sp.set_type(params.item_id, sp.TNat)
        sp.set_type(params.issuer, sp.TAddress)

        self.onlyUnpaused()

        # get the place - must exist
        this_place = self.place_store_map.get(self.data.places, params.lot_id)

        # get item store - must exist
        item_store = self.item_store_map.get(this_place.stored_items, params.issuer)

        # get the item from storage. get_item is only supposed to work for the item variant.
        the_item = sp.local("the_item", item_store[params.item_id].open_variant("item",
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

            # TODO: don't localise nat_to_mutez, is probably a cast and free.
            # send royalties to creator
            send_royalties = sp.compute(sp.utils.nat_to_mutez(royalties))
            self.send_if_value(item_royalties.creator, send_royalties)
            # send management fees
            send_mgr_fees = sp.compute(sp.utils.nat_to_mutez(abs(fee - royalties)))
            self.send_if_value(self.data.manager, send_mgr_fees)
            # send rest of the value to seller
            send_issuer = sp.compute(sp.amount - sp.utils.nat_to_mutez(fee))
            self.send_if_value(params.issuer, send_issuer)

            sp.if (sp.now < self.data.terminus):
                # NOTE: Assuming 6 decimals, like tez.
                user_share = sp.compute(sp.utils.mutez_to_nat(sp.amount) / 2)
                # Only distribute dao if anything is to be distributed.
                sp.if user_share > 0:
                    manager_share = sp.utils.mutez_to_nat(sp.amount) * sp.nat(250) / sp.nat(1000)
                    self.dao_distribute([
                        sp.record(to_=sp.sender, amount=user_share),
                        sp.record(to_=params.issuer, amount=user_share),
                        sp.record(to_=self.data.manager, amount=manager_share)
                    ])
        
        # transfer item to buyer
        self.fa2_transfer(self.data.items_contract, sp.self_address, sp.sender, the_item.value.token_id, 1)
        
        # reduce the item count in storage or remove it.
        sp.if the_item.value.item_amount > 1:
            the_item.value.item_amount = abs(the_item.value.item_amount - 1)
            item_store[params.item_id] = sp.variant("item", the_item.value)
        sp.else:
            del item_store[params.item_id]
            this_place.item_counter = abs(this_place.item_counter - 1)

        this_place.interaction_counter += 1

    #
    # Views
    #
    @sp.onchain_view(pure=True)
    def get_place_data(self, lot_id):
        sp.set_type(lot_id, sp.TNat)
        sp.if self.data.places.contains(lot_id) == False:
            sp.result(sp.record(
                stored_items = itemStoreLiteral,
                place_props = defaultPlaceProps))
        sp.else:
            sp.result(sp.record(
                stored_items = self.data.places[lot_id].stored_items,
                place_props = self.data.places[lot_id].place_props))

    @sp.onchain_view(pure=True)
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
                this_place.next_id
            ))))

    @sp.onchain_view(pure=True)
    def get_item_limit(self):
        sp.result(self.data.item_limit)

    @sp.onchain_view(pure=True)
    def is_other_fa2_permitted(self, fa2):
        """Returns if an fa2 token is permitted for the
        'other' type."""
        sp.set_type(fa2, sp.TAddress)
        sp.result(sp.record(
            permitted = self.permitted_fa2_map.is_permitted(self.data.other_permitted_fa2, fa2),
            swap_permitted = self.permitted_fa2_map.is_swap_permitted(self.data.other_permitted_fa2, fa2)
        ))

    @sp.onchain_view(pure=True)
    def get_permissions(self, query):
        sp.set_type(query,
            sp.TRecord(lot_id = sp.TNat,
                owner = sp.TOption(sp.TAddress),
                permittee = sp.TAddress))
        sp.result(self.get_permissions_inline(query.lot_id, query.owner, query.permittee))

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