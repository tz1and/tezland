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
registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")

# Now:
# TODO: get_place_data should take list of chunks to query. should return data in same view as get_place_data? maybe with selectable chunks?
# TODO: registry which should also contain information about royalties. maybe merkle tree stuff.
# TODO: consider where to put merkle tree proofs when placing (allowed fa2) and getting (royalties) items.
#       + properly define the royalties type for the merkle proof stuff. probably the same as explicit royalties!
# TODO: allow direct royalties? :( hate it but maybe have to allow it...
# TODO: royalties for non-tz1and items? maybe token registry could handle that to some extent?
#       at least in terms of what "type" of royalties.
# TODO: figure out ext-type items. could in theory be a separate map on the issuer level? maybe have token addess and option and make ext items go into sp.none?
# TODO: gas optimisations!
# TODO: FA2 origination is too large! try and optimise
# TODO: try to always use .get_opt()/.get() instead of contains/[] on maps/bigmaps. makes nasty code otherwise. duplicate/empty fails.
# TODO: delete empty chunks? chunk store remove_if_empty. make sure to delete them from place as well.
# TODO: investigate use of inline_result. and bound blocks in general.
# TODO: test owner = none when sender not place owner (for all eps where it matters)
# TODO: test owner = "not actual owner" when issuer is none for get_item.
# TODO: test owner = "not actual owner" when issuer is none for remove_items.
# TODO: so many empty FAILWITHs. Optimise...
# TODO: use open_some(unit) where it makes sense (views?)
# TODO: special permission for sending items to place? Might be good.
# TODO: add tests issuerOrPlaceOwnerInline. to make sure they work correctly in all combinations.
# TODO: optional send_to address on swaps. to allow customising where tez are sent to.
# TODO: re-distributing places. added get_owner view
# TODO: if a place is on auction and someone buys an item owned by the place, the tez would be sent to the auction contract.
#       I could change the auction contract so it does the "ask" thing instead - where you make a swap but only set operators instead of actually transferring the nft.
#       but it could lead to people just spamming auctions for the same place or revoking operators and having a bunch of dead auctions
#       I think you can make contract deny tez sent to it. I could just do that for the auction contract. which means you're not able to buy place owned items from a place on auction (since it actually doesn't have an owner)
#       Can also have a global optional "send to" address in the place that can be set by the auction contract.
# TODO: solution for the legacy collection mint issues:
#       - legacy public collection will be handled by V1 minter.
#       - maybe just don't allow minting in legacy collection anymore.
#       - add a mint_v1 entrypoint to minter v2
# TODO: validate royalties in minter to save origination fees.
# TODO: migrate: don't set operators, transfer tokens directly to world v2.
# TODO: make sure royalties version is set correctly everywhere.


# maybe?
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
#
#
# V2
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
    token_id=sp.TNat, # the fa2 token id
    token_amount=sp.TNat, # number of fa2 tokens to store.
    mutez_per_token=sp.TMutez, # 0 if not for sale.
    item_data=sp.TBytes, # transforms, etc
    send_to=sp.TOption(sp.TAddress), # where to send the tez
).layout(("token_id", ("token_amount", ("mutez_per_token", ("item_data", "send_to")))))

# NOTE: reccords in variants are immutable?
# See: https://gitlab.com/SmartPy/smartpy/-/issues/32
extensibleVariantItemType = sp.TVariant(
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
itemStoreMapType = sp.TMap(sp.TNat, extensibleVariantItemType)
itemStoreMapLiteral = sp.map(tkey=sp.TNat, tvalue=extensibleVariantItemType)
# map from token address to item
itemStoreType = sp.TMap(sp.TAddress, itemStoreMapType)
itemStoreLiteral = sp.map(tkey=sp.TAddress, tvalue=itemStoreMapType)
# map from issuer to item store
chunkStoreType = sp.TMap(sp.TOption(sp.TAddress), itemStoreType)
chunkStoreLiteral = sp.map(tkey=sp.TOption(sp.TAddress), tvalue=itemStoreType)

#
# Place prop storage
placePropsType = sp.TMap(sp.TBytes, sp.TBytes)
# only set color by default.
defaultPlaceProps = sp.map({sp.bytes("0x00"): sp.bytes('0x82b881')}, tkey=sp.TBytes, tvalue=sp.TBytes)

placeStorageType = sp.TRecord(
    interaction_counter=sp.TNat,
    place_props=placePropsType,
    chunks=sp.TSet(sp.TNat)
).layout(("interaction_counter", ("place_props", "chunks")))

placeStorageDefault = sp.record(
    interaction_counter = sp.nat(0),
    place_props = defaultPlaceProps,
    chunks = sp.set([]))

placeKeyType = sp.TRecord(
    place_contract = sp.TAddress,
    lot_id = sp.TNat
).layout(("place_contract", "lot_id"))

placeMapType = sp.TBigMap(placeKeyType, placeStorageType)
placeMapLiteral = sp.big_map(tkey=placeKeyType, tvalue=placeStorageType)


class Place_store_map:
    def make(self):
        return placeMapLiteral

    def get(self, map, key):
        sp.set_type(map, placeMapType)
        sp.set_type(key, placeKeyType)
        return map.get(key)

    def get_or_create(self, map, key):
        sp.set_type(map, placeMapType)
        sp.set_type(key, placeKeyType)
        with sp.if_(~map.contains(key)):
            map[key] = placeStorageDefault
        return map[key]

#
# Chunk storage
chunkStorageType = sp.TRecord(
    next_id = sp.TNat, # per chunk item ids
    interaction_counter=sp.TNat,
    stored_items=chunkStoreType
).layout(("next_id", ("interaction_counter", "stored_items")))

chunkStorageDefault = sp.record(
    next_id = sp.nat(0),
    interaction_counter=sp.nat(0),
    stored_items=chunkStoreLiteral)

chunkPlaceKeyType = sp.TRecord(
    place_key = placeKeyType,
    chunk_id = sp.TNat
).layout(("place_key", "chunk_id"))

placeDataParam = sp.TRecord(
    place_key = placeKeyType,
    chunk_ids = sp.TSet(sp.TNat)
).layout(("place_key", "chunk_ids"))

placeDataResultType = sp.TRecord(
    place = placeStorageType,
    chunks = sp.TMap(sp.TNat, chunkStorageType)
).layout(("place", "chunks"))

chunkMapType = sp.TBigMap(chunkPlaceKeyType, chunkStorageType)
chunkMapLiteral = sp.big_map(tkey=chunkPlaceKeyType, tvalue=chunkStorageType)


class Chunk_store_map:
    def make(self):
        return chunkMapLiteral

    def get(self, map, key):
        sp.set_type(map, chunkMapType)
        sp.set_type(key, chunkPlaceKeyType)
        return map.get(key)

    def get_or_create(self, map, key, place):
        sp.set_type(map, chunkMapType)
        sp.set_type(key, chunkPlaceKeyType)
        sp.set_type(place, placeStorageType)
        with sp.if_(~map.contains(key)):
            map[key] = chunkStorageDefault
            place.chunks.add(key.chunk_id)
        return map[key]

    # TODO: remove_if_empty

#
# Item storage
# TODO: this kind of breaks ext type items... could maybe store them with a special contract address????
# +++++ or maybe store ext type items in a special map???? or maybe it just doesn't matter under what token they are stored?
# +++++ or maybe the issuer map could be a record(ext_items_map, tokens_map)
class Item_store_map:
    def make(self):
        return chunkStoreLiteral

    def get(self, map, issuer, fa2):
        sp.set_type(map, chunkStoreType)
        sp.set_type(issuer, sp.TOption(sp.TAddress))
        sp.set_type(fa2, sp.TAddress)
        return map[issuer][fa2]

    def get_or_create(self, map, issuer, fa2):
        sp.set_type(map, chunkStoreType)
        sp.set_type(issuer, sp.TOption(sp.TAddress))
        sp.set_type(fa2, sp.TAddress)
        # if the issuer map does not exist, create it.
        with sp.if_(~map.contains(issuer)):
            map[issuer] = itemStoreLiteral
        # if the issuer map doesn't contain a map for the token, create it.
        with sp.if_(~map[issuer].contains(fa2)):
            map[issuer][fa2] = itemStoreMapLiteral
        return map[issuer][fa2]

    def remove_if_empty(self, map, issuer, fa2):
        sp.set_type(map, chunkStoreType)
        sp.set_type(issuer, sp.TOption(sp.TAddress))
        sp.set_type(fa2, sp.TAddress)
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

setPlacePropsVariantType = sp.TVariant(
    add_props = placePropsType,
    del_props = sp.TList(sp.TBytes)
).layout(("add_props", "del_props"))

updateItemListType = sp.TRecord(
    item_id=sp.TNat,
    item_data=sp.TBytes
).layout(("item_id", "item_data"))

seqNumResultType = sp.TRecord(
    place_seq_num = sp.TBytes,
    chunk_seq_nums = sp.TMap(sp.TNat, sp.TBytes)
).layout(("place_seq_num", "chunk_seq_nums"))

# Types for the migration ep.
migrationItemMapType = sp.TMap(sp.TAddress, sp.TMap(sp.TAddress, sp.TList(extensibleVariantItemType)))

migrationType = sp.TRecord(
    place_key = placeKeyType,
    # For migration from v1 we basically need the same data as a chunk but with a list as the leaf.
    migrate_item_map = migrationItemMapType,
    migrate_place_props = placePropsType,
    extension = extensionArgType
).layout(("place_key", ("migrate_item_map", ("migrate_place_props", "extension"))))

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
    def parameter_error(self):      return self.make("PARAM_ERROR")
    def data_length(self):          return self.make("DATA_LEN")
    def chunk_limit(self):          return self.make("CHUNK_LIMIT")
    def chunk_item_limit(self):     return self.make("CHUNK_ITEM_LIMIT")
    def not_for_sale(self):         return self.make("NOT_FOR_SALE")
    def wrong_amount(self):         return self.make("WRONG_AMOUNT")
    def wrong_item_type(self):      return self.make("WRONG_ITEM_TYPE")
    def token_not_registered(self): return self.make("TOKEN_NOT_REGISTERED")
    def unknown_owner(self):        return self.make("UNKNOWN_OWNER")

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
        return sp.set_type_expr(metakey, self.key_type())

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
    def __init__(self, administrator, token_registry, paused, items_tokens, metadata,
        name, description, exception_optimization_level="default-line"):

        # Needed for migration ep but not really needed otherwise.
        self.items_tokens = sp.set_type_expr(items_tokens, sp.TAddress)

        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")
        # Not a win at all in terms of gas, especially on the simpler eps.
        #self.add_flag("lazy-entry-points")
        # No noticeable effect on gas.
        #self.add_flag("initial-cast")
        # Makes much smaller code but removes annots from eps.
        #self.add_flag("simplify-via-michel")

        token_registry = sp.set_type_expr(token_registry, sp.TAddress)
        
        self.error_message = Error_message()
        self.permission_map = Permission_map()
        self.permission_param = Permission_param()
        self.place_store_map = Place_store_map()
        self.chunk_store_map = Chunk_store_map()
        self.item_store_map = Item_store_map()

        self.init_storage(
            token_registry = token_registry,
            migration_contract = sp.none,
            max_permission = permissionFull, # must be (power of 2)-1
            permissions = self.permission_map.make(),
            places = self.place_store_map.make(),
            chunks = self.chunk_store_map.make()
        )

        self.available_settings = [
            ("token_registry", sp.TAddress, None),
            ("migration_contract", sp.TOption(sp.TAddress), None),
            ("max_permission", sp.TNat, lambda x: sp.verify(utils.isPowerOfTwoMinusOne(x), message=self.error_message.parameter_error()))
        ]

        contract_metadata_mixin.ContractMetadata.__init__(self, administrator = administrator, metadata = metadata, meta_settings = True)
        pause_mixin.Pausable.__init__(self, administrator = administrator, paused = paused, meta_settings = True)
        fees_mixin.Fees.__init__(self, administrator = administrator, meta_settings = True)
        mod_mixin.Moderation.__init__(self, administrator = administrator, meta_settings = True)
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


    @sp.entry_point(lazify = True)
    def update_settings(self, params):
        """Allows the administrator to update various settings.
        
        Parameters are metaprogrammed with self.available_settings"""
        sp.set_type(params, sp.TList(sp.TVariant(
            **{setting[0]: setting[1] for setting in self.available_settings})))

        self.onlyAdministrator()

        with sp.for_("update", params) as update:
            with update.match_cases() as arg:
                for setting in self.available_settings:
                    with arg.match(setting[0]) as value:
                        if setting[2] != None:
                            setting[2](value)
                        setattr(self.data, setting[0], value)


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
    @sp.inline_result
    def getPermissionsInline(self, place_key, permittee):
        sp.set_type(place_key, placeKeyType)
        sp.set_type(permittee, sp.TAddress)

        # NOTE: no need to check if place contract is allowed in this world.

        place_owner = sp.local("place_owner", FA2.fa2_nft_get_owner(place_key.place_contract, place_key.lot_id))

        # If permittee is the owner, he has full permission.
        with sp.if_(place_owner.value == permittee):
            sp.result(sp.pair(place_owner.value, self.data.max_permission))
        # Else, query permissions.
        with sp.else_():
            sp.result(sp.pair(place_owner.value, self.permission_map.get_octal(self.data.permissions,
                place_owner.value,
                permittee,
                place_key)))


    @sp.entry_point(lazify = True)
    def update_place_props(self, params):
        sp.set_type(params, sp.TRecord(
            place_key = placeKeyType,
            prop_updates = sp.TList(setPlacePropsVariantType),
            extension = extensionArgType
        ).layout(("place_key", ("prop_updates", "extension"))))

        self.onlyUnpaused()

        # Place token must be allowed
        self.onlyAllowedPlaceTokens(params.place_key.place_contract)

        # Caller must have Full permissions.
        permissions = sp.snd(self.getPermissionsInline(params.place_key, sp.sender))
        sp.verify(permissions & permissionProps == permissionProps, message = self.error_message.no_permission())

        # Get or create the place.
        this_place = self.place_store_map.get_or_create(self.data.places, params.place_key)

        with sp.for_("item", params.prop_updates) as item:
            with item.match_cases() as arg:
                with arg.match("add_props") as add_props:
                    with sp.for_("prop", add_props.items()) as prop:
                        this_place.place_props[prop.key] = prop.value

                with arg.match("del_props") as del_props:
                    with sp.for_("prop", del_props) as prop:
                        del this_place.place_props[prop]

        # Verify the properties contrain at least the color (key 0x00).
        # And that the color is the right length.
        sp.verify(sp.len(this_place.place_props.get(sp.bytes("0x00"), message=self.error_message.parameter_error())) == placePropsColorLen,
            message = self.error_message.data_length())

        # Increment place interaction counter.
        this_place.interaction_counter += 1


    def validateItemData(self, item_data):
        """Verify the item data has the right length."""
        sp.verify(sp.len(item_data) >= itemDataMinLen, message = self.error_message.data_length())


    @sp.entry_point(lazify = True)
    def place_items(self, params):
        sp.set_type(params, sp.TRecord(
            chunk_key =  chunkPlaceKeyType,
            place_item_map = sp.TMap(sp.TAddress, sp.TList(extensibleVariantItemType)),
            merkle_proofs = sp.TOption(sp.TMap(sp.TAddress, registry_contract.merkle_tree_collections.MerkleProofType)),
            send_to_place = sp.TBool,
            extension = extensionArgType
        ).layout(("chunk_key", ("place_item_map", ("merkle_proofs", ("send_to_place", "extension"))))))

        self.onlyUnpaused()

        # Place token must be allowed
        place_limits = self.getAllowedPlaceTokenLimits(params.chunk_key.place_key.place_contract)

        sp.verify(params.chunk_key.chunk_id < place_limits.chunk_limit, message = self.error_message.chunk_limit())

        # Caller must have PlaceItems permissions.
        permissions = sp.snd(self.getPermissionsInline(params.chunk_key.place_key, sp.sender))
        sp.verify(permissions & permissionPlaceItems == permissionPlaceItems, message = self.error_message.no_permission())
        # TODO: special permission for sending items to place? Might be good.

        # Get or create the place and chunk.
        this_place = self.place_store_map.get_or_create(self.data.places, params.chunk_key.place_key)
        this_chunk = self.chunk_store_map.get_or_create(self.data.chunks, params.chunk_key, this_place)

        # Count items in place item storage.
        chunk_item_count = sp.local("chunk_item_count", sp.nat(0))
        with sp.for_("issuer_map", this_chunk.stored_items.values()) as issuer_map:
            with sp.for_("token_map", issuer_map.values()) as token_map:
                chunk_item_count.value += sp.len(token_map)

        # Count items to be added.
        add_item_count = sp.local("add_item_count", sp.nat(0))
        with sp.for_("item_list", params.place_item_map.values()) as item_list:
            add_item_count.value += sp.len(item_list)

        # Make sure chunk item limit is not exceeded.
        sp.verify(chunk_item_count.value + add_item_count.value <= place_limits.chunk_item_limit, message = self.error_message.chunk_item_limit())

        # Our token transfer map.
        transferMap = utils.FA2TokenTransferMap()

        registry_info = registry_contract.getTokenRegistryInfo(
            self.data.token_registry,
            params.place_item_map.keys(),
            params.merkle_proofs)

        # If tokens are sent to place, the issuer should be none, otherwise sender.
        issuer = sp.compute(sp.eif(params.send_to_place, sp.none, sp.some(sp.sender)))

        # For each fa2 in the map.
        with sp.for_("fa2_item", params.place_item_map.items()) as fa2_item:
            sp.verify(registry_info.get(fa2_item.key, default_value=False), self.error_message.token_not_registered())

            item_list = fa2_item.value

            # Get or create item storage.
            item_store = self.item_store_map.get_or_create(this_chunk.stored_items, issuer, fa2_item.key)

            transferMap.add_fa2(fa2_item.key)

            # For each item in the list.
            with sp.for_("curr", item_list) as curr:
                with curr.match_cases() as arg:
                    with arg.match("item") as item:
                        self.validateItemData(item.item_data)

                        # TODO:
                        # Token registry should be a separate contract
                        ## Check if FA2 token is permitted and get props.
                        #fa2_props = self.getPermittedFA2Props(fa2)
                        #
                        ## If swapping is not allowed, token_amount MUST be 1 and mutez_per_token MUST be 0.
                        #with sp.if_(~ fa2_props.swap_allowed):
                        #    sp.verify((item.token_amount == sp.nat(1)) & (item.mutez_per_token == sp.tez(0)), message = self.error_message.parameter_error())

                        # Transfer item to this contract.
                        transferMap.add_token(fa2_item.key, sp.self_address, item.token_id, item.token_amount)

                    with arg.match("ext") as ext_data:
                        self.validateItemData(ext_data)

                # Add item to storage.
                item_store[this_chunk.next_id] = curr

                # Increment next_id.
                this_chunk.next_id += 1

        # Transfer the tokens.
        transferMap.transfer_tokens(sp.sender)

        # Don't increment chunk interaction counter, as next_id changes.


    @sp.entry_point(lazify = True)
    def set_item_data(self, params):
        sp.set_type(params, sp.TRecord(
            chunk_key =  chunkPlaceKeyType,
            update_map = sp.TMap(sp.TOption(sp.TAddress), sp.TMap(sp.TAddress, sp.TList(updateItemListType))),
            extension = extensionArgType
        ).layout(("chunk_key", ("update_map", "extension"))))

        self.onlyUnpaused()

        # Place token must be allowed
        self.onlyAllowedPlaceTokens(params.chunk_key.place_key.place_contract)

        # Get the chunk - must exist.
        this_chunk = self.chunk_store_map.get(self.data.chunks, params.chunk_key)

        # Caller must have ModifyAll or ModifyOwn permissions.
        permissions = sp.snd(self.getPermissionsInline(params.chunk_key.place_key, sp.sender))
        hasModifyAll = permissions & permissionModifyAll == permissionModifyAll

        # If ModifyAll permission is not given, make sure update map only contains sender items.
        with sp.if_(~hasModifyAll):
            with sp.for_("remove_key", params.update_map.keys()) as remove_key:
                sp.verify(remove_key == sp.some(sp.sender), message = self.error_message.no_permission())

        # Update items.
        with sp.for_("issuer_item", params.update_map.items()) as issuer_item:
            with sp.for_("fa2_item", issuer_item.value.items()) as fa2_item:
                update_list = fa2_item.value

                # Get item store - must exist.
                item_store = self.item_store_map.get(this_chunk.stored_items, issuer_item.key, fa2_item.key)

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

        # Increment chunk interaction counter, as next_id does not change.
        this_chunk.interaction_counter += 1


    @sp.entry_point(lazify = True)
    def remove_items(self, params):
        sp.set_type(params, sp.TRecord(
            chunk_key =  chunkPlaceKeyType,
            remove_map = sp.TMap(sp.TOption(sp.TAddress), sp.TMap(sp.TAddress, sp.TList(sp.TNat))),
            extension = extensionArgType
        ).layout(("chunk_key", ("remove_map", "extension"))))

        self.onlyUnpaused()

        # TODO: Place token must be allowed?
        #self.onlyAllowedPlaceTokens(params.chunk_key.place_key.place_contract)

        # Get the chunk - must exist.
        this_chunk = self.chunk_store_map.get(self.data.chunks, params.chunk_key)

        # Caller must have ModifyAll or ModifyOwn permissions.
        owner, permissions = sp.match_pair(self.getPermissionsInline(params.chunk_key.place_key, sp.sender))
        hasModifyAll = permissions & permissionModifyAll == permissionModifyAll

        # If ModifyAll permission is not given, make sure remove map only contains sender items.
        with sp.if_(~hasModifyAll):
            with sp.for_("remove_key", params.remove_map.keys()) as remove_key:
                sp.verify(remove_key == sp.some(sp.sender), message = self.error_message.no_permission())

        # Token transfer map.
        transferMap = utils.FA2TokenTransferMap()

        # Remove items.
        with sp.for_("issuer_item", params.remove_map.items()) as issuer_item:
            item_owner = utils.openSomeOrDefault(issuer_item.key, owner)

            with sp.for_("fa2_item", issuer_item.value.items()) as fa2_item:
                item_list = fa2_item.value

                # Get item store - must exist.
                item_store = self.item_store_map.get(this_chunk.stored_items, issuer_item.key, fa2_item.key)

                transferMap.add_fa2(fa2_item.key)
                
                with sp.for_("curr", item_list) as curr:
                    # Nothing to do here with ext items. Just remove them.
                    with item_store[curr].match("item") as the_item:
                        # Transfer items back to issuer/owner
                        transferMap.add_token(
                            fa2_item.key,
                            item_owner,
                            the_item.token_id, the_item.token_amount)

                    # Delete item from storage.
                    del item_store[curr]

                # Remove the item store if empty.
                self.item_store_map.remove_if_empty(this_chunk.stored_items, issuer_item.key, fa2_item.key)

        # Transfer tokens.
        transferMap.transfer_tokens(sp.self_address)

        # Increment chunk interaction counter, as next_id does not change.
        this_chunk.interaction_counter += 1


    def sendValueRoyaltiesFeesInline(self, mutez_per_token, issuer_or_place_owner, item_royalty_info):
        """Inline function for sending royalties, fees, etc."""
        sp.set_type(mutez_per_token, sp.TMutez)
        sp.set_type(issuer_or_place_owner, sp.TAddress)
        sp.set_type(item_royalty_info, registry_contract.t_royalties_interop)

        # Collect amounts to send in a map.
        sendMap = utils.TokenSendMap()

        # Loop over all the shares and record how much to send.
        total_royalties = sp.local("total_royalties", sp.mutez(0))
        with sp.for_("share", item_royalty_info.shares) as share:
            # Calculate amount to be paid from absolute share.
            share_mutez = sp.compute(sp.split_tokens(mutez_per_token, share.share, item_royalty_info.total))
            sendMap.add(share.address, share_mutez)
            total_royalties.value += share_mutez

        # Our fees are in permille.
        fees_amount = sp.compute(sp.split_tokens(mutez_per_token, self.data.fees, sp.nat(1000)))
        sendMap.add(self.data.fees_to, fees_amount)

        # Send rest of the value to seller.
        left_amount = mutez_per_token - fees_amount - total_royalties.value
        sendMap.add(issuer_or_place_owner, left_amount)

        # Transfer.
        sendMap.transfer()


    def issuerOrPlaceOwnerInline(self, place_key, issuer):
        """Inline function for getting the owner of an item (either issuer or place owner)."""
        sp.set_type(place_key, placeKeyType)
        sp.set_type(issuer, sp.TOption(sp.TAddress))

        # the item owner is either the issuer (when set), or the place owner.
        return utils.openSomeOrDefault(issuer, FA2.fa2_nft_get_owner(place_key.place_contract, place_key.lot_id))


    @sp.entry_point(lazify = True)
    def get_item(self, params):
        sp.set_type(params, sp.TRecord(
            chunk_key =  chunkPlaceKeyType,
            item_id = sp.TNat,
            issuer = sp.TOption(sp.TAddress),
            fa2 = sp.TAddress,
            merkle_proof_royalties = sp.TOption(registry_contract.merkle_tree_royalties.MerkleProofType),
            extension = extensionArgType
        ).layout(("chunk_key", ("item_id", ("issuer", ("fa2", ("merkle_proof_royalties", "extension")))))))

        self.onlyUnpaused()

        # TODO: Place token must be allowed?
        #self.onlyAllowedPlaceTokens(params.chunk_key.place_key.place_contract)

        # If the issuer is none, the owner is the place owner.
        # That makes sure the tez are sent to the rightful owner (i.e., the place owner if issuer is none).
        item_owner = self.issuerOrPlaceOwnerInline(params.chunk_key.place_key, params.issuer)

        # Get the chunk - must exist.
        this_chunk = self.chunk_store_map.get(self.data.chunks, params.chunk_key)

        # Get item store - must exist.
        item_store = self.item_store_map.get(this_chunk.stored_items, params.issuer, params.fa2)

        # Swap based on item type.
        with item_store[params.item_id].match_cases() as arg:
            # For tz1and native items.
            with arg.match("item") as immutable:
                # This is silly but required because match args are not mutable.
                the_item = sp.local("the_item", immutable)

                # Make sure it's for sale, and the transfered amount is correct.
                sp.verify(the_item.value.mutez_per_token > sp.mutez(0), message = self.error_message.not_for_sale())
                sp.verify(the_item.value.mutez_per_token == sp.amount, message = self.error_message.wrong_amount())

                # Transfer royalties, etc.
                with sp.if_(sp.amount != sp.mutez(0)):
                    # Get the royalties for this item
                    # TODO: royalties for non-tz1and items? maybe token registry could handle that to some extent?
                    # at least in terms of what "type" of royalties.
                    item_royalty_info = registry_contract.getTokenRoyalties(
                        self.data.token_registry,
                        params.fa2, the_item.value.token_id,
                        params.merkle_proof_royalties)

                    # Send fees, royalties, value.
                    self.sendValueRoyaltiesFeesInline(sp.amount, item_owner, item_royalty_info)
                
                # Transfer item to buyer.
                utils.fa2_transfer(params.fa2, sp.self_address, sp.sender, the_item.value.token_id, 1)
                
                # Reduce the item count in storage or remove it.
                with sp.if_(the_item.value.token_amount > 1):
                    the_item.value.token_amount = abs(the_item.value.token_amount - 1)
                    item_store[params.item_id] = sp.variant("item", the_item.value)
                with sp.else_():
                    del item_store[params.item_id]

            # ext items are unswappable.
            with arg.match("ext"):
                sp.failwith(self.error_message.wrong_item_type())
        
        # Remove the item store if empty.
        self.item_store_map.remove_if_empty(this_chunk.stored_items, params.issuer, params.fa2)

        # Increment chunk interaction counter, as next_id does not change.
        this_chunk.interaction_counter += 1


    #
    # Migration
    #
    # TODO: Permissions?
    @sp.entry_point(lazify = True)
    def migration(self, params):
        """An entrypoint to recieve/send migrations.
        
        Initially set up to recieve migrations but can
        be upgraded to send migrations."""
        sp.set_type(params, migrationType)

        # Only allow recieving migrations from a certain contract,
        # and also only from admin as source.
        sp.verify((sp.some(sp.sender) == self.data.migration_contract) &
            (sp.source == self.data.administrator))

        # Place token must be allowed
        place_limits = self.getAllowedPlaceTokenLimits(params.place_key.place_contract)

        # Caller doesn't need permissions, is admin.

        # Get or create the place.
        this_place = self.place_store_map.get_or_create(self.data.places, params.place_key)
        # Make sure the place is empty.
        sp.verify(sp.len(this_place.chunks) == 0, message = "MIGRATION_PLACE_NOT_EMPTY")

        # Set the props on the place to migrate
        this_place.place_props = params.migrate_place_props
        this_place.interaction_counter += sp.nat(1)

        # If the migration map isn't empty
        with sp.if_(sp.len(params.migrate_item_map) > 0):
            # Keep a running count of items, so we can switch chunks.
            add_item_count = sp.local("add_item_count", sp.nat(0))
            # The current chunk we're working on.
            current_chunk = sp.local("current_chunk", sp.nat(0))

            # Get or create the current chunk.
            this_chunk = self.chunk_store_map.get_or_create(self.data.chunks, sp.record(place_key = params.place_key, chunk_id = current_chunk.value), this_place)

            # Our token transfer map.
            # Since all transfers come from migration_contract, we can have single map.
            transferMap = utils.FA2TokenTransferMap()

            # For each fa2 in the map.
            with sp.for_("issuer_item", params.migrate_item_map.items()) as issuer_item:
                registry_info = registry_contract.getTokenRegistryInfo(
                    self.data.token_registry,
                    issuer_item.value.keys(),
                    check_merkle_proofs=False)

                with sp.for_("fa2_item", issuer_item.value.items()) as fa2_item:
                    sp.verify(registry_info.get(fa2_item.key, default_value=False), self.error_message.token_not_registered())

                    transferMap.add_fa2(fa2_item.key)

                    item_list = fa2_item.value

                    # Get or create item storage.
                    item_store = self.item_store_map.get_or_create(this_chunk.stored_items, sp.some(issuer_item.key), fa2_item.key)

                    # For each item in the list.
                    with sp.for_("curr", item_list) as curr:
                        # if we added more items than the chunk limit, switch chunks and reset add count to 0
                        with sp.if_(add_item_count.value >= place_limits.chunk_item_limit):
                            # Remove itemstore if empty. Can happen in some cases,
                            # because the item store is created at the beginning of a token loop.
                            # Alternatively we could call item_store_map.get_or_create() inside the loop.
                            self.item_store_map.remove_if_empty(this_chunk.stored_items, sp.some(issuer_item.key), fa2_item.key)

                            # Reset counters and increment current chunk.
                            add_item_count.value = sp.nat(0)
                            current_chunk.value += sp.nat(1)
                            sp.verify(current_chunk.value < place_limits.chunk_limit, message = self.error_message.chunk_limit())

                            # update chunk and item storage
                            this_chunk = self.chunk_store_map.get_or_create(self.data.chunks, sp.record(place_key = params.place_key, chunk_id = current_chunk.value), this_place)
                            item_store = self.item_store_map.get_or_create(this_chunk.stored_items, sp.some(issuer_item.key), fa2_item.key)

                        with curr.match_cases() as arg:
                            with arg.match("item") as item:
                                self.validateItemData(item.item_data)

                                # transfer item to this contract
                                # do multi-transfer by building up a list of transfers
                                transferMap.add_token(fa2_item.key, sp.self_address, item.token_id, item.token_amount)

                            with arg.match("ext") as ext_data:
                                self.validateItemData(ext_data)

                        # Add item to storage.
                        item_store[this_chunk.next_id] = curr

                        # Increment next_id.
                        this_chunk.next_id += sp.nat(1)

                        # Add to item add counter
                        add_item_count.value += sp.nat(1)

            # Transfer if list has items.
            transferMap.transfer_tokens(sp.sender)

            # Don't increment chunk interaction counter, as chunks must be new.


    #
    # Views
    #
    @sp.onchain_view(pure=True)
    def get_place_data(self, params):
        sp.set_type(params, placeDataParam)
        with sp.set_result_type(placeDataResultType):
            res = sp.local("res", sp.record(
                place = self.data.places.get(params.place_key, placeStorageDefault),
                chunks = {}))

            with sp.for_("chunk_id", params.chunk_ids.elements()) as chunk_id:
                res.value.chunks[chunk_id ] = self.data.chunks.get(sp.record(
                    place_key = params.place_key,
                    chunk_id = chunk_id
                ), chunkStorageDefault)

            sp.result(res.value)


    @sp.onchain_view(pure=True)
    def get_place_seqnum(self, place_key):
        sp.set_type(place_key, placeKeyType)

        with sp.set_result_type(seqNumResultType):
            # Collect chunk sequence numbers.
            this_place = self.data.places.get(place_key, placeStorageDefault)
            chunk_sequence_numbers_map = sp.local("chunk_sequence_numbers_map", {}, sp.TMap(sp.TNat, sp.TBytes))
            with sp.for_("chunk_id", this_place.chunks.elements()) as chunk_id:
                this_chunk = self.data.chunks.get(sp.record(place_key = place_key, chunk_id = chunk_id), chunkStorageDefault)
                chunk_sequence_numbers_map.value[chunk_id] = sp.sha3(sp.pack(sp.pair(
                    this_chunk.interaction_counter,
                    this_chunk.next_id)))

            # Return the result.
            sp.result(sp.record(
                place_seq_num = sp.sha3(sp.pack(this_place.interaction_counter)),
                chunk_seq_nums = chunk_sequence_numbers_map.value))


    @sp.onchain_view(pure=True)
    def get_permissions(self, query):
        sp.set_type(query, sp.TRecord(
            place_key = placeKeyType,
            permittee = sp.TAddress
        ).layout(("place_key", "permittee")))
        with sp.set_result_type(sp.TNat):
            sp.result(sp.snd(self.getPermissionsInline(query.place_key, query.permittee)))
