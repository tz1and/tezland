# The World contract.
#
# Each lot belongs to a Place (an FA2 token that is the "land").
# Items (another type of token) can be stored on your Place, either to swap
# or just to build something nice.

import smartpy as sp

pause_mixin = sp.io.import_script_from_url("file:contracts/Pausable.py")
fees_mixin = sp.io.import_script_from_url("file:contracts/Fees.py")
mod_mixin = sp.io.import_script_from_url("file:contracts/Moderation_v2.py")
allowed_place_tokens = sp.io.import_script_from_url("file:contracts/AllowedPlaceTokens.py")
upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
contract_metadata_mixin = sp.io.import_script_from_url("file:contracts/ContractMetadata.py")
registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
legacy_royalties_contract = sp.io.import_script_from_url("file:contracts/TL_LegacyRoyalties.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")
FA2_legacy = sp.io.import_script_from_url("file:contracts/legacy/FA2_legacy.py")

# Now:
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
# TODO: so many empty FAILWITHs. Optimise... What still can be.
# TODO: special permission for sending items to place? Might be good.
# TODO: add tests issuerOrValueToOrPlaceOwnerInline, etc. to make sure they work correctly in all combinations.
# TODO: re-distributing places. added get_owner view
# TODO: optional value_to/send_to address on the place. can be used to split/for other contracts managing places, etc.
# TODO: if a place is on auction and someone buys an item owned by the place, the tez would be sent to the auction contract.
#       I could change the auction contract so it does the "ask" thing instead - where you make a swap but only set operators instead of actually transferring the nft.
#       but it could lead to people just spamming auctions for the same place or revoking operators and having a bunch of dead auctions
#       I think you can make contract deny tez sent to it. I could just do that for the auction contract. which means you're not able to buy place owned items from a place on auction (since it actually doesn't have an owner)
#       Can also have a global optional "send to" address in the place that can be set by the auction contract.
# TODO: make sure royalties version is set correctly everywhere.
# TODO: test set_props value_to
# TODO: test value_to place setting.
# TODO: test placing/updating/removing items in multiple chunks.
# TODO: add views option to mixins to allow not including views.
# TODO: test searching through chunks to find space when placing items. (see migration code). with lots of chunks. if it's worth the gas, maybe consider it.
# TODO: don't deploy factory in upgrade, this feature comes later.
# TODO: add flags and other state to deploy registry (if a certain step has been executed, etc)
# TODO: re-consider sequence number hashing. do they need to be hashed? since they are only checked for inequality, that can be done by pack() and compare.
# TODO: allow updating more than just data? (data, rate, primary) | (data) for items and ext respectively.
# TODO: reverse issuer and fa2 storage? this came up before... it shouldn't make a difference. registry.is_registered could be list. and maybe some other things.
# TODO: if the is_registered view failed on non-registered tokens, we wouldn't waste gas.



# maybe?
# TODO: add a limit on place props data len and item data len. Potential gaslock.

# Other
# TODO: think of some more tests for permission.
# TODO: DAO token drop with merkle tree based on: https://github.com/AnshuJalan/token-drop-template
#       + Add a pause function and an expiration date for the drop.
#       + https://github.com/teia-community/teia-smart-contracts/blob/main/python/contracts/daoTokenDrop.py
# TODO: sorting out the splitting of dao and team (probably with a proxy contract)
# TODO: proxy contract will also be some kind of multisig for all the only-admin things (pausing operation)
# TODO: research storage deserialisation limits
# TODO: investgate using a "metadata map" for item data.
# TODO: check if packing/unpacking michelson maps works well for script variables


# Some notes:
# - use abs instead sp.as_nat if unchecked. as_nat will throw on negative numbers, abs won't - but make smaller code.
# - every upgradeable_mixin entrypoint has an arg of extensionArgType. Can be used for merkle proof royalties, for example.
# - Item data is stored in half floats, usually, there are two formats as of now
#   + 0: 1 byte format, 3 floats pos = 7 bytes (this is also the minimum item data length)
#   + 1: 1 byte format, 3 floats for euler angles, 3 floats pos, 1 float scale = 15 bytes
#   NOTE: could store an animation index and all kinds of other stuff in data
# - Regarding chunk item storage efficiency: you can easily have up to 2000-3000 items (depending on issuer and token keys)
#   per map before gas becomes *expensive*.
# - use of inline_result. and bound blocks in general. can help with gas.
# - why switching to sigend royalties has such a large impact on perf:
#   + So I just wasted a day trying to figure out why having a public key in a contract's storage adds 30 mutez of gas
#   + And it's linear with the number of keys. I guess it does some cryptography even if the key is not used. Would be nice if that was deferred to when/if the key is actually used. (edited)
#   + I still don't really know what's going on but I'm also somewhat unwilling to read the tezos node code.
#   + So yeh - placing items and collecting them is now both 60 mutez more expensive, even if the key is unused.
#   + which is not much but it sure was curious enough to look into it.
#   + Interestingly, putting the keys into a bigmap did not help. At least not with only two keys.
#   + Ended up being closer to 90 mutez. I guess (hope) bigmap read + key init > 2 * key init.
#   + If you have more than two or three public keys in your contract, consider putting them in a bigmap.

# Optional ext argument type.
# Map val can contain about anything and be
# unpacked with sp.unpack.
extensionArgType = sp.TOption(sp.TMap(sp.TString, sp.TBytes))

#
# Item types
# For tz1and Item tokens.
itemRecordType = sp.TRecord(
    token_id = sp.TNat, # the fa2 token id
    amount = sp.TNat, # number of fa2 tokens to store.
    rate = sp.TMutez, # 0 if not for sale.
    data = sp.TBytes, # transforms, etc
    primary = sp.TBool, # split the entire value according to royalties.
).layout(("token_id", ("amount", ("rate", ("data", "primary")))))

# NOTE: reccords in variants are immutable?
# See: https://gitlab.com/SmartPy/smartpy/-/issues/32
extensibleVariantItemType = sp.TVariant(
    item = itemRecordType,
    ext = sp.TBytes # transforms, etc
).layout(("item", "ext"))

#
# Item storage
# map from item id to item
tokenStoreType = sp.TMap(sp.TNat, extensibleVariantItemType)
tokenStoreLiteral = sp.map(tkey=sp.TNat, tvalue=extensibleVariantItemType)
# map from token address to item
issuerStoreType = sp.TMap(sp.TAddress, tokenStoreType)
issuerStoreLiteral = sp.map(tkey=sp.TAddress, tvalue=tokenStoreType)
# map from issuer to item store
chunkStoreType = sp.TMap(sp.TOption(sp.TAddress), issuerStoreType)
chunkStoreLiteral = sp.map(tkey=sp.TOption(sp.TAddress), tvalue=issuerStoreType)

#
# Place prop storage
placePropsType = sp.TMap(sp.TBytes, sp.TBytes)
# only set color by default.
defaultPlaceProps = sp.map({sp.bytes("0x00"): sp.bytes('0x82b881')}, tkey=sp.TBytes, tvalue=sp.TBytes)

placeStorageType = sp.TRecord(
    counter = sp.TNat, # interaction counter for seq number generation
    props = placePropsType, # place properties
    chunks = sp.TSet(sp.TNat), # set of active/existing chunks
    value_to = sp.TOption(sp.TAddress) # value for place owned items is sent to, if set
).layout(("counter", ("props", ("chunks", "value_to"))))

placeStorageDefault = sp.record(
    counter = sp.nat(0),
    props = defaultPlaceProps,
    chunks = sp.set([]),
    value_to = sp.none)

placeKeyType = sp.TRecord(
    fa2 = sp.TAddress, # TODO: rename? shorten?
    id = sp.TNat
).layout(("fa2", "id"))

placeMapType = sp.TBigMap(placeKeyType, placeStorageType)
placeMapLiteral = sp.big_map(tkey=placeKeyType, tvalue=placeStorageType)


class PlaceStorage:
    @staticmethod
    def make():
        return placeMapLiteral

    def __init__(self, map: placeMapType, key: placeKeyType, create: bool = False) -> None:
        sp.set_type(map, placeMapType)
        sp.set_type(key, placeKeyType)
        self.data_map = map
        self.this_place_key = key
        if create is True:
            self.this_place = sp.local("this_place", self.__get_or_default())
        else:
            self.this_place = sp.local("this_place", self.__get())

    def __get(self):
        return self.data_map.get(self.this_place_key)

    def __get_or_default(self):
        return self.data_map.get(self.this_place_key, placeStorageDefault)

    def persist(self):
        self.data_map[self.this_place_key] = self.this_place.value

    def load(self, new_key: placeKeyType, create: bool = False):
        self.this_place_key = new_key
        if create is True:
            self.this_place.value = self.__get_or_default()
        else:
            self.this_place.value = self.__get()

    @property
    def value(self):
        return self.this_place.value

#
# Chunk storage
chunkStorageType = sp.TRecord(
    next_id = sp.TNat, # per chunk item ids
    counter = sp.TNat, # interaction counter for seq number generation
    storage = chunkStoreType
).layout(("next_id", ("counter", "storage")))

chunkStorageDefault = sp.record(
    next_id = sp.nat(0),
    counter = sp.nat(0),
    storage = chunkStoreLiteral)

chunkPlaceKeyType = sp.TRecord(
    place_key = placeKeyType,
    chunk_id = sp.TNat
).layout(("place_key", "chunk_id"))

placeDataParam = sp.TRecord(
    place_key = placeKeyType,
    chunk_ids = sp.TOption(sp.TSet(sp.TNat))
).layout(("place_key", "chunk_ids"))

placeDataResultType = sp.TRecord(
    place = placeStorageType,
    chunks = sp.TMap(sp.TNat, chunkStorageType)
).layout(("place", "chunks"))

chunkMapType = sp.TBigMap(chunkPlaceKeyType, chunkStorageType)
chunkMapLiteral = sp.big_map(tkey=chunkPlaceKeyType, tvalue=chunkStorageType)


class ChunkStorage:
    @staticmethod
    def make():
        return chunkMapLiteral

    def __init__(self, map: chunkMapType, key: chunkPlaceKeyType, create: bool = False) -> None:
        sp.set_type(map, chunkMapType)
        sp.set_type(key, chunkPlaceKeyType)
        self.data_map = map
        self.this_chunk_key = key
        if create is True:
            self.this_chunk = sp.local("this_chunk", self.__get_or_default())
        else:
            self.this_chunk = sp.local("this_chunk", self.__get())

    def __get(self):
        return self.data_map.get(self.this_chunk_key)

    def __get_or_default(self):
        return self.data_map.get(self.this_chunk_key, chunkStorageDefault)

    def persist(self, place: PlaceStorage = None):
        if place is not None:
            place.value.chunks.add(self.this_chunk_key.chunk_id)
        self.data_map[self.this_chunk_key] = self.this_chunk.value

    #def persist_or_remove(self, place: PlaceStorage = None):
    #    with sp.if_(sp.len(self.this_chunk.value.storage) == 0):
    #        if place is not None:
    #            place.value.chunks.remove(self.this_chunk_key.chunk_id)
    #        del self.data_map[self.this_chunk_key]
    #    with sp.else_():
    #        if place is not None:
    #            place.value.chunks.add(self.this_chunk_key.chunk_id)
    #        self.data_map[self.this_chunk_key] = self.this_chunk.value

    def load(self, new_key: chunkPlaceKeyType, create: bool = False):
        self.this_chunk_key = new_key
        if create is True:
            self.this_chunk.value = self.__get_or_default()
        else:
            self.this_chunk.value = self.__get()

    def count_items(self):
        chunk_item_count = sp.local("chunk_item_count", sp.nat(0))
        with sp.for_("issuer_map", self.this_chunk.value.storage.values()) as issuer_map:
            with sp.for_("token_map", issuer_map.values()) as token_map:
                chunk_item_count.value += sp.len(token_map)
        return chunk_item_count.value

    # TODO: persist_or_remove

    @property
    def value(self):
        return self.this_chunk.value


#
# Item storage
# TODO: this kind of breaks ext type items... could maybe store them with a special contract address????
# +++++ or maybe store ext type items in a special map???? or maybe it just doesn't matter under what token they are stored?
# +++++ or maybe the issuer map could be a record(ext_items_map, tokens_map)
class ItemStorage:
    @staticmethod
    def make():
        return issuerStoreLiteral

    def __init__(self, chunk_storage: ChunkStorage, issuer: sp.TOption(sp.TAddress), fa2: sp.TAddress, create: bool = False) -> None:
        sp.set_type(issuer, sp.TOption(sp.TAddress))
        sp.set_type(fa2, sp.TAddress)
        self.chunk_storage = chunk_storage
        self.issuer = issuer
        self.fa2 = fa2
        if create is True:
            self.this_issuer_store = sp.local("this_issuer_store", self.__get_or_default_issuer())
            self.this_fa2_store = sp.local("this_fa2_store", self.__get_or_default_fa2())
        else:
            self.this_issuer_store = sp.local("this_issuer_store", self.__get_issuer())
            self.this_fa2_store = sp.local("this_fa2_store", self.__get_fa2())

    def __get_issuer(self):
        return self.chunk_storage.value.storage.get(self.issuer)

    def __get_or_default_issuer(self):
        return self.chunk_storage.value.storage.get(self.issuer, issuerStoreLiteral)

    def __get_fa2(self):
        return self.this_issuer_store.value.get(self.fa2)

    def __get_or_default_fa2(self):
        return self.this_issuer_store.value.get(self.fa2, tokenStoreLiteral)

    def persist(self):
        self.this_issuer_store.value[self.fa2] = self.this_fa2_store.value
        self.chunk_storage.value.storage[self.issuer] = self.this_issuer_store.value

    def persist_or_remove(self):
        with sp.if_(sp.len(self.this_fa2_store.value) == 0):
            del self.this_issuer_store.value[self.fa2]
        with sp.else_():
            self.this_issuer_store.value[self.fa2] = self.this_fa2_store.value

        with sp.if_(sp.len(self.this_issuer_store.value) == 0):
            del self.chunk_storage.value.storage[self.issuer]
        with sp.else_():
            self.chunk_storage.value.storage[self.issuer] = self.this_issuer_store.value

    def load(self, new_issuer: sp.TOption(sp.TAddress), new_fa2: sp.TAddress, create: bool = False):
        self.issuer = new_issuer
        self.fa2 = new_fa2
        if create is True:
            self.this_issuer_store.value = self.__get_or_default_issuer()
            self.this_fa2_store.value = self.__get_or_default_fa2()
        else:
            self.this_issuer_store.value = self.__get_issuer()
            self.this_fa2_store.value = self.__get_fa2()

    @property
    def value(self):
        # NOTE: always returns FA2 store.
        return self.this_fa2_store.value

setPlacePropsVariantType = sp.TVariant(
    add_props = placePropsType,
    del_props = sp.TList(sp.TBytes),
    value_to = sp.TOption(sp.TAddress)
).layout(("add_props", ("del_props", "value_to")))

updateItemListType = sp.TRecord(
    item_id = sp.TNat,
    data = sp.TBytes
).layout(("item_id", "data"))

seqNumResultType = sp.TRecord(
    place_seq = sp.TBytes,
    chunk_seqs = sp.TMap(sp.TNat, sp.TBytes)
).layout(("place_seq", "chunk_seqs"))

# Types for the migration ep.
migrationItemMapType = sp.TMap(sp.TAddress, sp.TMap(sp.TAddress, sp.TList(extensibleVariantItemType)))

migrationType = sp.TRecord(
    place_key = placeKeyType,
    # For migration from v1 we basically need the same data as a chunk but with a list as the leaf.
    item_map = migrationItemMapType,
    props = placePropsType,
    ext = extensionArgType
).layout(("place_key", ("item_map", ("props", "ext"))))

# Types for place, get, update, remove entry points.
setPlacePropsType = sp.TRecord(
    place_key = placeKeyType,
    updates = sp.TList(setPlacePropsVariantType),
    ext = extensionArgType
).layout(("place_key", ("updates", "ext")))

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
class PermissionParams:
    @classmethod
    def get_add_type(cls):
        t = sp.TRecord(
            owner = sp.TAddress,
            permittee = sp.TAddress,
            place_key = placeKeyType,
            perm = sp.TNat).layout(("owner", ("permittee", ("place_key", "perm"))))
        return t

    @classmethod
    def make_add(cls, owner, permittee, place_key, perm):
        r = sp.record(owner = owner,
            permittee = permittee,
            place_key = place_key,
            perm = perm)
        return sp.set_type_expr(r, cls.get_add_type())

    @classmethod
    def get_remove_type(cls):
        t = sp.TRecord(
            owner = sp.TAddress,
            permittee = sp.TAddress,
            place_key = placeKeyType).layout(("owner", ("permittee", "place_key")))
        return t

    @classmethod
    def make_remove(cls, owner, permittee, place_key):
        r = sp.record(owner = owner,
            permittee = permittee,
            place_key = place_key)
        return sp.set_type_expr(r, cls.get_remove_type())


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
    def __init__(self, administrator, registry, legacy_royalties, paused, items_tokens, metadata,
        name, description, exception_optimization_level="default-line"):

        # Needed for migration ep but not really needed otherwise.
        self.items_tokens = sp.set_type_expr(items_tokens, sp.TAddress)

        self.add_flag("exceptions", exception_optimization_level)
        #self.add_flag("erase-comments")
        # Not a win at all in terms of gas, especially on the simpler eps.
        #self.add_flag("lazy-entry-points")
        # No noticeable effect on gas.
        #self.add_flag("initial-cast")
        # Makes much smaller code but removes annots from eps.
        #self.add_flag("simplify-via-michel")

        registry = sp.set_type_expr(registry, sp.TAddress)
        legacy_royalties = sp.set_type_expr(legacy_royalties, sp.TAddress)

        self.error_message = Error_message()
        self.permission_map = Permission_map()

        self.init_storage(
            registry = registry,
            legacy_royalties = legacy_royalties,
            migration_from = sp.none,
            max_permission = permissionFull, # must be (power of 2)-1
            permissions = self.permission_map.make(),
            places = PlaceStorage.make(),
            chunks = ChunkStorage.make()
        )

        self.available_settings = [
            ("registry", sp.TAddress, None),
            ("legacy_royalties", sp.TAddress, None),
            ("migration_from", sp.TOption(sp.TAddress), None),
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
            add = PermissionParams.get_add_type(),
            remove = PermissionParams.get_remove_type()
        ).layout(("add", "remove"))))

        #self.onlyUnpaused() # Probably fine to run when paused.

        with sp.for_("update", params) as update:
            with update.match_cases() as arg:
                with arg.match("add") as upd:
                    # can only add permissions for allowed places
                    self.onlyAllowedPlaceTokens(upd.place_key.fa2)
                    # Sender must be the owner
                    sp.verify(upd.owner == sp.sender, message = self.error_message.not_owner())
                    sp.verify((upd.perm > permissionNone) & (upd.perm <= self.data.max_permission), message = self.error_message.parameter_error())
                    # Add permission
                    self.permission_map.add(self.data.permissions,
                        upd.owner,
                        upd.permittee,
                        upd.place_key,
                        upd.perm)
                with arg.match("remove") as upd:
                    # NOTE: don't need to check if place key is valid
                    #self.onlyAllowedPlaceTokens(upd.place_key.fa2)
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

        place_owner = sp.local("place_owner", FA2.fa2_nft_get_owner(place_key.fa2, place_key.id))

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
        sp.set_type(params, setPlacePropsType)

        self.onlyUnpaused()

        # Place token must be allowed
        self.onlyAllowedPlaceTokens(params.place_key.fa2)

        # Caller must have Full permissions.
        permissions = sp.snd(self.getPermissionsInline(params.place_key, sp.sender))
        sp.verify(permissions & permissionProps == permissionProps, message = self.error_message.no_permission())

        # Get or create the place.
        this_place = PlaceStorage(self.data.places, params.place_key, True)

        with sp.for_("item", params.updates) as item:
            with item.match_cases() as arg:
                with arg.match("add_props") as add_props:
                    with sp.for_("prop", add_props.items()) as prop:
                        this_place.value.props[prop.key] = prop.value

                with arg.match("del_props") as del_props:
                    with sp.for_("prop", del_props) as prop:
                        del this_place.value.props[prop]

                with arg.match("value_to") as value_to:
                    this_place.value.value_to = value_to

        # Verify the properties contrain at least the color (key 0x00).
        # And that the color is the right length.
        sp.verify(sp.len(this_place.value.props.get(sp.bytes("0x00"), message=self.error_message.parameter_error())) == placePropsColorLen,
            message = self.error_message.data_length())

        # Increment place interaction counter.
        this_place.value.counter += 1

        # Persist place.
        this_place.persist()


    def validateItemData(self, data):
        """Verify the item data has the right length."""
        sp.verify(sp.len(data) >= itemDataMinLen, message = self.error_message.data_length())


    @sp.entry_point(lazify = True)
    def place_items(self, params):
        sp.set_type(params, sp.TRecord(
            place_key = placeKeyType,
            place_item_map = sp.TMap(sp.TNat, sp.TMap(sp.TBool, sp.TMap(sp.TAddress, sp.TList(extensibleVariantItemType)))),
            ext = extensionArgType
        ).layout(("place_key", ("place_item_map", "ext"))))

        self.onlyUnpaused()

        # Place token must be allowed
        place_limits = self.getAllowedPlaceTokenLimits(params.place_key.fa2)

        # Caller must have PlaceItems permissions.
        permissions = sp.snd(self.getPermissionsInline(params.place_key, sp.sender))
        sp.verify(permissions & permissionPlaceItems == permissionPlaceItems, message = self.error_message.no_permission())
        # TODO: special permission for sending items to place? Might be good.

        # Count items to be added, get FA2 set and check id limits.
        chunk_add_item_count = sp.local("chunk_add_item_count", sp.map(tkey=sp.TNat, tvalue=sp.TNat))
        fa2_set = sp.local("fa2_set", sp.set(t=sp.TAddress))
        with sp.for_("chunk_item", params.place_item_map.items()) as chunk_item:
            sp.verify(chunk_item.key < place_limits.chunk_limit, message = self.error_message.chunk_limit())

            add_item_count = sp.local("add_item_count", sp.nat(0))
            with sp.for_("fa2_map", chunk_item.value.values()) as fa2_map:
                with sp.for_("fa2_item", fa2_map.items()) as fa2_item:
                    fa2_set.value.add(fa2_item.key)
                    add_item_count.value += sp.len(fa2_item.value)

            chunk_add_item_count.value[chunk_item.key] = add_item_count.value

        # Get or create the place and chunk.
        this_place = PlaceStorage(self.data.places, params.place_key, True)

        # Our token transfer map.
        transferMap = utils.FA2TokenTransferMap()

        # Get registry info for FA2s.
        registry_contract.checkRegistered(
            self.data.registry,
            fa2_set.value)

        with sp.for_("chunk_item", params.place_item_map.items()) as chunk_item:
            chunk_key = sp.compute(sp.record(place_key = params.place_key, chunk_id = chunk_item.key))

            this_chunk = ChunkStorage(self.data.chunks, chunk_key, True)

            # Count items in place item storage.
            chunk_item_count = this_chunk.count_items()

            # Make sure chunk item limit is not exceeded.
            sp.verify(chunk_item_count + chunk_add_item_count.value.get(chunk_item.key, sp.nat(0)) <= place_limits.chunk_item_limit, message = self.error_message.chunk_item_limit())

            # For each fa2 in the map.
            with sp.for_("send_to_place_item", chunk_item.value.items()) as send_to_place_item:
                # If tokens are sent to place, the issuer should be none, otherwise sender.
                issuer = sp.compute(sp.eif(send_to_place_item.key, sp.none, sp.some(sp.sender)))

                with sp.for_("fa2_item", send_to_place_item.value.items()) as fa2_item:
                    # Get or create item storage.
                    item_store = ItemStorage(this_chunk, issuer, fa2_item.key, True)

                    transferMap.add_fa2(fa2_item.key)

                    # For each item in the list.
                    with sp.for_("curr", fa2_item.value) as curr:
                        with curr.match_cases() as arg:
                            with arg.match("item") as item:
                                self.validateItemData(item.data)

                                # TODO:
                                # Token registry should be a separate contract
                                ## Check if FA2 token is permitted and get props.
                                #fa2_props = self.getPermittedFA2Props(fa2)
                                #
                                ## If swapping is not allowed, amount MUST be 1 and rate MUST be 0.
                                #with sp.if_(~ fa2_props.swap_allowed):
                                #    sp.verify((item.amount == sp.nat(1)) & (item.rate == sp.tez(0)), message = self.error_message.parameter_error())

                                # Transfer item to this contract.
                                transferMap.add_token(fa2_item.key, sp.self_address, item.token_id, item.amount)

                            with arg.match("ext") as ext_data:
                                self.validateItemData(ext_data)

                        # Add item to storage.
                        item_store.value[this_chunk.value.next_id] = curr

                        # Increment next_id.
                        this_chunk.value.next_id += 1

                    # Persist item storage.
                    item_store.persist()

            # Don't increment chunk interaction counter, as next_id changes.

            # Persist chunk.
            this_chunk.persist(this_place)
        
        # Persist place.
        this_place.persist()

        # Transfer the tokens.
        transferMap.transfer_tokens(sp.sender)


    @sp.entry_point(lazify = True)
    def set_item_data(self, params):
        sp.set_type(params, sp.TRecord(
            place_key = placeKeyType,
            update_map = sp.TMap(sp.TNat, sp.TMap(sp.TOption(sp.TAddress), sp.TMap(sp.TAddress, sp.TList(updateItemListType)))),
            ext = extensionArgType
        ).layout(("place_key", ("update_map", "ext"))))

        self.onlyUnpaused()

        # TODO: Place token must be allowed?
        #self.onlyAllowedPlaceTokens(params.place_key.fa2)

        # Caller must have ModifyAll or ModifyOwn permissions.
        permissions = sp.snd(self.getPermissionsInline(params.place_key, sp.sender))
        hasModifyAll = permissions & permissionModifyAll == permissionModifyAll

        # If ModifyAll permission is not given, make sure update map only contains sender items.
        with sp.if_(~hasModifyAll):
            with sp.for_("issuer_map", params.update_map.values()) as issuer_map:
                with sp.for_("remove_key", issuer_map.keys()) as remove_key:
                    sp.verify(remove_key == sp.some(sp.sender), message = self.error_message.no_permission())

        # Update items.
        with sp.for_("chunk_item", params.update_map.items()) as chunk_item:
            chunk_key = sp.compute(sp.record(place_key = params.place_key, chunk_id = chunk_item.key))

            # Get the chunk - must exist.
            this_chunk = ChunkStorage(self.data.chunks, chunk_key)

            with sp.for_("issuer_item", chunk_item.value.items()) as issuer_item:
                with sp.for_("fa2_item", issuer_item.value.items()) as fa2_item:
                    # Get item store - must exist.
                    item_store = ItemStorage(this_chunk, issuer_item.key, fa2_item.key)

                    with sp.for_("update", fa2_item.value) as update:
                        self.validateItemData(update.data)

                        with item_store.value[update.item_id].match_cases() as arg:
                            with arg.match("item") as immutable:
                                # sigh - variants are not mutable
                                item_var = sp.compute(immutable)
                                item_var.data = update.data
                                item_store.value[update.item_id] = sp.variant("item", item_var)
                            with arg.match("ext"):
                                item_store.value[update.item_id] = sp.variant("ext", update.data)

                    # Persist item storage.
                    item_store.persist()

            # Increment chunk interaction counter, as next_id does not change.
            this_chunk.value.counter += 1

            # Persist chunk
            this_chunk.persist()


    @sp.entry_point(lazify = True)
    def remove_items(self, params):
        sp.set_type(params, sp.TRecord(
            place_key = placeKeyType,
            remove_map = sp.TMap(sp.TNat, sp.TMap(sp.TOption(sp.TAddress), sp.TMap(sp.TAddress, sp.TSet(sp.TNat)))),
            ext = extensionArgType
        ).layout(("place_key", ("remove_map", "ext"))))

        self.onlyUnpaused()

        # TODO: Place token must be allowed?
        #self.onlyAllowedPlaceTokens(params.place_key.fa2)

        # Caller must have ModifyAll or ModifyOwn permissions.
        owner, permissions = sp.match_pair(self.getPermissionsInline(params.place_key, sp.sender))
        hasModifyAll = permissions & permissionModifyAll == permissionModifyAll

        # If ModifyAll permission is not given, make sure remove map only contains sender items.
        with sp.if_(~hasModifyAll):
            with sp.for_("issuer_map", params.remove_map.values()) as issuer_map:
                with sp.for_("remove_key", issuer_map.keys()) as remove_key:
                    sp.verify(remove_key == sp.some(sp.sender), message = self.error_message.no_permission())

        # Token transfer map.
        transferMap = utils.FA2TokenTransferMap()

        # Remove items.
        with sp.for_("chunk_item", params.remove_map.items()) as chunk_item:
            chunk_key = sp.compute(sp.record(place_key = params.place_key, chunk_id = chunk_item.key))

            # Get the chunk - must exist.
            this_chunk = ChunkStorage(self.data.chunks, chunk_key)

            with sp.for_("issuer_item", chunk_item.value.items()) as issuer_item:
                item_owner = utils.openSomeOrDefault(issuer_item.key, owner)

                with sp.for_("fa2_item", issuer_item.value.items()) as fa2_item:
                    # Get item store - must exist.
                    item_store = ItemStorage(this_chunk, issuer_item.key, fa2_item.key)

                    transferMap.add_fa2(fa2_item.key)
                    
                    with sp.for_("curr", fa2_item.value.elements()) as curr:
                        # Nothing to do here with ext items. Just remove them.
                        with item_store.value[curr].match("item") as the_item:
                            # Transfer items back to issuer/owner
                            transferMap.add_token(
                                fa2_item.key,
                                item_owner,
                                the_item.token_id, the_item.amount)

                        # Delete item from storage.
                        del item_store.value[curr]

                    # Remove the item store if empty.
                    item_store.persist_or_remove()

            # Increment chunk interaction counter, as next_id does not change.
            this_chunk.value.counter += 1

            # Persist chunk
            this_chunk.persist()

        # Transfer tokens.
        transferMap.transfer_tokens(sp.self_address)


    @sp.inline_result
    def getTokenRoyalties(self, fa2, token_id):
        """Gets token royalties and/or validate signed royalties."""
        sp.set_type(fa2, sp.TAddress)
        sp.set_type(token_id, sp.TNat)
        royalties_type = sp.local("royalties_type", sp.view("get_royalties_type", self.data.registry,
            fa2, t = registry_contract.t_get_royalties_type_result).open_some())

        # Type 0 = Registry does not know about this token's royalties.
        with sp.if_(royalties_type.value == 0):
            # Get royalties from legacy royalties contract.
            sp.result(sp.view("get_token_royalties", self.data.legacy_royalties,
                sp.set_type_expr(sp.record(fa2=fa2, id=token_id), legacy_royalties_contract.t_token_key),
                t = FA2.t_royalties_interop).open_some())

        with sp.else_():
            with sp.if_(royalties_type.value == 1):
                # Convert V1 royalties to V2.
                royalties = sp.compute(FA2_legacy.get_token_royalties(fa2, token_id))
                royalties_v2 = sp.local("royalties_v2", sp.record(total = 1000, shares = []), FA2.t_royalties_interop)

                with sp.for_("contributor", royalties.contributors) as contributor:
                    royalties_v2.value.shares.push(sp.record(
                        address = contributor.address,
                        share = contributor.relative_royalties * royalties.royalties / 1000))

                sp.result(royalties_v2.value)
            with sp.else_():
                with sp.if_(royalties_type.value == 2):
                    # Just return V2 royalties.
                    sp.result(FA2.get_token_royalties(fa2, token_id))
                with sp.else_():
                    sp.failwith("ROYALTIES_NOT_IMPLEMENTED")


    def sendValueRoyaltiesFeesInline(self, rate, issuer_or_place_owner, item_royalty_info, primary):
        """Inline function for sending royalties, fees, etc."""
        sp.set_type(rate, sp.TMutez)
        sp.set_type(issuer_or_place_owner, sp.TAddress)
        sp.set_type(item_royalty_info, FA2.t_royalties_interop)
        sp.set_type(primary, sp.TBool)

        # Collect amounts to send in a map.
        sendMap = utils.TokenSendMap()

        # First, we take our fees are in permille.
        fees_amount = sp.compute(sp.split_tokens(rate, self.data.fees, sp.nat(1000)))
        sendMap.add(self.data.fees_to, fees_amount)

        value_after_fees = sp.compute(rate - fees_amount)

        # If a primary sale, split entire value (minus fees) according to royalties.
        with sp.if_(primary):
            # Loop over all the shares to find the total shares.
            total_shares = sp.local("total_shares", sp.nat(0))
            with sp.for_("share", item_royalty_info.shares) as share:
                total_shares.value += share.share

            # Loop over all the shares and send value.
            with sp.for_("share", item_royalty_info.shares) as share:
                # Calculate amount to be paid from absolute share.
                share_mutez = sp.compute(sp.split_tokens(value_after_fees, share.share, total_shares.value))
                sendMap.add(share.address, share_mutez)

        # Else, send royalties according to total and send value to issuer or place owner.
        with sp.else_():
            # Loop over all the shares and record how much to send.
            total_royalties = sp.local("total_royalties", sp.mutez(0))
            with sp.for_("share", item_royalty_info.shares) as share:
                # Calculate amount to be paid from absolute share.
                share_mutez = sp.compute(sp.split_tokens(value_after_fees, share.share, item_royalty_info.total))
                sendMap.add(share.address, share_mutez)
                total_royalties.value += share_mutez

            # Send rest of the value to seller.
            left_amount = value_after_fees - total_royalties.value
            sendMap.add(issuer_or_place_owner, left_amount)

        # Transfer.
        sendMap.transfer()


    @sp.inline_result
    def issuerOrValueToOrPlaceOwnerInline(self, place_key, issuer, value_to):
        """Inline function for getting where to send the value of an item to
        (either issuer, value_to or place owner)."""
        sp.set_type(place_key, placeKeyType)
        sp.set_type(issuer, sp.TOption(sp.TAddress))
        sp.set_type(value_to, sp.TOption(sp.TAddress))

        with issuer.match_cases() as arg:
            with arg.match("None", "issuer_none"):
                with value_to.match_cases() as arg:
                    with arg.match("None", "value_to_none"):
                        sp.result(FA2.fa2_nft_get_owner(place_key.fa2, place_key.id))
                    with arg.match("Some") as open:
                        sp.result(open)

            with arg.match("Some") as open:
                sp.result(open)


    @sp.entry_point(lazify = True)
    def get_item(self, params):
        sp.set_type(params, sp.TRecord(
            place_key = placeKeyType,
            chunk_id = sp.TNat,
            item_id = sp.TNat,
            issuer = sp.TOption(sp.TAddress),
            fa2 = sp.TAddress,
            ext = extensionArgType
        ).layout(("place_key", ("chunk_id", ("item_id", ("issuer", ("fa2", "ext")))))))

        self.onlyUnpaused()

        # TODO: Place token must be allowed?
        #self.onlyAllowedPlaceTokens(params.chunk_key.place_key.fa2)

        chunk_key = sp.compute(sp.record(place_key = params.place_key, chunk_id = params.chunk_id))

        # Get place and chunk - must exist.
        this_place = PlaceStorage(self.data.places, params.place_key)
        this_chunk = ChunkStorage(self.data.chunks, chunk_key)

        # If the issuer is none, the value_to or owner is the item owner.
        # Used for sending the value to the correct address.
        item_owner = self.issuerOrValueToOrPlaceOwnerInline(params.place_key, params.issuer, this_place.value.value_to)

        # Get item store - must exist.
        item_store = ItemStorage(this_chunk, params.issuer, params.fa2)

        # Swap based on item type.
        with item_store.value[params.item_id].match_cases() as arg:
            # For tz1and native items.
            with arg.match("item") as immutable:
                # This is silly but required because match args are not mutable.
                the_item = sp.local("the_item", immutable)

                # Make sure it's for sale, and the transfered amount is correct.
                sp.verify(the_item.value.rate > sp.mutez(0), message = self.error_message.not_for_sale())
                sp.verify(the_item.value.rate == sp.amount, message = self.error_message.wrong_amount())

                # Transfer royalties, etc.
                with sp.if_(sp.amount != sp.mutez(0)):
                    # Get the royalties for this item
                    # TODO: royalties for non-tz1and items? maybe token registry could handle that to some extent?
                    # at least in terms of what "type" of royalties.
                    item_royalty_info = self.getTokenRoyalties(
                        params.fa2, the_item.value.token_id)

                    # Send fees, royalties, value.
                    self.sendValueRoyaltiesFeesInline(sp.amount, item_owner, item_royalty_info, the_item.value.primary)
                
                # Transfer item to buyer.
                utils.fa2_transfer(params.fa2, sp.self_address, sp.sender, the_item.value.token_id, 1)
                
                # Reduce the item count in storage or remove it.
                with sp.if_(the_item.value.amount > 1):
                    # NOTE: fine to use abs here, token amout is checked to be > 1.
                    the_item.value.amount = abs(the_item.value.amount - 1)
                    item_store.value[params.item_id] = sp.variant("item", the_item.value)
                with sp.else_():
                    del item_store.value[params.item_id]

            # ext items are unswappable.
            with arg.match("ext"):
                sp.failwith(self.error_message.wrong_item_type())
        
        # Remove the item store if empty.
        item_store.persist_or_remove()

        # Increment chunk interaction counter, as next_id does not change.
        this_chunk.value.counter += 1

        # Persist chunk
        this_chunk.persist()


    #
    # Migration
    #
    # TODO: Permissions?
    @sp.entry_point(lazify = True)
    def migration(self, params):
        """An entrypoint to recieve/send migrations.
        
        Initially set up to recieve migrations but can
        be upgraded to send migrations.
        
        NOTE: migration() assumes tokens have been recieved already.
        This is dangerous, but saves gas and it's clearly an admin-only action."""
        sp.set_type(params, migrationType)

        # Only allow recieving migrations from a certain contract,
        # and also only from admin as source.
        sp.verify((sp.some(sp.sender) == self.data.migration_from) &
            (sp.source == self.data.administrator))

        # Place token must be allowed
        place_limits = self.getAllowedPlaceTokenLimits(params.place_key.fa2)

        # Caller doesn't need permissions, is admin.

        # Get or create the place.
        this_place = PlaceStorage(self.data.places, params.place_key, True)
        # Make sure the place is empty.
        sp.verify(sp.len(this_place.value.chunks) == 0, message = "MIGRATION_PLACE_NOT_EMPTY")

        # Set the props on the place to migrate
        this_place.value.props = params.props
        this_place.value.counter += sp.nat(1)

        # If the migration map isn't empty
        with sp.if_(sp.len(params.item_map) > 0):
            # Keep a running count of items, so we can switch chunks.
            add_item_count = sp.local("add_item_count", sp.nat(0))
            # The current chunk we're working on.
            chunk_key = sp.local("chunk_key", sp.record(place_key = params.place_key, chunk_id = sp.nat(0)))

            fa2_set = sp.local("fa2_set", sp.set(t=sp.TAddress))
            with sp.for_("fa2_map", params.item_map.values()) as fa2_map:
                with sp.for_("fa2", fa2_map.keys()) as fa2:
                    fa2_set.value.add(fa2)

            registry_contract.checkRegistered(
                self.data.registry,
                fa2_set.value)

            # Get or create the current chunk.
            this_chunk = ChunkStorage(self.data.chunks, chunk_key.value, True)

            # For each fa2 in the map.
            with sp.for_("issuer_item", params.item_map.items()) as issuer_item:
                with sp.for_("fa2_item", issuer_item.value.items()) as fa2_item:
                    # Get or create item storage.
                    item_store = ItemStorage(this_chunk, sp.some(issuer_item.key), fa2_item.key, True)

                    # For each item in the list.
                    with sp.for_("curr", fa2_item.value) as curr:
                        # if we added more items than the chunk limit, switch chunks and reset add count to 0
                        with sp.if_(add_item_count.value >= place_limits.chunk_item_limit):
                            # Remove itemstore if empty. Can happen in some cases,
                            # because the item store is created at the beginning of a token loop.
                            # Alternatively we could call item_store_map.get_or_create() inside the loop.
                            item_store.persist_or_remove()

                            # Persist chunk
                            this_chunk.persist(this_place)

                            # Reset counters and increment current chunk.
                            add_item_count.value = sp.nat(0)
                            chunk_key.value = sp.record(place_key = params.place_key, chunk_id = chunk_key.value.chunk_id + sp.nat(1))
                            sp.verify(chunk_key.value.chunk_id < place_limits.chunk_limit, message = self.error_message.chunk_limit())

                            # update chunk and item storage
                            this_chunk.load(chunk_key.value, True)
                            item_store.load(sp.some(issuer_item.key), fa2_item.key, True)

                        with curr.match_cases() as arg:
                            with arg.match("item") as item:
                                self.validateItemData(item.data)

                            with arg.match("ext") as ext_data:
                                self.validateItemData(ext_data)

                        # Add item to storage.
                        item_store.value[this_chunk.value.next_id] = curr

                        # Increment next_id.
                        this_chunk.value.next_id += sp.nat(1)

                        # Add to item add counter
                        add_item_count.value += sp.nat(1)

                    item_store.persist()

            # Don't increment chunk interaction counter, as chunks must be new.

            # Persist chunk
            this_chunk.persist(this_place)
        
        # Persist place
        this_place.persist()


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

            with sp.for_("chunk_id", utils.openSomeOrDefault(params.chunk_ids, res.value.place.chunks).elements()) as chunk_id:
                res.value.chunks[chunk_id] = self.data.chunks.get(sp.record(
                    place_key = params.place_key,
                    chunk_id = chunk_id
                ), chunkStorageDefault)

            sp.result(res.value)


    @sp.onchain_view(pure=True)
    def get_place_seqnum(self, place_key):
        sp.set_type(place_key, placeKeyType)

        with sp.set_result_type(seqNumResultType):
            # Collect chunk sequence numbers.
            this_place = PlaceStorage(self.data.places, place_key, True)
            chunk_sequence_numbers_map = sp.local("chunk_sequence_numbers_map", {}, sp.TMap(sp.TNat, sp.TBytes))
            with sp.for_("chunk_id", this_place.value.chunks.elements()) as chunk_id:
                this_chunk = self.data.chunks.get(sp.record(place_key = place_key, chunk_id = chunk_id), chunkStorageDefault)
                chunk_sequence_numbers_map.value[chunk_id] = sp.sha3(sp.pack(sp.pair(
                    this_chunk.counter,
                    this_chunk.next_id)))

            # Return the result.
            sp.result(sp.record(
                place_seq = sp.sha3(sp.pack(this_place.value.counter)),
                chunk_seqs = chunk_sequence_numbers_map.value))


    @sp.onchain_view(pure=True)
    def get_permissions(self, query):
        sp.set_type(query, sp.TRecord(
            place_key = placeKeyType,
            permittee = sp.TAddress
        ).layout(("place_key", "permittee")))
        with sp.set_result_type(sp.TNat):
            sp.result(sp.snd(self.getPermissionsInline(query.place_key, query.permittee)))
