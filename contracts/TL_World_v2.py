# The World contract.
#
# Each lot belongs to a Place (an FA2 token that is the "land").
# Items (another type of token) can be stored on your Place, either to swap
# or just to build something nice.

import smartpy as sp

pause_mixin = sp.io.import_script_from_url("file:contracts/Pausable.py")
fees_mixin = sp.io.import_script_from_url("file:contracts/Fees.py")
mod_mixin = sp.io.import_script_from_url("file:contracts/Moderation.py")
allowed_place_tokens = sp.io.import_script_from_url("file:contracts/AllowedPlaceTokens.py")
upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
contract_metadata_mixin = sp.io.import_script_from_url("file:contracts/ContractMetadata.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")

# Now:
# TODO: the extra level for token address is to alleviate storage penalty for collections and other fa2s.
# TODO: chunks. separate storage in bigmap with key (place_key, chunk_id).
# TODO: place should have map of chunks with sequence numbers.
# TODO: collections. collection factory, minter and registry.
# TODO: allowed fa2s are checked against registry? which should also contain information about royalties.
# TODO: allow direct royalties? :( hate it but maybe have to allow it...
# TODO: 2-level fa2 transfer map?
# TODO: migration mechanism to allow recieving (from lower version) and forwarding items(to higher version) migrations. could do v1 to v2 migration as an upgrade to v1?
# TODO: figure out ext-type items. could in theory be a separate map on the issuer level?
# TODO: gas optimisations!
# TODO: per chunk AND per place interaction counter?
# TODO: restore v1 deply to be able to test deploy and upgrades on sandbox

# Probably kinda urgent:
# TODO: add a limit on place props data len and item data len. Potential gaslock.

# Other
# TODO: think of some more tests for permission.
# TODO: DAO token drop with merkle tree based on: https://github.com/AnshuJalan/token-drop-template
#       + Add a pause function and an expiration date for the drop.
#       + https://github.com/teia-community/teia-smart-contracts/blob/main/python/contracts/daoTokenDrop.py
# TODO: Does the places token even need to be administrated/minted by minter?
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

# NOTE: reccords in variants are immutable?
# See: https://gitlab.com/SmartPy/smartpy/-/issues/32
extensibleVariantType = sp.TVariant(
    item = itemRecordType,
    ext = sp.TBytes # transforms, etc
).layout(("item", "ext"))

#
# Item storage
# TODO: rename all these to make more sense...
# chunkStore = issuerStore?
# itemStore = tokenStore?
# itemStoreMap = itemStore?
# map from item id to item
itemStoreMapType = sp.TMap(sp.TNat, extensibleVariantType)
itemStoreMapLiteral = sp.map(tkey=sp.TNat, tvalue=extensibleVariantType)
# map from token address to item
itemStoreType = sp.TMap(sp.TAddress, itemStoreMapType)
itemStoreLiteral = sp.map(tkey=sp.TAddress, tvalue=itemStoreMapType)
# map from issuer to item store
chunkStoreType = sp.TMap(sp.TAddress, itemStoreType)
chunkStoreLiteral = sp.map(tkey=sp.TAddress, tvalue=itemStoreType)

# TODO: handle issuer and token store levels in this class, with remove if empty, etc.
class Item_store_map_old:
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
# Place prop storage
placePropsType = sp.TMap(sp.TBytes, sp.TBytes)
# only set color by default.
defaultPlaceProps = sp.map({sp.bytes("0x00"): sp.bytes('0x82b881')}, tkey=sp.TBytes, tvalue=sp.TBytes)

placeStorageType = sp.TRecord(
    next_id=sp.TNat,
    interaction_counter=sp.TNat,
    place_props=placePropsType,
    stored_items=chunkStoreType
).layout(("next_id", ("interaction_counter", ("place_props", "stored_items"))))

placeStorageDefault = sp.record(
    next_id = sp.nat(0),
    interaction_counter = sp.nat(0),
    place_props = defaultPlaceProps,
    stored_items=chunkStoreLiteral
)

placeKeyType = sp.TRecord(
    place_contract = sp.TAddress,
    lot_id = sp.TNat
).layout(("place_contract", "lot_id"))

class Place_store_map:
    def make(self):
        return sp.big_map(tkey=placeKeyType, tvalue=placeStorageType)
    def get(self, map, key):
        return map.get(key)
    def get_or_create(self, map, key):
        with sp.if_(~map.contains(key)):
            map[key] = placeStorageDefault
        return map[key]

#
# Chunk storage
# TODO:
#chunkStorageType = sp.TRecord(
#    next_id = sp.TNat, # per cunk item ids
#    chunk_storage=chunkStoreType
#)
#
#chunkStorageDefault = sp.record(
#    next_id = sp.nat(0),
#    chunk_storage=chunkStoreLiteral
#)

#chunkType = sp.TMap(sp.TAddress, # from issuer
#    sp.TMap(sp.TAddress, # to token
#        sp.TMap(sp.TNat, # to item id
#            extensibleVariantType # to item
#        )))

# TODO: per chunk item limit and chunk limit.
# TODO: this kind of breaks ext type items... could maybe store them with a special contract address????
# +++++ or maybe store ext type items in a special map???? or maybe it just doesn't matter under what token they are stored?
# +++++ or maybe the issuer map could be a record(ext_items_map, tokens_map)
class Item_store_map:
    def make(self):
        return chunkStoreLiteral

    def get(self, map, issuer, fa2):
        #map = sp.set_type_expr(map, chunkStoreType)
        #issuer = sp.set_type_expr(issuer, sp.TAddress)
        #fa2 = sp.set_type_expr(fa2, sp.TAddress)
        return map[issuer][fa2]

    def get_or_create(self, map, issuer, fa2):
        #map = sp.set_type_expr(map, chunkStoreType)
        #issuer = sp.set_type_expr(issuer, sp.TAddress)
        #fa2 = sp.set_type_expr(fa2, sp.TAddress)
        # if the issuer map does not exist, create it.
        with sp.if_(~map.contains(issuer)):
            map[issuer] = itemStoreLiteral
        # if the issuer map doesn't contain a map for the token, create it.
        with sp.if_(~map[issuer].contains(fa2)):
            map[issuer][fa2] = itemStoreMapLiteral
        return map[issuer][fa2]

    def remove_if_empty(self, map, issuer, fa2):
        #map = sp.set_type_expr(map, chunkStoreType)
        #issuer = sp.set_type_expr(issuer, sp.TAddress)
        #fa2 = sp.set_type_expr(fa2, sp.TAddress)
        # If the chunk has a map for the issuer
        with sp.if_(map.contains(issuer)):
            # and it has a map for the token and it's empty
            with sp.if_(map[issuer].contains(fa2) & (sp.len(map[issuer][fa2]) == 0)):
                # delete the issuer-token map
                del map[issuer][fa2]
            # if now the issuer map is empty
            with sp.if_(sp.len(map[issuer]) == 0):
                # delete the issuer map
                del map[issuer]

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
    ext = sp.TBytes
).layout(("item", "ext"))

itemDataMinLen = sp.nat(7) # format 0 is 7 bytes
placePropsColorLen = sp.nat(3) # 3 bytes for color

# Permissions are in octal.
# Can be any combination of these.
# Remove and modify own items in all places is always given. to prevent abuse.
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
    def chunk_limit(self):          return self.make("CHUNK_LIMIT")
    def chunk_item_limit(self):     return self.make("CHUNK_ITEM_LIMIT")
    def not_for_sale(self):         return self.make("NOT_FOR_SALE")
    def wrong_amount(self):         return self.make("WRONG_AMOUNT")
    def wrong_item_type(self):      return self.make("WRONG_ITEM_TYPE")
    def token_not_registered(self): return self.make("TOKEN_NOT_REGISTERED")

#
# Like Operator_set from legacy FA2. Lazy set for place permissions.
class Permission_map:
    def key_type(self):
        return sp.TRecord(owner = sp.TAddress,
                          permittee = sp.TAddress,
                          place_key = placeKeyType
                          ).layout(("owner", ("permittee", "place_key")))

    def make(self):
        return sp.big_map(tkey = self.key_type(), tvalue = sp.TNat)

    def make_key(self, owner, permittee, place_key):
        metakey = sp.record(owner = owner,
                            permittee = permittee,
                            place_key = place_key)
        metakey = sp.set_type_expr(metakey, self.key_type())
        return metakey

    def add(self, set, owner, permittee, place_key, perm):
        set[self.make_key(owner, permittee, place_key)] = perm

    def remove(self, set, owner, permittee, place_key):
        del set[self.make_key(owner, permittee, place_key)]

    def is_member(self, set, owner, permittee, place_key):
        return set.contains(self.make_key(owner, permittee, place_key))

    def get_octal(self, set, owner, permittee, place_key):
        return set.get(self.make_key(owner, permittee, place_key), default_value = permissionNone)

#
# Like Operator_param from legacy Fa2. Defines type types for the set_permissions entry-point.
class Permission_param:
    def get_add_type(self):
        t = sp.TRecord(
            owner = sp.TAddress,
            permittee = sp.TAddress,
            place_key = placeKeyType,
            perm = sp.TNat).layout(("owner", ("permittee", ("place_key", "perm"))))
        return t

    def make_add(self, owner, permittee, place_key, perm):
        r = sp.record(owner = owner,
            permittee = permittee,
            place_key = place_key,
            perm = perm)
        return sp.set_type_expr(r, self.get_add_type())

    def get_remove_type(self):
        t = sp.TRecord(
            owner = sp.TAddress,
            permittee = sp.TAddress,
            place_key = placeKeyType).layout(("owner", ("permittee", "place_key")))
        return t

    def make_remove(self, owner, permittee, place_key):
        r = sp.record(owner = owner,
            permittee = permittee,
            place_key = place_key)
        return sp.set_type_expr(r, self.get_remove_type())

#
# The World contract.
# NOTE: should be pausable for code updates and because other item fa2 tokens are out of our control.
class TL_World(
    contract_metadata_mixin.ContractMetadata,
    pause_mixin.Pausable,
    fees_mixin.Fees,
    mod_mixin.Moderation,
    allowed_place_tokens.AllowedPlaceTokens,
    upgradeable_mixin.Upgradeable,
    sp.Contract):
    def __init__(self, administrator, items_contract, places_contract, token_registry, metadata, name, description, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")
        # Not a win at all in terms of gas, especially on the simpler eps.
        #self.add_flag("lazy-entry-points")
        # No noticeable effect on gas.
        #self.add_flag("initial-cast")
        # Makes much smaller code but removes annots from eps.
        #self.add_flag("simplify-via-michel")

        items_contract = sp.set_type_expr(items_contract, sp.TAddress)
        places_contract = sp.set_type_expr(places_contract, sp.TAddress)
        token_registry = sp.set_type_expr(token_registry, sp.TAddress)
        
        self.error_message = Error_message()
        self.permission_map = Permission_map()
        self.permission_param = Permission_param()
        self.place_store_map = Place_store_map()
        self.item_store_map = Item_store_map()
        self.init_storage(
            items_contract = items_contract,
            places_contract = places_contract,
            token_registry = token_registry,
            max_permission = permissionFull, # must be (power of 2)-1
            permissions = self.permission_map.make(),
            places = self.place_store_map.make()
        )
        contract_metadata_mixin.ContractMetadata.__init__(self, administrator = administrator, metadata = metadata)
        pause_mixin.Pausable.__init__(self, administrator = administrator)
        fees_mixin.Fees.__init__(self, administrator = administrator)
        mod_mixin.Moderation.__init__(self, administrator = administrator)
        allowed_place_tokens.AllowedPlaceTokens.__init__(self, administrator = administrator)
        upgradeable_mixin.Upgradeable.__init__(self, administrator = administrator)
        self.generate_contract_metadata(name, description)

    def generate_contract_metadata(self, name, description):
        """Generate a metadata json file with all the contract's offchain views
        and standard TZIP-12 and TZIP-016 key/values."""
        metadata_base = {
            "name": name,
            "description": description,
            "version": "2.0.0",
            "interfaces": ["TZIP-012", "TZIP-016"],
            "authors": [
                "852Kerfunkle <https://github.com/852Kerfunkle>"
            ],
            "homepage": "https://www.tz1and.com",
            "source": {
                "tools": ["SmartPy"],
                "location": "https://github.com/tz1and",
            },
            "license": { "name": "UNLICENSED" }
        }
        offchain_views = []
        for f in dir(self):
            attr = getattr(self, f)
            if isinstance(attr, sp.OnOffchainView):
                # Include onchain views as tip 16 offchain views
                offchain_views.append(attr)
        metadata_base["views"] = offchain_views
        self.init_metadata("metadata_base", metadata_base)


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
                    # can only add permissions for allowed places
                    self.onlyAllowedPlaceTokens(upd.place_key.place_contract)
                    # Sender must be the owner
                    sp.verify(upd.owner == sp.sender, message = self.error_message.not_owner())
                    sp.verify((upd.perm > permissionNone) & (upd.perm <= self.data.max_permission), message = self.error_message.parameter_error())
                    # Add permission
                    self.permission_map.add(self.data.permissions,
                        upd.owner,
                        upd.permittee,
                        upd.place_key,
                        upd.perm)
                with arg.match("remove_permission") as upd:
                    # NOTE: don't need to check if place key is valid
                    #self.onlyAllowedPlaceTokens(upd.place_key.place_contract)
                    # Sender must be the owner
                    sp.verify(upd.owner == sp.sender, message = self.error_message.not_owner())
                    # Remove permission
                    self.permission_map.remove(self.data.permissions,
                        upd.owner,
                        upd.permittee,
                        upd.place_key)


    # Don't use private lambda because we need to be able to update code
    # Also, duplicating code is cheaper at runtime.
    def getPermissionsInline(self, place_key, owner, permittee):
        place_key = sp.set_type_expr(place_key, placeKeyType)
        owner = sp.set_type_expr(owner, sp.TOption(sp.TAddress))
        permittee = sp.set_type_expr(permittee, sp.TAddress)

        # TODO: check if place contract is allowed in this world.

        # Local var for permissions.
        permission = sp.local("permission", permissionNone)

        # If permittee is the owner, he has full permission.
        with sp.if_(utils.fa2_get_balance(place_key.place_contract, place_key.lot_id, permittee) > 0):
            permission.value = self.data.max_permission
        with sp.else_():
            # otherwise, make sure the purpoted owner is actually the owner and permissions are set.
            with sp.if_(owner.is_some() & (utils.fa2_get_balance(place_key.place_contract, place_key.lot_id, owner.open_some()) > 0)):
                permission.value = sp.compute(self.permission_map.get_octal(self.data.permissions,
                    owner.open_some(),
                    permittee,
                    place_key))

        return permission.value


    @sp.entry_point(lazify = True)
    def set_place_props(self, params):
        sp.set_type(params, sp.TRecord(
            place_key =  placeKeyType,
            owner =  sp.TOption(sp.TAddress),
            props =  placePropsType,
            extension = extensionArgType
        ).layout(("place_key", ("owner", ("props", "extension")))))

        self.onlyUnpaused()

        # Place token must be allowed
        self.onlyAllowedPlaceTokens(params.place_key.place_contract)

        # Caller must have Full permissions.
        permissions = self.getPermissionsInline(params.place_key, params.owner, sp.sender)
        sp.verify(permissions & permissionProps == permissionProps, message = self.error_message.no_permission())

        # Get or create the place.
        this_place = self.place_store_map.get_or_create(self.data.places, params.place_key)

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


    def getTokenRegistry(self, fa2):
        return sp.view("is_registered", self.data.token_registry,
            sp.set_type_expr(fa2, sp.TAddress),
            t = sp.TBool).open_some()


    @sp.entry_point(lazify = True)
    def place_items(self, params):
        sp.set_type(params, sp.TRecord(
            place_key =  placeKeyType,
            owner = sp.TOption(sp.TAddress),
            place_item_map = sp.TMap(sp.TAddress, sp.TList(placeItemListType)),
            extension = extensionArgType
        ).layout(("place_key", ("owner", ("place_item_map", "extension")))))

        self.onlyUnpaused()

        # Place token must be allowed
        place_limits = self.getAllowedPlaceToken(params.place_key.place_contract)

        # Caller must have PlaceItems permissions.
        permissions = self.getPermissionsInline(params.place_key, params.owner, sp.sender)
        sp.verify(permissions & permissionPlaceItems == permissionPlaceItems, message = self.error_message.no_permission())

        # Get or create the place.
        this_place = self.place_store_map.get_or_create(self.data.places, params.place_key)

        # Count items in place item storage.
        place_item_count = sp.local("place_item_count", sp.nat(0))
        with sp.for_("issuer_map", this_place.stored_items.values()) as issuer_map:
            with sp.for_("token_map", issuer_map.values()) as token_map:
                place_item_count.value += sp.len(token_map)

        # Count items to be added.
        add_item_count = sp.local("add_item_count", sp.nat(0))
        with sp.for_("item_list", params.place_item_map.values()) as item_list:
            add_item_count.value += sp.len(item_list)

        # Make sure chunk item limit is not exceeded.
        sp.verify(place_item_count.value + add_item_count.value <= place_limits.chunk_item_limit, message = self.error_message.chunk_item_limit())

        # For each fa2 in the map.
        with sp.for_("fa2", params.place_item_map.keys()) as fa2:
            item_list = params.place_item_map[fa2]

            # Get or create item storage.
            item_store = self.item_store_map.get_or_create(this_place.stored_items, sp.sender, fa2)

            # Our token transfer map.
            # TODO: we could do this outside the loops with a 2-level transfer map
            transferMap = sp.local("transferMap", sp.map(tkey = sp.TNat, tvalue = FA2.t_transfer_tx))

            # For each item in the list.
            with sp.for_("curr", item_list) as curr:
                with curr.match_cases() as arg:
                    with arg.match("item") as item:
                        self.validateItemData(item.item_data)

                        registered = self.getTokenRegistry(fa2)
                        sp.verify(registered == True, self.error_message.token_not_registered())

                        # TODO:
                        # Token registry should be a separate contract
                        ## Check if FA2 token is permitted and get props.
                        #fa2_props = self.getPermittedFA2Props(fa2)
                        #
                        ## If swapping is not allowed, token_amount MUST be 1 and mutez_per_token MUST be 0.
                        #with sp.if_(~ fa2_props.swap_allowed):
                        #    sp.verify((item.token_amount == sp.nat(1)) & (item.mutez_per_token == sp.tez(0)), message = self.error_message.parameter_error())

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

                    with arg.match("ext") as ext_data:
                        self.validateItemData(ext_data)
                        # Add item to storage.
                        item_store[this_place.next_id] = sp.variant("ext", ext_data)

                # Increment next_id.
                this_place.next_id += 1

            # only transfer if list has items
            # TODO: we could do this outside the loops with a 2-level transfer map
            with sp.if_(sp.len(transferMap.value) > 0):
                utils.fa2_transfer_multi(fa2, sp.sender, transferMap.value.values())


    @sp.entry_point(lazify = True)
    def set_item_data(self, params):
        sp.set_type(params, sp.TRecord(
            place_key =  placeKeyType,
            owner = sp.TOption(sp.TAddress),
            update_map = sp.TMap(sp.TAddress, sp.TMap(sp.TAddress, sp.TList(updateItemListType))),
            extension = extensionArgType
        ).layout(("place_key", ("owner", ("update_map", "extension")))))

        self.onlyUnpaused()

        # Place token must be allowed
        self.onlyAllowedPlaceTokens(params.place_key.place_contract)

        # Get the place - must exist.
        this_place = self.place_store_map.get(self.data.places, params.place_key)

        # Caller must have ModifyAll or ModifyOwn permissions.
        permissions = self.getPermissionsInline(params.place_key, params.owner, sp.sender)
        hasModifyAll = permissions & permissionModifyAll == permissionModifyAll

        # If ModifyAll permission is not given, make sure update map only contains sender items.
        with sp.if_(~hasModifyAll):
            with sp.for_("remove_key", params.update_map.keys()) as remove_key:
                sp.verify(remove_key == sp.sender, message = self.error_message.no_permission())

        # Update items.
        with sp.for_("issuer", params.update_map.keys()) as issuer:
            with sp.for_("fa2", params.update_map[issuer].keys()) as fa2:
                update_list = params.update_map[issuer][fa2]
                # Get item store - must exist.
                item_store = self.item_store_map.get(this_place.stored_items, issuer, fa2)
                
                with sp.for_("update", update_list) as update:
                    self.validateItemData(update.item_data)

                    with item_store[update.item_id].match_cases() as arg:
                        with arg.match("item") as immutable:
                            # sigh - variants are not mutable
                            item_var = sp.compute(immutable)
                            item_var.item_data = update.item_data
                            item_store[update.item_id] = sp.variant("item", item_var)
                        with arg.match("ext"):
                            item_store[update.item_id] = sp.variant("ext", update.item_data)

        # Increment interaction counter, next_id does not change.
        this_place.interaction_counter += 1


    @sp.entry_point(lazify = True)
    def remove_items(self, params):
        sp.set_type(params, sp.TRecord(
            place_key =  placeKeyType,
            owner = sp.TOption(sp.TAddress),
            remove_map = sp.TMap(sp.TAddress, sp.TMap(sp.TAddress, sp.TList(sp.TNat))),
            extension = extensionArgType
        ).layout(("place_key", ("owner", ("remove_map", "extension")))))

        self.onlyUnpaused()

        # TODO: Place token must be allowed?
        #self.onlyAllowedPlaceTokens(params.place_key.place_contract)

        # Get the place - must exist.
        this_place = self.place_store_map.get(self.data.places, params.place_key)

        # Caller must have ModifyAll or ModifyOwn permissions.
        permissions = self.getPermissionsInline(params.place_key, params.owner, sp.sender)
        hasModifyAll = permissions & permissionModifyAll == permissionModifyAll

        # If ModifyAll permission is not given, make sure remove map only contains sender items.
        with sp.if_(~hasModifyAll):
            with sp.for_("remove_key", params.remove_map.keys()) as remove_key:
                sp.verify(remove_key == sp.sender, message = self.error_message.no_permission())

        # Remove items.
        with sp.for_("issuer", params.remove_map.keys()) as issuer:
            with sp.for_("fa2", params.remove_map[issuer].keys()) as fa2:
                item_list = params.remove_map[issuer][fa2]

                # Get item store - must exist.
                item_store = self.item_store_map.get(this_place.stored_items, issuer, fa2)

                # Our token transfer map.
                # TODO: we could do this outside the loops with a 2-level transfer map
                transferMap = sp.local("transferMap", sp.map(tkey = sp.TNat, tvalue = FA2.t_transfer_tx))
                
                with sp.for_("curr", item_list) as curr:
                    with item_store[curr].match_cases() as arg:
                        with arg.match("item") as the_item:
                            # TODO: 2 level transfer map!
                            # Transfer all remaining items back to issuer
                            # do multi-transfer by building up a list of transfers
                            with sp.if_(transferMap.value.contains(the_item.token_id)):
                                transferMap.value[the_item.token_id].amount += the_item.item_amount
                            with sp.else_():
                                transferMap.value[the_item.token_id] = sp.record(amount=the_item.item_amount, to_=issuer, token_id=the_item.token_id)

                        # Nothing to do here with ext items. Just remove them.
                    
                    # Delete item from storage.
                    del item_store[curr]

                # Only transfer if transfer map has items.
                # TODO: we could do this outside the loops with a 2-level transfer map
                with sp.if_(sp.len(transferMap.value) > 0):
                    utils.fa2_transfer_multi(fa2, sp.self_address, transferMap.value.values())

                # Remove the item store if empty.
                self.item_store_map.remove_if_empty(this_place.stored_items, issuer, fa2)

        # Increment interaction counter, next_id does not change.
        this_place.interaction_counter += 1


    # Inline function for sending royalties, fees, etc
    def sendValueRoyaltiesFeesInline(self, params):
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
            place_key =  placeKeyType,
            item_id = sp.TNat,
            issuer = sp.TAddress,
            fa2 = sp.TAddress,
            extension = extensionArgType
        ).layout(("place_key", ("item_id", ("issuer", ("fa2", "extension"))))))

        self.onlyUnpaused()

        # TODO: Place token must be allowed?
        #self.onlyAllowedPlaceTokens(params.place_key.place_contract)

        # Get the place - must exist.
        this_place = self.place_store_map.get(self.data.places, params.place_key)

        # Get item store - must exist.
        item_store = self.item_store_map.get(this_place.stored_items, params.issuer, params.fa2)

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
                    # TODO: royalties for non-tz1and items? maybe token registry could handle that to some extent?
                    # at least in terms of what "type" of royalties.
                    item_royalty_info = sp.compute(utils.tz1and_items_get_royalties(params.fa2, the_item.value.token_id))

                    # Send fees, royalties, value.
                    self.sendValueRoyaltiesFeesInline(sp.record(mutez_per_item=the_item.value.mutez_per_item, issuer=params.issuer, item_royalty_info=item_royalty_info))
                
                # Transfer item to buyer.
                utils.fa2_transfer(params.fa2, sp.self_address, sp.sender, the_item.value.token_id, 1)
                
                # Reduce the item count in storage or remove it.
                with sp.if_(the_item.value.item_amount > 1):
                    the_item.value.item_amount = abs(the_item.value.item_amount - 1)
                    item_store[params.item_id] = sp.variant("item", the_item.value)
                with sp.else_():
                    del item_store[params.item_id]

            # ext items are unswappable.
            with arg.match("ext"):
                sp.failwith(self.error_message.wrong_item_type())
        
        # Remove the item store if empty.
        self.item_store_map.remove_if_empty(this_place.stored_items, params.issuer, params.fa2)

        # Increment interaction counter, next_id does not change.
        this_place.interaction_counter += 1


    #
    # Views
    #
    @sp.onchain_view(pure=True)
    def get_place_data(self, place_key):
        sp.set_type(place_key, placeKeyType)
        with sp.if_(self.data.places.contains(place_key) == False):
            sp.result(sp.set_type_expr(placeStorageDefault, placeStorageType))
        with sp.else_():
            sp.result(sp.set_type_expr(self.data.places[place_key], placeStorageType))


    @sp.onchain_view(pure=True)
    def get_place_seqnum(self, place_key):
        sp.set_type(place_key, placeKeyType)
        with sp.if_(self.data.places.contains(place_key) == False):
            sp.result(sp.sha3(sp.pack(sp.pair(
                sp.nat(0),
                sp.nat(0)
            ))))
        with sp.else_():
            this_place = self.data.places[place_key]
            sp.result(sp.sha3(sp.pack(sp.pair(
                this_place.interaction_counter,
                this_place.next_id
            ))))


    @sp.onchain_view(pure=True)
    def get_permissions(self, query):
        sp.set_type(query, sp.TRecord(
            place_key = placeKeyType,
            owner = sp.TOption(sp.TAddress),
            permittee = sp.TAddress
        ).layout(("place_key", ("owner", "permittee"))))
        sp.result(self.getPermissionsInline(query.place_key, query.owner, query.permittee))
