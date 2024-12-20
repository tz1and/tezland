# The World contract.
#
# Each lot belongs to a Place (an FA2 token that is the "land").
# Items (another type of token) can be stored on your Place, either to swap
# or just to build something nice.

import smartpy as sp

from tz1and_contracts_smartpy.mixins.Administrable import Administrable
from tz1and_contracts_smartpy.mixins.Pausable import Pausable
from tz1and_contracts_smartpy.mixins.Upgradeable import Upgradeable
from tz1and_contracts_smartpy.mixins.ContractMetadata import ContractMetadata
from tz1and_contracts_smartpy.mixins.MetaSettings import MetaSettings
from contracts.mixins.Fees import Fees
from contracts.mixins.Moderation import Moderation
from contracts.mixins.AllowedPlaceTokens import AllowedPlaceTokens

from contracts import TL_TokenRegistry, TL_RoyaltiesAdapter, FA2
from contracts.utils import TokenTransfer, FA2Utils, ErrorMessages
from tz1and_contracts_smartpy.utils import Utils


# Now:
# TODO: figure out ext-type items. could in theory be a separate map on the issuer level? maybe have token addess and option and make ext items go into sp.none?
# TODO: add tests issuerOrValueToOrPlaceOwnerInline, etc. to make sure they work correctly in all combinations.
# TODO: test royalties:
#       + V1 royalties
#       + V2 royalties
#       + trusted (legacy) royalties
# TODO: reverse issuer and fa2 storage? this came up before... it shouldn't make a difference. registry.is_registered could be list. and maybe some other things.
# TODO: VIEWS: use getX/onlyX instead of isX/checkX where it applies. isX may be OK sometimes!
# TODO: go over records again, find where we can use map/set
# TODO: include AdminLambda in contracts?
# TODO: Could make a wallet contract to be able to test royalties sent, etc...
# TODO: LOOK AT MINTER SIZE INCREASE!!!
# TODO: INDEXER: validate collection metadata doesn't contain fishy stuff (offchain views etc)


# Some time
# TODO: special permission for sending items to place? Might be good.
# TODO: delete empty chunks? chunk store remove_if_empty. make sure to delete them from place as well.
# TODO: so many empty FAILWITHs. Optimise... What still can be.


# Other
# TODO: think of some more tests for permission.
# TODO: DAO token drop with signed drops. Based on collections or royalties. Sign, record if paid.
# TODO: sorting out the splitting of dao and team (probably with a proxy contract)
# TODO: proxy contract will also be some kind of multisig for all the only-admin things (pausing operation)
# TODO: research storage deserialisation limits
# TODO: investgate using a "metadata map" for item data.
# TODO: check if packing/unpacking michelson maps works well for script variables


# Some notes:
# - maketet blacklist adds about 200 gas to token transfers. not sure if worth it.
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
    value_to = sp.TOption(sp.TAddress), # value for place owned items is sent to, if set
    items_to = sp.TOption(sp.TAddress) # where place owned items are sent to when removed, if set
).layout(("counter", ("props", ("chunks", ("value_to", "items_to")))))

placeStorageDefault = sp.record(
    counter = sp.nat(0),
    props = defaultPlaceProps,
    chunks = sp.set([]),
    value_to = sp.none,
    items_to = sp.none)

placeKeyType = sp.TRecord(
    fa2 = sp.TAddress,
    id = sp.TNat
).layout(("fa2", "id"))

placeMapType = sp.TBigMap(placeKeyType, placeStorageType)


class PlaceStorage:
    @staticmethod
    def make():
        return sp.big_map(tkey=placeKeyType, tvalue=placeStorageType)

    def __init__(self, map, key, create: bool = False):
        sp.set_type(map, placeMapType) # set_type_expr gives compiler error
        self.data_map = map
        self.this_place_key = sp.set_type_expr(key, placeKeyType)
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

    def load(self, new_key, create: bool = False):
        self.this_place_key = sp.set_type_expr(new_key, placeKeyType)
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

placeSeqNumParam = placeDataParam

placeDataResultType = sp.TRecord(
    place = placeStorageType,
    chunks = sp.TMap(sp.TNat, chunkStorageType)
).layout(("place", "chunks"))

chunkMapType = sp.TBigMap(chunkPlaceKeyType, chunkStorageType)


class ChunkStorage:
    @staticmethod
    def make():
        return sp.big_map(tkey=chunkPlaceKeyType, tvalue=chunkStorageType)

    def __init__(self, map, key, create: bool = False):
        sp.set_type(map, chunkMapType) # set_type_expr gives compiler error
        self.data_map = map
        self.this_chunk_key = sp.set_type_expr(key, chunkPlaceKeyType)
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

    def load(self, new_key, create: bool = False):
        self.this_chunk_key = sp.set_type_expr(new_key, chunkPlaceKeyType)
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

    def __init__(self, chunk_storage: ChunkStorage, issuer, fa2, create: bool = False):
        self.chunk_storage = chunk_storage
        self.issuer = sp.set_type_expr(issuer, sp.TOption(sp.TAddress))
        self.fa2 = sp.set_type_expr(fa2, sp.TAddress)
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

    def load(self, new_issuer, new_fa2, create: bool = False):
        self.issuer = sp.set_type_expr(new_issuer, sp.TOption(sp.TAddress))
        self.fa2 = sp.set_type_expr(new_fa2, sp.TAddress)
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

updatePlacePropsVariantType = sp.TVariant(
    add_props = placePropsType,
    del_props = sp.TSet(sp.TBytes)
).layout(("add_props", "del_props"))

updatePlaceOwnerPropsVariantType = sp.TVariant(
    value_to = sp.TOption(sp.TAddress),
    items_to = sp.TOption(sp.TAddress)
).layout(("value_to", "items_to"))

# Types for place, get, update, remove entry points.
updatePlaceType = sp.TRecord(
    place_key = placeKeyType,
    update = sp.TVariant(
        props = sp.TList(updatePlacePropsVariantType),
        owner_props = sp.TList(updatePlaceOwnerPropsVariantType)
    ).layout(("props", "owner_props")),
    ext = extensionArgType
).layout(("place_key", ("update", "ext")))

placeItemsType = sp.TRecord(
    place_key = placeKeyType,
    place_item_map = sp.TMap(sp.TNat, sp.TMap(sp.TBool, sp.TMap(sp.TAddress, sp.TList(extensibleVariantItemType)))),
    ext = extensionArgType
).layout(("place_key", ("place_item_map", "ext")))

setItemDataType = sp.TRecord(
    place_key = placeKeyType,
    update_map = sp.TMap(sp.TNat, sp.TMap(sp.TOption(sp.TAddress), sp.TMap(sp.TAddress, sp.TList(updateItemListType)))),
    ext = extensionArgType
).layout(("place_key", ("update_map", "ext")))

removeItemsType = sp.TRecord(
    place_key = placeKeyType,
    remove_map = sp.TMap(sp.TNat, sp.TMap(sp.TOption(sp.TAddress), sp.TMap(sp.TAddress, sp.TSet(sp.TNat)))),
    ext = extensionArgType
).layout(("place_key", ("remove_map", "ext")))

getItemType = sp.TRecord(
    place_key = placeKeyType,
    chunk_id = sp.TNat,
    item_id = sp.TNat,
    issuer = sp.TOption(sp.TAddress),
    fa2 = sp.TAddress,
    ext = extensionArgType
).layout(("place_key", ("chunk_id", ("item_id", ("issuer", ("fa2", "ext"))))))

itemDataMinLen = sp.nat(7) # format 0 is 7 bytes
placePropsColorLen = sp.nat(3) # 3 bytes for color

# Permissions are in octal.
# Can be any combination of these.
# Remove and modify own items in all places is always given. to prevent abuse.
permissionNone       = sp.nat(0) # no permissions
permissionPlaceItems = sp.nat(1) # can place items
permissionModifyAll  = sp.nat(2) # can edit and remove all items
permissionProps      = sp.nat(4) # can edit place props
permissionOwnerProps = sp.nat(8) # can change owner props.
permissionFull       = sp.nat(15) # has full permissions.

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

setPermissionsType = sp.TList(sp.TVariant(
    add = PermissionParams.get_add_type(),
    remove = PermissionParams.get_remove_type()
).layout(("add", "remove")))


#
# The World contract.
# NOTE: should be pausable for code updates and because other item fa2 tokens are out of our control.
class TL_World_v2(
    Administrable,
    ContractMetadata,
    Pausable,
    Fees,
    Moderation,
    AllowedPlaceTokens,
    MetaSettings,
    Upgradeable,
    sp.Contract):
    def __init__(self, administrator, registry, royalties_adapter, paused, items_tokens, metadata,
        name, description, exception_optimization_level="default-line", debug_asserts=False, include_views=True):

        sp.Contract.__init__(self)

        # Needed for migration ep but not really needed otherwise.
        self.items_tokens = sp.set_type_expr(items_tokens, sp.TAddress)
        self.debug_asserts = debug_asserts

        self.add_flag("exceptions", exception_optimization_level)
        #self.add_flag("erase-comments")
        # Not a win at all in terms of gas, especially on the simpler eps.
        #self.add_flag("lazy-entry-points")
        # No noticeable effect on gas.
        #self.add_flag("initial-cast")
        # Makes much smaller code but removes annots from eps.
        #self.add_flag("simplify-via-michel")

        self.permission_map = Permission_map()

        self.init_storage(
            permissions = self.permission_map.make(),
            places = PlaceStorage.make(),
            chunks = ChunkStorage.make()
        )

        self.addMetaSettings([
            ("registry", registry, sp.TAddress, lambda x : Utils.onlyContract(x)),
            ("royalties_adapter", royalties_adapter, sp.TAddress, lambda x : Utils.onlyContract(x)),
            ("migration_from", sp.none, sp.TOption(sp.TAddress), lambda x : Utils.ifSomeRun(x, lambda y: Utils.onlyContract(y))),
            ("max_permission", permissionFull, sp.TNat, lambda x: sp.verify(Utils.isPowerOfTwoMinusOne(x), message=ErrorMessages.parameter_error()))
        ])

        if include_views: self.addViews()

        Administrable.__init__(self, administrator = administrator, include_views = False)
        Pausable.__init__(self, paused = paused, include_views = False)
        ContractMetadata.__init__(self, metadata = metadata)
        Fees.__init__(self, fees_to = administrator)
        Moderation.__init__(self)
        AllowedPlaceTokens.__init__(self, include_views = include_views)
        MetaSettings.__init__(self)
        Upgradeable.__init__(self)

        self.generateContractMetadata(name, description,
            authors=["852Kerfunkle <https://github.com/852Kerfunkle>"],
            source_location="https://github.com/tz1and",
            homepage="https://www.tz1and.com", license="UNLICENSED",
            version="2.0.0")


    #
    # Public entry points
    #
    @sp.entry_point(lazify=True, parameter_type=setPermissionsType)
    def set_permissions(self, params):
        #self.onlyUnpaused() # Probably fine to run when paused.

        with sp.for_("update", params) as update:
            with update.match_cases() as arg:
                with arg.match("add") as upd:
                    # can only add permissions for allowed places
                    self.onlyAllowedPlaceTokens(upd.place_key.fa2)
                    # Sender must be the owner
                    sp.verify(upd.owner == sp.sender, message = ErrorMessages.not_owner())
                    sp.verify((upd.perm > permissionNone) & (upd.perm <= self.data.settings.max_permission), message = ErrorMessages.parameter_error())
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
                    sp.verify(upd.owner == sp.sender, message = ErrorMessages.not_owner())
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

        place_owner = sp.local("place_owner", FA2.getOwner(place_key.fa2, place_key.id).open_some())

        # If permittee is the owner, he has full permission.
        with sp.if_(place_owner.value == permittee):
            sp.result(sp.pair(place_owner.value, self.data.settings.max_permission))
        # Else, query permissions.
        with sp.else_():
            sp.result(sp.pair(place_owner.value, self.permission_map.get_octal(self.data.permissions,
                place_owner.value,
                permittee,
                place_key)))


    @sp.entry_point(lazify = True, parameter_type=updatePlaceType)
    def update_place(self, params):
        self.onlyUnpaused()

        # Place token must be allowed
        self.onlyAllowedPlaceTokens(params.place_key.fa2)

        permissions = sp.snd(self.getPermissionsInline(params.place_key, sp.sender))

        # Get or create the place.
        this_place = PlaceStorage(self.data.places, params.place_key, True)

        with params.update.match_cases() as update_arg:
            with update_arg.match("props") as props:
                # Caller must have props permissions.
                sp.verify(permissions & permissionProps == permissionProps, message = ErrorMessages.no_permission())

                with sp.for_("item", props) as item:
                    with item.match_cases() as arg:
                        with arg.match("add_props") as add_props:
                            with sp.for_("prop", add_props.items()) as prop:
                                this_place.value.props[prop.key] = prop.value

                        with arg.match("del_props") as del_props:
                            with sp.for_("prop", del_props.elements()) as prop:
                                del this_place.value.props[prop]

                # Verify the properties contrain at least the color (key 0x00).
                # And that the color is the right length.
                sp.verify(sp.len(this_place.value.props.get(sp.bytes("0x00"), message=ErrorMessages.parameter_error())) == placePropsColorLen,
                    message = ErrorMessages.data_length())

            with update_arg.match("owner_props") as owner_props:
                # Caller must have propsOwner permissions.
                sp.verify(permissions & permissionOwnerProps == permissionOwnerProps, message = ErrorMessages.no_permission())

                with sp.for_("item", owner_props) as item:
                    with item.match_cases() as arg:
                        with arg.match("value_to") as value_to:
                            this_place.value.value_to = value_to

                        with arg.match("items_to") as items_to:
                            this_place.value.items_to = items_to

        # Increment place interaction counter.
        this_place.value.counter += 1

        # Persist place.
        this_place.persist()


    def validateItemData(self, data):
        """Verify the item data has the right length."""
        sp.verify(sp.len(data) >= itemDataMinLen, message = ErrorMessages.data_length())


    @sp.entry_point(lazify = True, parameter_type=placeItemsType)
    def place_items(self, params):
        self.onlyUnpaused()

        # Place token must be allowed
        place_limits = self.getAllowedPlaceTokenLimits(params.place_key.fa2)

        # Caller must have PlaceItems permissions.
        permissions = sp.snd(self.getPermissionsInline(params.place_key, sp.sender))
        sp.verify(permissions & permissionPlaceItems == permissionPlaceItems, message = ErrorMessages.no_permission())
        # TODO: special permission for sending items to place? Might be good.

        # Count items to be added, get FA2 set and check id limits.
        chunk_add_item_count = sp.local("chunk_add_item_count", sp.map(tkey=sp.TNat, tvalue=sp.TNat))
        fa2_set = sp.local("fa2_set", sp.set(t=sp.TAddress))
        with sp.for_("chunk_item", params.place_item_map.items()) as chunk_item:
            sp.verify(chunk_item.key < place_limits.chunk_limit, message = ErrorMessages.chunk_limit())

            add_item_count = sp.local("add_item_count", sp.nat(0))
            with sp.for_("fa2_map", chunk_item.value.values()) as fa2_map:
                with sp.for_("fa2_item", fa2_map.items()) as fa2_item:
                    fa2_set.value.add(fa2_item.key)
                    add_item_count.value += sp.len(fa2_item.value)

            chunk_add_item_count.value[chunk_item.key] = add_item_count.value

        # Get or create the place and chunk.
        this_place = PlaceStorage(self.data.places, params.place_key, True)

        # Our token transfer map.
        transferMap = TokenTransfer.FA2TokenTransferMap()

        # Get registry info for FA2s.
        sp.compute(TL_TokenRegistry.onlyRegistered(self.data.settings.registry, fa2_set.value).open_some())

        with sp.for_("chunk_item", params.place_item_map.items()) as chunk_item:
            chunk_key = sp.compute(sp.record(place_key = params.place_key, chunk_id = chunk_item.key))

            this_chunk = ChunkStorage(self.data.chunks, chunk_key, True)

            # Count items in place item storage.
            chunk_item_count = this_chunk.count_items()

            # Make sure chunk item limit is not exceeded.
            sp.verify(chunk_item_count + chunk_add_item_count.value.get(chunk_item.key, sp.nat(0)) <= place_limits.chunk_item_limit, message = ErrorMessages.chunk_item_limit())

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

                                # Transfer item to this contract.
                                transferMap.add_token(fa2_item.key, sp.self_address, item.token_id, item.amount)

                            with arg.match("ext") as ext_data:
                                self.validateItemData(ext_data)

                        if (self.debug_asserts):
                            sp.verify(~item_store.value.contains(this_chunk.value.next_id),
                                sp.pair("Debug assert: Map already contains item", this_chunk.value.next_id))

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


    @sp.entry_point(lazify = True, parameter_type=setItemDataType)
    def set_item_data(self, params):
        self.onlyUnpaused()

        # NOTE: doesn't matter if place token is not allowed.
        #self.onlyAllowedPlaceTokens(params.place_key.fa2)

        # Caller must have ModifyAll or ModifyOwn permissions.
        permissions = sp.snd(self.getPermissionsInline(params.place_key, sp.sender))
        hasModifyAll = permissions & permissionModifyAll == permissionModifyAll

        # If ModifyAll permission is not given, make sure update map only contains sender items.
        with sp.if_(~hasModifyAll):
            with sp.for_("issuer_map", params.update_map.values()) as issuer_map:
                with sp.for_("remove_key", issuer_map.keys()) as remove_key:
                    sp.verify(remove_key == sp.some(sp.sender), message = ErrorMessages.no_permission())

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


    @sp.inline_result
    def issuerOrItemsToOrPlaceOwnerInline(self, issuer, items_to, owner):
        """Inline function for getting where to send the a place ownd tiem
        on removal (either issuer, items_to or place owner)."""
        sp.set_type(issuer, sp.TOption(sp.TAddress))
        sp.set_type(items_to, sp.TOption(sp.TAddress))
        sp.set_type(owner, sp.TAddress)

        with issuer.match_cases() as arg:
            with arg.match("None", "issuer_none"):
                with items_to.match_cases() as arg:
                    with arg.match("None", "items_to_none"):
                        sp.result(owner)
                    with arg.match("Some") as open:
                        sp.result(open)

            with arg.match("Some") as open:
                sp.result(open)


    @sp.entry_point(lazify = True, parameter_type=removeItemsType)
    def remove_items(self, params):
        self.onlyUnpaused()

        # NOTE: doesn't matter if place token is not allowed.
        #self.onlyAllowedPlaceTokens(params.place_key.fa2)

        # Caller must have ModifyAll or ModifyOwn permissions.
        owner, permissions = sp.match_pair(self.getPermissionsInline(params.place_key, sp.sender))
        hasModifyAll = permissions & permissionModifyAll == permissionModifyAll

        # If ModifyAll permission is not given, make sure remove map only contains sender items.
        with sp.if_(~hasModifyAll):
            with sp.for_("issuer_map", params.remove_map.values()) as issuer_map:
                with sp.for_("remove_key", issuer_map.keys()) as remove_key:
                    sp.verify(remove_key == sp.some(sp.sender), message = ErrorMessages.no_permission())

        # Get the place - must exist.
        this_place = PlaceStorage(self.data.places, params.place_key)

        # Token transfer map.
        transferMap = TokenTransfer.FA2TokenTransferMap()

        # Remove items.
        with sp.for_("chunk_item", params.remove_map.items()) as chunk_item:
            chunk_key = sp.compute(sp.record(place_key = params.place_key, chunk_id = chunk_item.key))

            # Get the chunk - must exist.
            this_chunk = ChunkStorage(self.data.chunks, chunk_key)

            with sp.for_("issuer_item", chunk_item.value.items()) as issuer_item:
                # If the issuer is none, the items_to or owner is the item owner.
                # Used for sending place owned items to the correct address.
                item_owner = self.issuerOrItemsToOrPlaceOwnerInline(issuer_item.key, this_place.value.items_to, owner)

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
                        sp.result(FA2.getOwner(place_key.fa2, place_key.id).open_some())
                    with arg.match("Some") as open:
                        sp.result(open)

            with arg.match("Some") as open:
                sp.result(open)


    @sp.entry_point(lazify = True, parameter_type=getItemType)
    def get_item(self, params):
        self.onlyUnpaused()

        # NOTE: doesn't matter if place token is not allowed.
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
                sp.verify(the_item.value.rate > sp.mutez(0), message = ErrorMessages.not_for_sale())
                sp.verify(the_item.value.rate == sp.amount, message = ErrorMessages.wrong_amount())

                # Transfer royalties, etc.
                with sp.if_(sp.amount != sp.mutez(0)):
                    # Get the royalties for this item
                    item_royalty_info = sp.compute(TL_RoyaltiesAdapter.getRoyalties(
                        self.data.settings.royalties_adapter, sp.record(fa2 = params.fa2, id = the_item.value.token_id)).open_some())

                    # Send fees, royalties, value.
                    TL_RoyaltiesAdapter.sendValueRoyaltiesFeesInline(self.data.settings.fees, self.data.settings.fees_to, sp.amount,
                        item_owner, item_royalty_info, the_item.value.primary)
                
                # Transfer item to buyer.
                FA2Utils.fa2_transfer(params.fa2, sp.self_address, sp.sender, the_item.value.token_id, 1)
                
                # Reduce the item count in storage or remove it.
                with sp.if_(the_item.value.amount > 1):
                    # NOTE: fine to use abs here, token amout is checked to be > 1.
                    the_item.value.amount = abs(the_item.value.amount - 1)
                    item_store.value[params.item_id] = sp.variant("item", the_item.value)
                with sp.else_():
                    del item_store.value[params.item_id]

            # ext items are unswappable.
            with arg.match("ext"):
                sp.failwith(ErrorMessages.wrong_item_type())
        
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
    @sp.entry_point(lazify = True, parameter_type=migrationType)
    def migration(self, params):
        """An entrypoint to recieve/send migrations.
        
        Initially set up to recieve migrations but can
        be upgraded to send migrations.
        
        NOTE: migration() assumes tokens have been recieved already.
        This is dangerous, but saves gas and it's clearly an admin-only action."""
        # Only allow recieving migrations from a certain contract,
        # and also only from admin as source.
        sp.verify((sp.some(sp.sender) == self.data.settings.migration_from) &
            (sp.source == self.data.administrator))

        # Place token must be allowed
        place_limits = self.getAllowedPlaceTokenLimits(params.place_key.fa2)

        # Caller doesn't need permissions, is admin.

        # Get or create the place.
        this_place = PlaceStorage(self.data.places, params.place_key, True)
        # Make sure the place is empty.
        sp.verify(sp.len(this_place.value.chunks) == 0, message = ErrorMessages.migration_place_not_emptry())

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

            sp.compute(TL_TokenRegistry.onlyRegistered(self.data.settings.registry, fa2_set.value).open_some())

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
                            sp.verify(chunk_key.value.chunk_id < place_limits.chunk_limit, message = ErrorMessages.chunk_limit())

                            # update chunk and item storage
                            this_chunk.load(chunk_key.value, True)
                            item_store.load(sp.some(issuer_item.key), fa2_item.key, True)

                        with curr.match_cases() as arg:
                            with arg.match("item") as item:
                                self.validateItemData(item.data)

                            with arg.match("ext") as ext_data:
                                self.validateItemData(ext_data)

                        if (self.debug_asserts):
                            sp.verify(~item_store.value.contains(this_chunk.value.next_id),
                                sp.pair("Debug assert: Map already contains item", this_chunk.value.next_id))

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
    def addViews(self):
        def get_place_data(self, params):
            sp.set_type(params, placeDataParam)
            with sp.set_result_type(placeDataResultType):
                res = sp.local("res", sp.record(
                    place = self.data.places.get(params.place_key, placeStorageDefault),
                    chunks = {}))

                with sp.for_("chunk_id", Utils.openSomeOrDefault(params.chunk_ids, res.value.place.chunks).elements()) as chunk_id:
                    this_chunk_opt = self.data.chunks.get_opt(sp.record(place_key = params.place_key, chunk_id = chunk_id))
                    with this_chunk_opt.match("Some") as this_chunk:
                        res.value.chunks[chunk_id] = this_chunk

                sp.result(res.value)
        self.get_place_data = sp.onchain_view(pure=True)(get_place_data)


        def get_place_seqnum(self, params):
            sp.set_type(params, placeSeqNumParam)

            with sp.set_result_type(seqNumResultType):
                this_place_opt = self.data.places.get_opt(params.place_key)

                with this_place_opt.match_cases() as arg:
                    with arg.match("Some", "this_place") as this_place:
                        # Collect chunk sequence numbers.
                        chunk_sequence_numbers_map = sp.local("chunk_sequence_numbers_map", {}, seqNumResultType.chunk_seqs)

                        with sp.for_("chunk_id", Utils.openSomeOrDefault(params.chunk_ids, this_place.chunks).elements()) as chunk_id:
                            this_chunk_opt = self.data.chunks.get_opt(sp.record(place_key = params.place_key, chunk_id = chunk_id))
                            with this_chunk_opt.match("Some") as this_chunk:
                                chunk_sequence_numbers_map.value[chunk_id] = sp.sha3(sp.pack(sp.pair(
                                    this_chunk.counter,
                                    this_chunk.next_id)))

                        # Return the result.
                        sp.result(sp.record(
                            place_seq = sp.sha3(sp.pack(this_place.counter)),
                            chunk_seqs = chunk_sequence_numbers_map.value))

                    with arg.match("None"):
                        sp.result(sp.record(
                            place_seq = sp.sha3(sp.pack(0)),
                            chunk_seqs = {}))
        self.get_place_seqnum = sp.onchain_view(pure=True)(get_place_seqnum)


        def get_permissions(self, query):
            sp.set_type(query, sp.TRecord(
                place_key = placeKeyType,
                permittee = sp.TAddress
            ).layout(("place_key", "permittee")))
            with sp.set_result_type(sp.TNat):
                sp.result(sp.snd(self.getPermissionsInline(query.place_key, query.permittee)))
        self.get_permissions = sp.onchain_view(pure=True)(get_permissions)
