# The World contract.
#
# Each lot belongs to a Place (an FA2 token that is the "land").
# Items (another type of token) can be stored on your Place, either to swap
# or just to build something nice.

import smartpy as sp

pause_mixin = sp.io.import_script_from_url("file:contracts/Pausable.py")
fees_mixin = sp.io.import_script_from_url("file:contracts/Fees.py")
mod_mixin = sp.io.import_script_from_url("file:contracts/Moderation.py")
permitted_fa2 = sp.io.import_script_from_url("file:contracts/PermittedFA2.py")
upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")

# Urgent
# TODO: make max contributors variable in royalties?
# TODO: test issuer map removal.
# TODO: think of some more tests for permission.
# TODO: place permissions: increase seq num (interaction counter)?
# TODO: use metadata builder for all other contracts.
#
#
# Other
# TODO: DAO token drop with merkle tree based on: https://github.com/AnshuJalan/token-drop-template
# TODO: Does the places token even need to be administrated by minter?
# TODO: generalised minter: map of token contracts with props: admin_only, allow_mint_multiple
# TODO: sorting out the splitting of dao and team (probably with a proxy contract)
# TODO: proxy contract will also be some kind of multisig for all the only-admin things (pausing operation)
# TODO: research storage deserialisation limits
# TODO: investgate using a "metadata map" for item data.
# TODO: check if packing/unpacking michelson maps works well for script variables
# TODO: turn transferMap into a metaclass?
#
#
# V2
# TODO: should I do chunking? I could make room for it right now by hashing pair (place, chunk) and storing chunks in separate bigmap.
#  + chunk limit. get_place_data takes list of chunks to query. have per-chunk seq-num. and a global one.
# TODO: place_items issuer override for "gifting" items by way of putting them in their place (if they have permission).


# Some notes:
# - Place minting assumes consecutive ids, so place names will not match token_ids. Exteriors and interiors will count separately. I can live with that.
# - use abs instead sp.as_nat. as_nat can throw, abs doesn't.
# - DON'T add Items or Places, to permitted_fa2.
# - every upgradeable_mixin entrypoint has an arg of extensionArgType. Can be used for merkle proof royalties, for example.
# - Item data is stored in half floats, usually, there are two formats as of now
#   + 0: 1 byte format, 3 floats pos = 7 bytes (this is also the minimum item data length)
#   + 1: 1 byte format, 3 floats for euler angles, 3 floats pos, 1 float scale = 15 bytes
#   NOTE: could store an animation index and all kinds of other stuff in item_data
# - Regarding place item storage efficiency: you can easily have up to 2000-3000 items per map before gas becomes *expensive*.

# Optional extension argument type.
# Map val can contain about anything and be
# unpacked with sp.unpack.
extensionArgType = sp.TOption(sp.TMap(sp.TString, sp.TBytes))

#
# Item types
# For tz1and Item tokens.
itemRecordType = sp.TRecord(
    item_amount=sp.TNat, # number of fa2 tokens to store.
    token_id=sp.TNat, # the fa2 token id
    mutez_per_item=sp.TMutez, # 0 if not for sale.
    item_data=sp.TBytes, # transforms, etc
).layout(("item_amount", ("token_id", ("mutez_per_item", "item_data"))))

# For any other tokens someone might want to exhibit. These are "place only".
otherTokenRecordType = sp.TRecord(
    item_amount=sp.TNat, # number of fa2 tokens to store.
    token_id=sp.TNat, # the fa2 token id
    mutez_per_item=sp.TMutez, # 0 if not for sale.
    item_data=sp.TBytes, # transforms, etc
    fa2=sp.TAddress # store a fa2 token address
).layout(("item_amount", ("token_id", ("mutez_per_item", ("item_data", "fa2")))))

# NOTE: reccords in variants are immutable?
# See: https://gitlab.com/SmartPy/smartpy/-/issues/32
extensibleVariantType = sp.TVariant(
    item = itemRecordType,
    other = otherTokenRecordType,
    ext = sp.TBytes # transforms, etc
).layout(("item", ("other", "ext")))

#
# Item storage
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
        with sp.if_(~map.contains(issuer)):
            map[issuer] = itemStoreMapLiteral
        return map[issuer]
    def remove_if_empty(self, map, issuer):
        with sp.if_(map.contains(issuer) & (sp.len(map[issuer]) == 0)):
            del map[issuer]

#
# Place storage
placePropsType = sp.TMap(sp.TBytes, sp.TBytes)
# only set color by default.
defaultPlaceProps = sp.map({sp.bytes("0x00"): sp.bytes('0x82b881')}, tkey=sp.TBytes, tvalue=sp.TBytes)

placeStorageType = sp.TRecord(
    next_id=sp.TNat,
    interaction_counter=sp.TNat,
    place_props=placePropsType,
    stored_items=itemStoreType
).layout(("next_id", ("interaction_counter", ("place_props", "stored_items"))))

placeStorageDefault = sp.record(
    next_id = sp.nat(0),
    interaction_counter = sp.nat(0),
    place_props = defaultPlaceProps,
    stored_items=itemStoreLiteral
)

class Place_store_map:
    def make(self):
        return sp.big_map(tkey=sp.TNat, tvalue=placeStorageType)
    def get(self, map, lot_id):
        return map.get(lot_id)
    def get_or_create(self, map, lot_id):
        with sp.if_(~map.contains(lot_id)):
            map[lot_id] = placeStorageDefault
        return map[lot_id]

updateItemListType = sp.TRecord(
    item_id=sp.TNat,
    item_data=sp.TBytes
).layout(("item_id", "item_data"))

placeItemListType = sp.TVariant(
    item = sp.TRecord(
        token_id=sp.TNat,
        token_amount=sp.TNat,
        mutez_per_token=sp.TMutez,
        item_data=sp.TBytes
    ).layout(("token_id", ("token_amount", ("mutez_per_token", "item_data")))),
    other = sp.TRecord(
        token_id=sp.TNat,
        token_amount=sp.TNat,
        mutez_per_token=sp.TMutez,
        item_data=sp.TBytes,
        fa2=sp.TAddress
    ).layout(("token_id", ("token_amount", ("mutez_per_token", ("item_data", "fa2"))))),
    ext = sp.TBytes
).layout(("item", ("other", "ext")))

itemDataMinLen = sp.nat(7) # format 0 is 7 bytes
placePropsColorLen = sp.nat(3) # 3 bytes for color

# permissions are in octal, like unix.
# can be any combination of these.
# remove and modify own items in all places is always given. to prevent abuse.
permissionNone       = sp.nat(0) # no permissions
permissionPlaceItems = sp.nat(1) # can place items
permissionModifyAll  = sp.nat(2) # can edit and remove all items
permissionProps      = sp.nat(4) # can edit place props
permissionCanSell    = sp.nat(8) # can place items that are for sale. # TODO: not implemented.
permissionFull       = sp.nat(15) # has full permissions.

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
    def not_for_sale(self):         return self.make("NOT_FOR_SALE")
    def wrong_amount(self):         return self.make("WRONG_AMOUNT")
    def wrong_item_type(self):      return self.make("WRONG_ITEM_TYPE")

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
            perm = sp.TNat).layout(("owner", ("permittee", ("token_id", "perm"))))
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
            token_id = sp.TNat).layout(("owner", ("permittee", "token_id")))
        return t
    def make_remove(self, owner, permittee, token_id):
        r = sp.record(owner = owner,
            permittee = permittee,
            token_id = token_id)
        return sp.set_type_expr(r, self.get_remove_type())

#
# The World contract.
# NOTE: should be pausable for code updates and because other item fa2 tokens are out of our control.
class TL_World(
    pause_mixin.Pausable,
    fees_mixin.Fees,
    mod_mixin.Moderation,
    permitted_fa2.PermittedFA2,
    upgradeable_mixin.Upgradeable,
    sp.Contract):
    def __init__(self, administrator, items_contract, places_contract, dao_contract, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")
        # Not a win at all in terms of gas, especially on the simpler eps.
        #self.add_flag("lazy-entry-points")
        # No noticeable effect on gas.
        #self.add_flag("initial-cast")
        # Makes much smaller code but removes annots from eps.
        #self.add_flag("simplify-via-michel")
        
        self.error_message = Error_message()
        self.permission_map = Permission_map()
        self.permission_param = Permission_param()
        self.place_store_map = Place_store_map()
        self.item_store_map = Item_store_map()
        self.init_storage(
            items_contract = items_contract,
            places_contract = places_contract,
            dao_contract = dao_contract,
            metadata = metadata,
            item_limit = sp.nat(64),
            max_permission = permissionFull, # must be (power of 2)-1
            permissions = self.permission_map.make(),
            places = self.place_store_map.make()
        )
        pause_mixin.Pausable.__init__(self, administrator = administrator)
        fees_mixin.Fees.__init__(self, administrator = administrator)
        mod_mixin.Moderation.__init__(self, administrator = administrator)
        permitted_fa2.PermittedFA2.__init__(self, administrator = administrator)
        upgradeable_mixin.Upgradeable.__init__(self, administrator = administrator,
            entrypoints = ['set_place_props', 'place_items', 'set_item_data', 'remove_items', 'get_item'])

    #
    # Manager-only entry points
    #
    @sp.entry_point
    def update_item_limit(self, item_limit):
        sp.set_type(item_limit, sp.TNat)
        self.onlyAdministrator()
        self.data.item_limit = item_limit


    @sp.entry_point
    def update_max_permission(self, max_permission):
        sp.set_type(max_permission, sp.TNat)
        self.onlyAdministrator()
        sp.verify(utils.isPowerOfTwoMinusOne(max_permission), message=self.error_message.parameter_error())
        self.data.max_permission = max_permission


    #
    # Public entry points
    #
    @sp.entry_point
    def set_permissions(self, params):
        sp.set_type(params, sp.TList(sp.TVariant(
            add_permission = self.permission_param.get_add_type(),
            remove_permission = self.permission_param.get_remove_type()
        ).layout(("add_permission", "remove_permission"))))

        #self.onlyUnpaused() # Probably fine to run when paused.

        with sp.for_("update", params) as update:
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
    def getPermissionsInline(self, lot_id, owner, permittee):
        lot_id = sp.set_type_expr(lot_id, sp.TNat)
        owner = sp.set_type_expr(owner, sp.TOption(sp.TAddress))
        permittee = sp.set_type_expr(permittee, sp.TAddress)

        # Local var for permissions.
        permission = sp.local("permission", permissionNone)

        # If permittee is the owner, he has full permission.
        with sp.if_(utils.fa2_get_balance(self.data.places_contract, lot_id, permittee) > 0):
            permission.value = self.data.max_permission
        with sp.else_():
            # otherwise, make sure the purpoted owner is actually the owner and permissions are set.
            with sp.if_(owner.is_some() & (utils.fa2_get_balance(self.data.places_contract, lot_id, owner.open_some()) > 0)):
                permission.value = sp.compute(self.permission_map.get_octal(self.data.permissions,
                    owner.open_some(),
                    permittee,
                    lot_id))

        return permission.value


    @sp.entry_point(lazify = True)
    def set_place_props(self, params):
        sp.set_type(params, sp.TRecord(
            lot_id =  sp.TNat,
            owner =  sp.TOption(sp.TAddress),
            props =  placePropsType,
            extension = extensionArgType
        ).layout(("lot_id", ("owner", ("props", "extension")))))

        self.onlyUnpaused()

        # Caller must have Full permissions.
        permissions = self.getPermissionsInline(params.lot_id, params.owner, sp.sender)
        sp.verify(permissions & permissionProps == permissionProps, message = self.error_message.no_permission())

        # Get or create the place.
        this_place = self.place_store_map.get_or_create(self.data.places, params.lot_id)

        # Verify the properties contrain at least the color (key 0x00).
        # And that the color is the right length.
        sp.verify(sp.len(params.props.get(sp.bytes("0x00"), message=self.error_message.parameter_error())) == placePropsColorLen,
            message = self.error_message.data_length())
        this_place.place_props = params.props

        # Increment interaction counter, next_id does not change.
        this_place.interaction_counter += 1

    def validateItemData(self, item_data):
        # Verify the item data has the right length.
        sp.verify(sp.len(item_data) >= itemDataMinLen, message = self.error_message.data_length())

    @sp.entry_point(lazify = True)
    def place_items(self, params):
        sp.set_type(params, sp.TRecord(
            lot_id = sp.TNat,
            owner = sp.TOption(sp.TAddress),
            item_list = sp.TList(placeItemListType),
            extension = extensionArgType
        ).layout(("lot_id", ("owner", ("item_list", "extension")))))

        self.onlyUnpaused()

        # Caller must have PlaceItems permissions.
        permissions = self.getPermissionsInline(params.lot_id, params.owner, sp.sender)
        sp.verify(permissions & permissionPlaceItems == permissionPlaceItems, message = self.error_message.no_permission())

        # Get or create the place.
        this_place = self.place_store_map.get_or_create(self.data.places, params.lot_id)

        # Count items in place item storage.
        place_item_count = sp.local("place_item_count", sp.nat(0))
        with sp.for_("issuer_map", this_place.stored_items.values()) as issuer_map:
            place_item_count.value += sp.len(issuer_map)

        # Make sure item limit is not exceeded.
        sp.verify(place_item_count.value + sp.len(params.item_list) <= self.data.item_limit, message = self.error_message.item_limit())

        # Get or create item storage.
        item_store = self.item_store_map.get_or_create(this_place.stored_items, sp.sender)

        # Our token transfer map.
        transferMap = sp.local("transferMap", sp.map(tkey = sp.TNat, tvalue = FA2.t_transfer_tx))

        # For each item in the list.
        with sp.for_("curr", params.item_list) as curr:
            with curr.match_cases() as arg:
                with arg.match("item") as item:
                    self.validateItemData(item.item_data)

                    # transfer item to this contract
                    # do multi-transfer by building up a list of transfers
                    with sp.if_(transferMap.value.contains(item.token_id)):
                        transferMap.value[item.token_id].amount += item.token_amount
                    with sp.else_():
                        transferMap.value[item.token_id] = sp.record(amount=item.token_amount, to_=sp.self_address, token_id=item.token_id)

                    # Add item to storage.
                    item_store[this_place.next_id] = sp.variant("item", sp.record(
                        item_amount = item.token_amount,
                        token_id = item.token_id,
                        mutez_per_item = item.mutez_per_token,
                        item_data = item.item_data))

                with arg.match("other") as other:
                    self.validateItemData(other.item_data)

                    # Check if FA2 token is permitted and get props.
                    fa2_props = self.getPermittedFA2Props(other.fa2)

                    # If swapping is not allowed, token_amount MUST be 1 and mutez_per_token MUST be 0.
                    with sp.if_(~ fa2_props.swap_allowed):
                        sp.verify((other.token_amount == sp.nat(1)) & (other.mutez_per_token == sp.tez(0)), message = self.error_message.parameter_error())

                    # Transfer external token to this contract. Only support 1 token per placement. No swaps.
                    utils.fa2_transfer(other.fa2, sp.sender, sp.self_address, other.token_id, other.token_amount)

                    # Add item to storage.
                    item_store[this_place.next_id] = sp.variant("other", sp.record(
                        item_amount = other.token_amount,
                        token_id = other.token_id,
                        mutez_per_item = other.mutez_per_token,
                        item_data = other.item_data,
                        fa2 = other.fa2))

                with arg.match("ext") as ext_data:
                    self.validateItemData(ext_data)
                    # Add item to storage.
                    item_store[this_place.next_id] = sp.variant("ext", ext_data)

            # Increment next_id.
            this_place.next_id += 1

        # only transfer if list has items
        with sp.if_(sp.len(transferMap.value) > 0):
            utils.fa2_transfer_multi(self.data.items_contract, sp.sender, transferMap.value.values())


    @sp.entry_point(lazify = True)
    def set_item_data(self, params):
        sp.set_type(params, sp.TRecord(
            lot_id = sp.TNat,
            owner = sp.TOption(sp.TAddress),
            update_map = sp.TMap(sp.TAddress, sp.TList(updateItemListType)),
            extension = extensionArgType
        ).layout(("lot_id", ("owner", ("update_map", "extension")))))

        self.onlyUnpaused()

        # Get the place - must exist.
        this_place = self.place_store_map.get(self.data.places, params.lot_id)

        # Caller must have ModifyAll or ModifyOwn permissions.
        permissions = self.getPermissionsInline(params.lot_id, params.owner, sp.sender)
        hasModifyAll = permissions & permissionModifyAll == permissionModifyAll

        # If ModifyAll permission is not given, make sure update map only contains sender items.
        with sp.if_(~hasModifyAll):
            with sp.for_("remove_key", params.update_map.keys()) as remove_key:
                sp.verify(remove_key == sp.sender, message = self.error_message.no_permission())

        # Update items.
        with sp.for_("issuer", params.update_map.keys()) as issuer:
            update_list = params.update_map[issuer]
            # Get item store - must exist.
            item_store = self.item_store_map.get(this_place.stored_items, issuer)
            
            with sp.for_("update", update_list) as update:
                self.validateItemData(update.item_data)

                with item_store[update.item_id].match_cases() as arg:
                    with arg.match("item") as immutable:
                        # sigh - variants are not mutable
                        item_var = sp.compute(immutable)
                        item_var.item_data = update.item_data
                        item_store[update.item_id] = sp.variant("item", item_var)
                    with arg.match("other") as immutable:
                        # sigh - variants are not mutable
                        other_var = sp.compute(immutable)
                        other_var.item_data = update.item_data
                        item_store[update.item_id] = sp.variant("other", other_var)
                    with arg.match("ext"):
                        item_store[update.item_id] = sp.variant("ext", update.item_data)

        # Increment interaction counter, next_id does not change.
        this_place.interaction_counter += 1


    @sp.entry_point(lazify = True)
    def remove_items(self, params):
        sp.set_type(params, sp.TRecord(
            lot_id = sp.TNat,
            owner = sp.TOption(sp.TAddress),
            remove_map = sp.TMap(sp.TAddress, sp.TList(sp.TNat)),
            extension = extensionArgType
        ).layout(("lot_id", ("owner", ("remove_map", "extension")))))

        self.onlyUnpaused()

        # Get the place - must exist.
        this_place = self.place_store_map.get(self.data.places, params.lot_id)

        # Caller must have ModifyAll or ModifyOwn permissions.
        permissions = self.getPermissionsInline(params.lot_id, params.owner, sp.sender)
        hasModifyAll = permissions & permissionModifyAll == permissionModifyAll

        # If ModifyAll permission is not given, make sure remove map only contains sender items.
        with sp.if_(~hasModifyAll):
            with sp.for_("remove_key", params.remove_map.keys()) as remove_key:
                sp.verify(remove_key == sp.sender, message = self.error_message.no_permission())

        # Our token transfer map.
        transferMap = sp.local("transferMap", sp.map(tkey = sp.TNat, tvalue = FA2.t_transfer_tx))

        # Remove items.
        with sp.for_("issuer", params.remove_map.keys()) as issuer:
            item_list = params.remove_map[issuer]
            # Get item store - must exist.
            item_store = self.item_store_map.get(this_place.stored_items, issuer)
            
            with sp.for_("curr", item_list) as curr:
                with item_store[curr].match_cases() as arg:
                    with arg.match("item") as the_item:
                        # Transfer all remaining items back to issuer
                        # do multi-transfer by building up a list of transfers
                        with sp.if_(transferMap.value.contains(the_item.token_id)):
                            transferMap.value[the_item.token_id].amount += the_item.item_amount
                        with sp.else_():
                            transferMap.value[the_item.token_id] = sp.record(amount=the_item.item_amount, to_=issuer, token_id=the_item.token_id)

                    with arg.match("other") as the_other:
                        # transfer external token back to the issuer. Only support 1 token.
                        utils.fa2_transfer(the_other.fa2, sp.self_address, issuer, the_other.token_id, the_other.item_amount)

                    # Nothing to do here with ext items. Just remove them.
                
                # Delete item from storage.
                del item_store[curr]

            # Remove the item store if empty.
            self.item_store_map.remove_if_empty(this_place.stored_items, issuer)

        # Increment interaction counter, next_id does not change.
        this_place.interaction_counter += 1

        # Only transfer if transfer map has items.
        with sp.if_(sp.len(transferMap.value) > 0):
            utils.fa2_transfer_multi(self.data.items_contract, sp.self_address, transferMap.value.values())


    # Lambda for sending royalties, fees, etc
    # It could be inlined, but instead we build a local lambda
    # to be reused in get_item.
    def sendValueRoyaltiesFeesLambda(self, params):
        sp.set_type(params, sp.TRecord(
            mutez_per_item = sp.TMutez,
            issuer = sp.TAddress,
            item_royalty_info = FA2.t_royalties
        ).layout(("mutez_per_item", ("issuer", "item_royalty_info"))))

        # Calculate fee and royalties.
        fee = sp.compute(sp.utils.mutez_to_nat(params.mutez_per_item) * (params.item_royalty_info.royalties + self.data.fees) / sp.nat(1000))
        royalties = sp.compute(params.item_royalty_info.royalties * fee / (params.item_royalty_info.royalties + self.data.fees))

        # Collect amounts to send in a map.
        send_map = sp.local("send_map", sp.map(tkey=sp.TAddress, tvalue=sp.TMutez))
        def addToSendMap(address, amount):
            send_map.value[address] = send_map.value.get(address, sp.mutez(0)) + amount

        # If there are any royalties to be paid.
        with sp.if_(royalties > sp.nat(0)):
            # Pay each contributor his relative share.
            with sp.for_("contributor", params.item_royalty_info.contributors) as contributor:
                # Calculate amount to be paid from relative share.
                absolute_amount = sp.compute(sp.utils.nat_to_mutez(royalties * contributor.relative_royalties / 1000))
                addToSendMap(contributor.address, absolute_amount)

        # TODO: don't localise nat_to_mutez, is probably a cast and free.
        # Send management fees.
        send_mgr_fees = sp.compute(sp.utils.nat_to_mutez(abs(fee - royalties)))
        addToSendMap(self.data.fees_to, send_mgr_fees)

        # Send rest of the value to seller.
        send_issuer = sp.compute(params.mutez_per_item - sp.utils.nat_to_mutez(fee))
        addToSendMap(params.issuer, send_issuer)

        # Transfer.
        with sp.for_("send", send_map.value.items()) as send:
            utils.send_if_value(send.key, send.value)


    @sp.entry_point(lazify = True)
    def get_item(self, params):
        sp.set_type(params, sp.TRecord(
            lot_id = sp.TNat,
            item_id = sp.TNat,
            issuer = sp.TAddress,
            extension = extensionArgType
        ).layout(("lot_id", ("item_id", ("issuer", "extension")))))

        self.onlyUnpaused()

        # Get the place - must exist.
        this_place = self.place_store_map.get(self.data.places, params.lot_id)

        # Get item store - must exist.
        item_store = self.item_store_map.get(this_place.stored_items, params.issuer)

        # Build a local lambda from sendValueRoyaltiesFeesLambda
        sendValueLocalLambda = sp.compute(sp.build_lambda(self.sendValueRoyaltiesFeesLambda, with_storage="read-only", with_operations=True))

        # Swap based on item type.
        with item_store[params.item_id].match_cases() as arg:
            # For tz1and native items.
            with arg.match("item") as immutable:
                # This is silly but required because match args are not mutable.
                the_item = sp.local("the_item", immutable)

                # Make sure it's for sale, and the transfered amount is correct.
                sp.verify(the_item.value.mutez_per_item > sp.mutez(0), message = self.error_message.not_for_sale())
                sp.verify(the_item.value.mutez_per_item == sp.amount, message = self.error_message.wrong_amount())

                # Transfer royalties, etc.
                with sp.if_(the_item.value.mutez_per_item != sp.tez(0)):
                    # Get the royalties for this item
                    item_royalty_info = sp.compute(utils.tz1and_items_get_royalties(self.data.items_contract, the_item.value.token_id))

                    # Send fees, royalties, value.
                    sp.compute(sendValueLocalLambda(sp.record(mutez_per_item=the_item.value.mutez_per_item, issuer=params.issuer, item_royalty_info=item_royalty_info)))
                
                # Transfer item to buyer.
                utils.fa2_transfer(self.data.items_contract, sp.self_address, sp.sender, the_item.value.token_id, 1)
                
                # Reduce the item count in storage or remove it.
                with sp.if_(the_item.value.item_amount > 1):
                    the_item.value.item_amount = abs(the_item.value.item_amount - 1)
                    item_store[params.item_id] = sp.variant("item", the_item.value)
                with sp.else_():
                    del item_store[params.item_id]

            # Other FA2 items.
            with arg.match("other") as immutable:
                # This is silly but required because match args are not mutable.
                the_item = sp.local("the_item", immutable)

                # Make sure it's for sale, and the transfered amount is correct.
                sp.verify(the_item.value.mutez_per_item > sp.mutez(0), message = self.error_message.not_for_sale())
                sp.verify(the_item.value.mutez_per_item == sp.amount, message = self.error_message.wrong_amount())

                # Transfer royalties, etc.
                with sp.if_(the_item.value.mutez_per_item != sp.tez(0)):
                    # Get the royalties for this item
                    item_royalty_info = sp.compute(self.getRoyaltiesForPermittedFA2(the_item.value.token_id, the_item.value.fa2))

                    # Send fees, royalties, value.
                    sp.compute(sendValueLocalLambda(sp.record(mutez_per_item=the_item.value.mutez_per_item, issuer=params.issuer, item_royalty_info=item_royalty_info)))
                
                # Transfer item to buyer.
                utils.fa2_transfer(the_item.value.fa2, sp.self_address, sp.sender, the_item.value.token_id, 1)
                
                # Reduce the item count in storage or remove it.
                with sp.if_(the_item.value.item_amount > 1):
                    the_item.value.item_amount = abs(the_item.value.item_amount - 1)
                    item_store[params.item_id] = sp.variant("other", the_item.value)
                with sp.else_():
                    del item_store[params.item_id]

            # ext items are unswappable.
            with arg.match("ext"):
                sp.failwith(self.error_message.wrong_item_type())
        
        # Remove the item store if empty.
        self.item_store_map.remove_if_empty(this_place.stored_items, params.issuer)

        # Increment interaction counter, next_id does not change.
        this_place.interaction_counter += 1


    #
    # Views
    #
    @sp.onchain_view(pure=True)
    def get_place_data(self, lot_id):
        sp.set_type(lot_id, sp.TNat)
        with sp.if_(self.data.places.contains(lot_id) == False):
            sp.result(sp.set_type_expr(placeStorageDefault, placeStorageType))
        with sp.else_():
            sp.result(sp.set_type_expr(self.data.places[lot_id], placeStorageType))


    @sp.onchain_view(pure=True)
    def get_place_seqnum(self, lot_id):
        sp.set_type(lot_id, sp.TNat)
        with sp.if_(self.data.places.contains(lot_id) == False):
            sp.result(sp.sha3(sp.pack(sp.pair(
                sp.nat(0),
                sp.nat(0)
            ))))
        with sp.else_():
            this_place = self.data.places[lot_id]
            sp.result(sp.sha3(sp.pack(sp.pair(
                this_place.interaction_counter,
                this_place.next_id
            ))))


    @sp.onchain_view(pure=True)
    def get_item_limit(self):
        sp.result(self.data.item_limit)


    @sp.onchain_view(pure=True)
    def get_permissions(self, query):
        sp.set_type(query, sp.TRecord(
            lot_id = sp.TNat,
            owner = sp.TOption(sp.TAddress),
            permittee = sp.TAddress
        ).layout(("lot_id", ("owner", "permittee"))))
        sp.result(self.getPermissionsInline(query.lot_id, query.owner, query.permittee))
