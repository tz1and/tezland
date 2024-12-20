import smartpy as sp

from tz1and_contracts_smartpy.mixins.Administrable import Administrable
from tz1and_contracts_smartpy.mixins.Pausable import Pausable
from tz1and_contracts_smartpy.mixins.Upgradeable import Upgradeable
from tz1and_contracts_smartpy.mixins.ContractMetadata import ContractMetadata
from tz1and_contracts_smartpy.mixins.MetaSettings import MetaSettings
from tz1and_contracts_smartpy.mixins.BasicPermissions import BasicPermissions

from contracts.utils import EnvUtils, ErrorMessages


ownershipInfo = sp.TOption(sp.TRecord(
    owner = sp.TAddress,
    proposed_owner = sp.TOption(sp.TAddress),
).layout(("owner", "proposed_owner")))

# Know royalties types for bounded type
royaltiesLegacy   = sp.bounded(sp.nat(0))
royaltiesTz1andV1 = sp.bounded(sp.nat(1))
royaltiesTz1andV2 = sp.bounded(sp.nat(2))

t_royalties_bounded = sp.TBounded([0, 1, 2], sp.TNat)

# Collection types for bouded type.
collectionPrivate = sp.bounded(sp.nat(0))
collectionPublic  = sp.bounded(sp.nat(1))
collectionTrusted = sp.bounded(sp.nat(2))

t_collection_bounded = sp.TBounded([0, 1, 2], sp.TNat)

collectionType = sp.TRecord(
    royalties_type = t_royalties_bounded,
    collection_type = t_collection_bounded,
    ownership = ownershipInfo
).layout(("royalties_type", ("collection_type", "ownership")))

collectionMapLiteral = sp.big_map(tkey = sp.TAddress, tvalue = collectionType)

manageCollectionVariant = sp.TVariant(
    add_private = sp.TMap(sp.TAddress, sp.TRecord(
        owner = sp.TAddress,
        royalties_type = t_royalties_bounded
    ).layout(("owner", "royalties_type"))),
    add_public = sp.TMap(sp.TAddress, t_royalties_bounded),
    add_trusted = sp.TMap(sp.TAddress, sp.TRecord(
        signature = sp.TSignature,
        royalties_type = t_royalties_bounded
    ).layout(("signature", "royalties_type"))),
    remove = sp.TSet(sp.TAddress)
).layout(("add_private", ("add_public", ("add_trusted", "remove"))))

t_manage_collections = sp.TList(manageCollectionVariant)

collaboratorsKeyType = sp.TRecord(collection = sp.TAddress, collaborator = sp.TAddress).layout(("collection", "collaborator"))
collaboratorsMapLiteral = sp.big_map(tkey = collaboratorsKeyType, tvalue = sp.TUnit)

adminPrivateCollectionVariant = sp.TVariant(
    add_collaborators = sp.TMap(sp.TAddress, sp.TSet(sp.TAddress)),
    remove_collaborators = sp.TMap(sp.TAddress, sp.TSet(sp.TAddress)),
    transfer_ownership = sp.TRecord(
        collection = sp.TAddress,
        new_owner = sp.TAddress
    ).layout(("collection", "new_owner")),
    acccept_ownership = sp.TAddress
).layout(("add_collaborators", ("remove_collaborators", ("transfer_ownership", "acccept_ownership"))))

t_admin_private_collections = sp.TList(adminPrivateCollectionVariant)

# View params
t_ownership_check = sp.TRecord(
    collection = sp.TAddress,
    address = sp.TAddress
).layout(("collection", "address"))
t_ownership_result = sp.TBounded(["owner", "collaborator"], sp.TString) 

t_registry_param = sp.TSet(sp.TAddress)
t_registry_result = sp.TSet(sp.TAddress)

#
# Collections "Trusted" - signed offchain.
#

# Don't need the address here, because it's the map key map.
t_collection_sign = sp.TRecord(
    collection=sp.TAddress,
    royalties_type=t_royalties_bounded
).layout(("collection", "royalties_type"))


def signCollection(collection_sign, private_key):
    collection_sign = sp.set_type_expr(collection_sign, t_collection_sign)
    # Gives: Type format error atom secret_key
    #private_key = sp.set_type_expr(private_key, sp.TSecretKey)

    packed_collection_sign = sp.pack(collection_sign)

    signature = sp.make_signature(
        private_key,
        packed_collection_sign,
        message_format = 'Raw')

    return signature


@EnvUtils.view_helper
def getRegistered(token_registry, fa2_set) -> sp.Expr:
    return sp.view("get_registered", sp.set_type_expr(token_registry, sp.TAddress),
        sp.set_type_expr(fa2_set, t_registry_param),
        t = t_registry_result)


@EnvUtils.view_helper
def onlyRegistered(token_registry, fa2_set) -> sp.Expr:
    return sp.view("only_registered", sp.set_type_expr(token_registry, sp.TAddress),
        sp.set_type_expr(fa2_set, t_registry_param),
        t = sp.TUnit)


@EnvUtils.view_helper
def getRoyaltiesType(token_registry, fa2) -> sp.Expr:
    return sp.view("get_royalties_type", sp.set_type_expr(token_registry, sp.TAddress),
        sp.set_type_expr(fa2, sp.TAddress),
        t = t_royalties_bounded)


@EnvUtils.view_helper
def getCollectionInfo(token_registry, fa2) -> sp.Expr:
    return sp.view("get_collection_info", sp.set_type_expr(token_registry, sp.TAddress),
        sp.set_type_expr(fa2, sp.TAddress),
        t = collectionType)


@EnvUtils.view_helper
def isPrivateOwnerOrCollab(token_registry, collection, address) -> sp.Expr:
    return sp.view("is_private_owner_or_collab", sp.set_type_expr(token_registry, sp.TAddress),
        sp.set_type_expr(sp.record(
            collection = collection,
            address = address
        ), t_ownership_check),
        t = t_ownership_result)


#
# Token registry contract.
# NOTE: should be pausable for code updates.
class TL_TokenRegistry(
    Administrable,
    ContractMetadata,
    BasicPermissions,
    Pausable,
    MetaSettings,
    Upgradeable,
    sp.Contract):
    def __init__(self, administrator, collections_public_key, metadata, exception_optimization_level="default-line"):
        sp.Contract.__init__(self)

        self.add_flag("exceptions", exception_optimization_level)
        #self.add_flag("erase-comments")

        collections_public_key = sp.set_type_expr(collections_public_key, sp.TKey)

        self.init_storage(
            collections = collectionMapLiteral,
            collaborators = collaboratorsMapLiteral
        )

        self.addMetaSettings([
            ("collections_public_key", collections_public_key, sp.TKey, None)
        ])

        Administrable.__init__(self, administrator = administrator, include_views = False)
        Pausable.__init__(self, include_views = False)
        ContractMetadata.__init__(self, metadata = metadata)
        BasicPermissions.__init__(self, lazy_ep = True)
        MetaSettings.__init__(self)
        Upgradeable.__init__(self)

        self.generateContractMetadata("tz1and TokenRegistry", "tz1and token registry",
            authors=["852Kerfunkle <https://github.com/852Kerfunkle>"],
            source_location="https://github.com/tz1and",
            homepage="https://www.tz1and.com", license="UNLICENSED")


    #
    # Some inline helpers
    #
    def onlyOwnerPrivate(self, collection):
        # Get owner from private collection map and check owner
        the_collection = sp.compute(self.data.collections.get(collection, message = ErrorMessages.invalid_collection()))
        sp.verify(the_collection.collection_type == collectionPrivate, ErrorMessages.not_private())
        # CHeck owner.
        sp.verify(the_collection.ownership.open_some().owner == sp.sender, ErrorMessages.only_owner())


    #
    # Mixed admin, permitted and user.
    #
    @sp.entry_point(lazify = True)
    def manage_collections(self, params):
        """Admin or permitted can add/remove public collections in minter"""
        sp.set_type(params, t_manage_collections)

        self.onlyUnpaused()

        with sp.for_("task", params) as task:
            with task.match_cases() as arg:
                with arg.match("add_private") as add_private:
                    # Only admin or permitted can add_private.
                    self.onlyAdministratorOrPermitted()

                    with sp.for_("add_private_item", add_private.items()) as add_private_item:
                        # You cannot add collections that already exist
                        sp.verify(~self.data.collections.contains(add_private_item.key), ErrorMessages.collection_exists())
                        self.data.collections[add_private_item.key] = sp.record(
                            royalties_type = add_private_item.value.royalties_type,
                            collection_type = collectionPrivate,
                            ownership = sp.some(sp.record(
                                owner = add_private_item.value.owner,
                                proposed_owner = sp.none)))

                with arg.match("add_public") as add_public:
                    # Only admin or permitted can add_public.
                    self.onlyAdministratorOrPermitted()

                    with sp.for_("add_public_item", add_public.items()) as add_public_item:
                        # You cannot add collections that already exist
                        sp.verify(~self.data.collections.contains(add_public_item.key), ErrorMessages.collection_exists())
                        self.data.collections[add_public_item.key] = sp.record(
                            royalties_type = add_public_item.value,
                            collection_type = collectionPublic,
                            ownership = sp.none)

                with arg.match("add_trusted") as add_trusted:
                    # Anyone can add_trusted. If the signature is valid.
                    with sp.for_("add_trusted_item", add_trusted.items()) as add_trusted_item:
                        # You cannot add collections that already exist
                        sp.verify(~self.data.collections.contains(add_trusted_item.key), ErrorMessages.collection_exists())

                        # Validate signature!
                        sp.verify(sp.check_signature(self.data.settings.collections_public_key,
                            add_trusted_item.value.signature,
                            sp.pack(sp.set_type_expr(sp.record(
                                collection=add_trusted_item.key,
                                royalties_type=add_trusted_item.value.royalties_type),
                                t_collection_sign))), "INVALID_SIGNATURE")

                        self.data.collections[add_trusted_item.key] = sp.record(
                            royalties_type = add_trusted_item.value.royalties_type,
                            collection_type = collectionTrusted,
                            ownership = sp.none)

                with arg.match("remove") as remove:
                    # Only admin or permitted can remove.
                    self.onlyAdministratorOrPermitted()

                    with sp.for_("remove_element", remove.elements()) as remove_element:
                        del self.data.collections[remove_element]


    #
    # Private entry points
    #
    @sp.entry_point(lazify = True)
    def admin_private_collections(self, params):
        """User can add/remove collaborators to private collections, transfer owner."""
        sp.set_type(params, t_admin_private_collections)

        self.onlyUnpaused()

        with sp.for_("upd", params) as upd:
            with upd.match_cases() as arg:
                with arg.match("add_collaborators") as add_collaborators:
                    with sp.for_("add_collaborators_item", add_collaborators.items()) as add_collaborators_item:
                        self.onlyOwnerPrivate(add_collaborators_item.key)
                        with sp.for_("address", add_collaborators_item.value.elements()) as address:
                            self.data.collaborators[sp.record(collection = add_collaborators_item.key, collaborator = address)] = sp.unit

                with arg.match("remove_collaborators") as remove_collaborators:
                    with sp.for_("remove_collaborators_item", remove_collaborators.items()) as remove_collaborators_item:
                        self.onlyOwnerPrivate(remove_collaborators_item.key)
                        with sp.for_("address", remove_collaborators_item.value.elements()) as address:
                            del self.data.collaborators[sp.record(collection = remove_collaborators_item.key, collaborator = address)]

                with arg.match("transfer_ownership") as transfer_ownership:
                    the_collection = sp.compute(self.data.collections.get(transfer_ownership.collection, message = ErrorMessages.invalid_collection()))
                    sp.verify(the_collection.collection_type == collectionPrivate, ErrorMessages.not_private())
                    ownership_open = sp.compute(the_collection.ownership.open_some())

                    # Only owner can transfer ownership.
                    sp.verify(ownership_open.owner == sp.sender, ErrorMessages.only_owner())

                    # Set proposed owner.
                    ownership_open.proposed_owner = sp.some(transfer_ownership.new_owner)

                    # Update collection.
                    the_collection.ownership = sp.some(ownership_open)
                    self.data.collections[transfer_ownership.collection] = the_collection

                with arg.match("acccept_ownership") as acccept_ownership:
                    the_collection = sp.compute(self.data.collections.get(acccept_ownership, message = ErrorMessages.invalid_collection()))
                    sp.verify(the_collection.collection_type == collectionPrivate, ErrorMessages.not_private())
                    ownership_open = sp.compute(the_collection.ownership.open_some())

                    # Check that there is a proposed owner and
                    # check that the proposed owner executed the entry point.
                    sp.verify(sp.some(sp.sender) == ownership_open.proposed_owner, message=ErrorMessages.not_proposed_owner())

                    # Set the new owner address.
                    ownership_open.owner = sp.sender

                    # Reset the proposed owner value.
                    ownership_open.proposed_owner = sp.none

                    # Update collection
                    the_collection.ownership = sp.some(ownership_open)
                    self.data.collections[acccept_ownership] = the_collection


    #
    # Views
    #
    @sp.onchain_view(pure=True)
    def get_registered(self, contract_set):
        """Returns set of collections that are registered.
        
        Existance in set = inclusion."""
        sp.set_type(contract_set, t_registry_param)

        with sp.set_result_type(t_registry_result):
            result_set = sp.local("result_set", sp.set([]), t_registry_result)
            with sp.for_("contract", contract_set.elements()) as contract:
                with sp.if_(self.data.collections.contains(contract)):
                    result_set.value.add(contract)
            sp.result(result_set.value)


    @sp.onchain_view(pure=True)
    def only_registered(self, contract_set):
        """Fails if any of the contracts in `contract_set` aren't registered.
        Otherwise just returns unit."""
        sp.set_type(contract_set, t_registry_param)

        with sp.for_("contract", contract_set.elements()) as contract:
            with sp.if_(~self.data.collections.contains(contract)):
                sp.failwith("TOKEN_NOT_REGISTERED")
        sp.result(sp.unit)


    @sp.onchain_view(pure=True)
    def get_royalties_type(self, contract):
        """Returns the royalties type for a collections.
        
        Throws INVALID_COLLECTION if not a valid collection."""
        sp.set_type(contract, sp.TAddress)

        with sp.set_result_type(t_royalties_bounded):
            sp.result(self.data.collections.get(contract,
                message=ErrorMessages.invalid_collection()).royalties_type)


    @sp.onchain_view(pure=True)
    def get_collection_info(self, contract):
        """Returns the registry info for a collections.
        
        Throws INVALID_COLLECTION if not a valid collection."""
        sp.set_type(contract, sp.TAddress)

        with sp.set_result_type(collectionType):
            sp.result(self.data.collections.get(contract,
                message=ErrorMessages.invalid_collection()))


    @sp.onchain_view(pure=True)
    def is_private_owner_or_collab(self, params):
        """Returns owner|collaborator if address is collection owner or collaborator.

        Throws INVALID_COLLECTION if not a valid collection.
        Throws NOT_PRIVATE if not a private collection.
        Throws NOT_OWNER_OR_COLLABORATOR if neither owner nor collaborator."""
        sp.set_type(params, t_ownership_check)

        with sp.set_result_type(t_ownership_result):
            # Get private collection params.
            the_collection = sp.compute(self.data.collections.get(params.collection,
                message = ErrorMessages.invalid_collection()))
            sp.verify(the_collection.collection_type == collectionPrivate, ErrorMessages.not_private())

            # Return "owner" if owner.
            with sp.if_(the_collection.ownership.open_some(sp.unit).owner == params.address):
                sp.result(sp.bounded("owner"))
            with sp.else_():
                # Return "collaborator" if collaborator.
                with sp.if_(self.data.collaborators.contains(sp.record(collection = params.collection, collaborator = params.address))):
                    sp.result(sp.bounded("collaborator"))
                with sp.else_():
                    sp.failwith(ErrorMessages.not_owner_or_collaborator())


    @sp.onchain_view(pure=True)
    def get_collections_public_key(self):
        sp.result(self.data.settings.collections_public_key)
