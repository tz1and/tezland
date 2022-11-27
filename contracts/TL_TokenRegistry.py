import smartpy as sp

pause_mixin = sp.io.import_script_from_url("file:contracts/Pausable.py")
upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
contract_metadata_mixin = sp.io.import_script_from_url("file:contracts/ContractMetadata.py")
basic_permissions_mixin = sp.io.import_script_from_url("file:contracts/BasicPermissions.py")
#MerkleTree = sp.io.import_script_from_url("file:contracts/MerkleTree.py").MerkleTree
utils = sp.io.import_script_from_url("file:contracts/Utils.py")


# TODO: can drastically optimise the size by not having the admin/contract metadata mixins. Maybe useful to optimise.
# TODO: decide laziness of entrypoints...
# TODO: private is weird nomenclature. rename to colleciton and public/shared collection maybe.
# TODO: test update_settings
# TODO: layouts!!!
# TODO: signed collection should allow every user to add a collection with a royalties type.
# TODO: BULLSHIT


# Know royalties types:
# 0 - legacy royalties
# 1 - tz1and V1
# 2 - tz1and V2

ownershipInfo = sp.TOption(sp.TRecord(
    owner = sp.TAddress,
    proposed_owner = sp.TOption(sp.TAddress),
).layout(("owner", "proposed_owner")))

# Collection types for bouded type.
collectionPrivate   = sp.bounded(sp.nat(0))
collectionPublic    = sp.bounded(sp.nat(1))
collectionTrusted   = sp.bounded(sp.nat(2))

collectionType = sp.TRecord(
    royalties_type = sp.TNat,
    collection_type = sp.TBounded([0, 1, 2], sp.TNat),
    ownership = ownershipInfo
).layout(("royalties_type", ("collection_type", "ownership")))

collectionMapLiteral = sp.big_map(tkey = sp.TAddress, tvalue = collectionType)

manageCollectionVariant = sp.TVariant(
    add_private = sp.TMap(sp.TAddress, sp.TRecord(
        owner = sp.TAddress,
        royalties_type = sp.TNat
    ).layout(("owner", "royalties_type"))),
    add_public = sp.TMap(sp.TAddress, sp.TNat),
    add_trusted = sp.TMap(sp.TAddress, sp.TRecord(
        signature = sp.TSignature,
        royalties_type = sp.TNat
    ).layout(("signature", "royalties_type"))),
    remove = sp.TSet(sp.TAddress)
).layout(("add_private", ("add_public", ("add_trusted", "remove"))))

t_manage_collections = sp.TList(manageCollectionVariant)

collaboratorsKeyType = sp.TRecord(collection = sp.TAddress, collaborator = sp.TAddress).layout(("collection", "collaborator"))
collaboratorsMapLiteral = sp.big_map(tkey = collaboratorsKeyType, tvalue = sp.TUnit)

adminPrivateCollectionVariant = sp.TVariant(
    add_collaborators = sp.TRecord(
        collection = sp.TAddress,
        collaborators = sp.TSet(sp.TAddress)
    ).layout(("collection", "collaborators")),
    remove_collaborators = sp.TRecord(
        collection = sp.TAddress,
        collaborators = sp.TSet(sp.TAddress)
    ).layout(("collection", "collaborators")),
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

t_get_royalties_type_result = sp.TNat

#
# Collections "Trusted" - signed offchain.
#

# Don't need the address here, because it's the map key map.
t_collection_sign = sp.TRecord(
    collection=sp.TAddress,
    royalties_type=sp.TNat
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


def isRegistered(token_registry_contract: sp.TAddress, fa2_set: sp.TSet):
    sp.set_type(token_registry_contract, sp.TAddress)
    sp.set_type(fa2_set, sp.TSet(sp.TAddress))
    return sp.compute(sp.view("is_registered", token_registry_contract,
        sp.set_type_expr(
            fa2_set,
            t_registry_param),
        t = t_registry_result).open_some())


def checkRegistered(token_registry_contract: sp.TAddress, fa2_set: sp.TSet):
    sp.set_type(token_registry_contract, sp.TAddress)
    sp.set_type(fa2_set, sp.TSet(sp.TAddress))
    sp.compute(sp.view("check_registered", token_registry_contract,
        sp.set_type_expr(
            fa2_set,
            t_registry_param),
        t = sp.TUnit).open_some())


#
# Token registry contract.
# NOTE: should be pausable for code updates.
class TL_TokenRegistry(
    contract_metadata_mixin.ContractMetadata,
    basic_permissions_mixin.BasicPermissions,
    pause_mixin.Pausable,
    upgradeable_mixin.Upgradeable,
    sp.Contract):
    def __init__(self, administrator, collections_public_key, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        #self.add_flag("erase-comments")

        collections_public_key = sp.set_type_expr(collections_public_key, sp.TKey)

        self.init_storage(
            collections = collectionMapLiteral,
            collaborators = collaboratorsMapLiteral,
            collections_public_key = collections_public_key
        )

        self.available_settings = [
            ("collections_public_key", sp.TKey, None)
        ]

        contract_metadata_mixin.ContractMetadata.__init__(self, administrator = administrator, metadata = metadata, meta_settings = True)
        basic_permissions_mixin.BasicPermissions.__init__(self, administrator = administrator)
        pause_mixin.Pausable.__init__(self, administrator = administrator, meta_settings = True)
        upgradeable_mixin.Upgradeable.__init__(self, administrator = administrator)
        self.generate_contract_metadata()

    def generate_contract_metadata(self):
        """Generate a metadata json file with all the contract's offchain views
        and standard TZIP-12 and TZIP-016 key/values."""
        metadata_base = {
            "name": 'tz1and TokenRegistry',
            "description": 'tz1and token registry',
            "version": "1.0.0",
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

    #
    # Some inline helpers
    #
    def onlyOwnerPrivate(self, collection):
        # Get owner from private collection map and check owner
        the_collection = sp.compute(self.data.collections.get(collection, message = "INVALID_COLLECTION"))
        sp.verify(the_collection.collection_type == collectionPrivate, "NOT_PRIVATE")
        # CHeck owner.
        sp.verify(the_collection.ownership.open_some().owner == sp.sender, "ONLY_OWNER")

    #
    # Admin and permitted entry points
    #
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
                        sp.verify(~self.data.collections.contains(add_private_item.key), "COLLECTION_EXISTS")
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
                        sp.verify(~self.data.collections.contains(add_public_item.key), "COLLECTION_EXISTS")
                        self.data.collections[add_public_item.key] = sp.record(
                            royalties_type = add_public_item.value,
                            collection_type = collectionPublic,
                            ownership = sp.none)

                with arg.match("add_trusted") as add_trusted:
                    # Anyone can add_trusted. If the signature is valid.
                    with sp.for_("add_trusted_item", add_trusted.items()) as add_trusted_item:
                        # You cannot add collections that already exist
                        sp.verify(~self.data.collections.contains(add_trusted_item.key), "COLLECTION_EXISTS")

                        # Validate signature!
                        sp.verify(sp.check_signature(self.data.collections_public_key,
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
                    self.onlyOwnerPrivate(add_collaborators.collection)
                    with sp.for_("address", add_collaborators.collaborators.elements()) as address:
                        self.data.collaborators[sp.record(collection = add_collaborators.collection, collaborator = address)] = sp.unit

                with arg.match("remove_collaborators") as remove_collaborators:
                    self.onlyOwnerPrivate(remove_collaborators.collection)
                    with sp.for_("address", remove_collaborators.collaborators.elements()) as address:
                        del self.data.collaborators[sp.record(collection = remove_collaborators.collection, collaborator = address)]

                with arg.match("transfer_ownership") as transfer_ownership:
                    the_collection = sp.compute(self.data.collections.get(transfer_ownership.collection, message = "INVALID_COLLECTION"))
                    sp.verify(the_collection.collection_type == collectionPrivate, "NOT_PRIVATE")
                    ownership_open = sp.compute(the_collection.ownership.open_some())

                    # Only owner can transfer ownership.
                    sp.verify(ownership_open.owner == sp.sender, "ONLY_OWNER")

                    # Set proposed owner.
                    ownership_open.proposed_owner = sp.some(transfer_ownership.new_owner)

                    # Update collection.
                    the_collection.ownership = sp.some(ownership_open)
                    self.data.collections[transfer_ownership.collection] = the_collection

                with arg.match("acccept_ownership") as acccept_ownership:
                    the_collection = sp.compute(self.data.collections.get(acccept_ownership, message = "INVALID_COLLECTION"))
                    sp.verify(the_collection.collection_type == collectionPrivate, "NOT_PRIVATE")
                    ownership_open = sp.compute(the_collection.ownership.open_some())

                    # Check that there is a proposed owner and
                    # check that the proposed owner executed the entry point.
                    sp.verify(sp.some(sp.sender) == ownership_open.proposed_owner, message="NOT_PROPOSED_OWNER")

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
    def is_registered(self, contract_set):
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
    def check_registered(self, contract_set):
        """Fails with TOKEN_NOT_REGISTERED if any of the contracts aren't.
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

        with sp.set_result_type(sp.TNat):
            sp.result(self.data.collections.get(contract, message="INVALID_COLLECTION").royalties_type)


    @sp.onchain_view(pure=True)
    def get_collection_info(self, contract):
        """Returns the registry info for a collections.
        
        Throws INVALID_COLLECTION if not a valid collection."""
        sp.set_type(contract, sp.TAddress)

        with sp.set_result_type(collectionType):
            sp.result(self.data.collections.get(contract, message="INVALID_COLLECTION"))


    @sp.onchain_view(pure=True)
    def is_private_owner_or_collab(self, params):
        """Returns owner|collaborator if address is collection owner or collaborator.

        Throws INVALID_COLLECTION if not a valid collection.
        Throws NOT_PRIVATE if not a private collection.
        Throws NOT_OWNER_OR_COLLABORATOR if neither owner nor collaborator."""
        sp.set_type(params, t_ownership_check)

        with sp.set_result_type(t_ownership_result):
            # Get private collection params.
            the_collection = sp.compute(self.data.collections.get(params.collection, message = "INVALID_COLLECTION"))
            sp.verify(the_collection.collection_type == collectionPrivate, "NOT_PRIVATE")

            # Return "owner" if owner.
            with sp.if_(the_collection.ownership.open_some().owner == params.address):
                sp.result(sp.bounded("owner"))
            with sp.else_():
                # Return "collaborator" if collaborator.
                with sp.if_(self.data.collaborators.contains(sp.record(collection = params.collection, collaborator = params.address))):
                    sp.result(sp.bounded("collaborator"))
                with sp.else_():
                    sp.failwith("NOT_OWNER_OR_COLLABORATOR")


    @sp.onchain_view(pure=True)
    def get_collections_public_key(self):
        sp.result(self.data.collections_public_key)
