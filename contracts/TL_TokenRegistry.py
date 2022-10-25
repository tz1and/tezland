import smartpy as sp

pause_mixin = sp.io.import_script_from_url("file:contracts/Pausable.py")
upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
contract_metadata_mixin = sp.io.import_script_from_url("file:contracts/ContractMetadata.py")
basic_permissions_mixin = sp.io.import_script_from_url("file:contracts/BasicPermissions.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")


# TODO: store information about a contracts royalties?
# TODO: convert tz1and royalties to the more common decimals and shares format? (see fa2 metadata)
# TODO: add support for merkle tree to check for supported tokens? object.com, etc...
# TODO: can drastically optimise the size by not having the admin/contract metadata mixins. Maybe useful to optimise.
# TODO: decide laziness of entrypoints...
# TODO: should we address collections by id or by address???? shouldn't make a diff in bigmap keys...
#       but makes a small difference in gas when deserialising ops. in turn would mean world would have to use collection IDs.
# TODO: figure out if the minter should also be the token registry or have similar functionality, to be used by the token registry (which could be replaced as it's upgraded)
#       + maybe: token registry checks minter and also provides roylaties. that way the oncahin royalty provider (registry) can always be updated and can also use merkle
#         trees for objkt.com tokens, etc.
# TODO: private is weird nomenclature. rename to colleciton and public/shared collection maybe.
# TODO: *should* split registry bit into TokenRegistry to make the registry smaller to call. (without all the minter stuff).
#       might need a layer on top of the registry anyway, for the merkle tree stuff. can always add that later.
#       both world and minter would then use registry to check for inclusion. probably cheaper for world to only call registry.
#       Gotta see how it actually works out in terms of size.
# TODO: layouts!!!

privateCollectionValueType = sp.TRecord(
    owner = sp.TAddress,
    proposed_owner = sp.TOption(sp.TAddress)).layout(("owner", "proposed_owner"))
privateCollectionMapType = sp.TBigMap(sp.TAddress, privateCollectionValueType)
privateCollectionMapLiteral = sp.big_map(tkey = sp.TAddress, tvalue = privateCollectionValueType)

publicCollectionMapType = sp.TBigMap(sp.TAddress, sp.TUnit)
publicCollectionMapLiteral = sp.big_map(tkey = sp.TAddress, tvalue = sp.TUnit)

collaboratorsKeyType = sp.TRecord(collection = sp.TAddress, collaborator = sp.TAddress).layout(("collection", "collaborator"))
collaboratorsMapType = sp.TBigMap(collaboratorsKeyType, sp.TUnit)
collaboratorsMapLiteral = sp.big_map(tkey = collaboratorsKeyType, tvalue = sp.TUnit)

t_manage_public_collections = sp.TList(sp.TVariant(
    add_collections = sp.TList(sp.TAddress),
    remove_collections = sp.TList(sp.TAddress)
).layout(("add_collections", "remove_collections")))

t_manage_private_collections = sp.TList(sp.TVariant(
    add_collections = sp.TList(sp.TRecord(
        contract = sp.TAddress,
        owner = sp.TAddress
    ).layout(("contract", "owner"))),
    remove_collections = sp.TList(sp.TAddress)
).layout(("add_collections", "remove_collections")))

t_manage_collaborators = sp.TList(sp.TVariant(
    add_collaborators = sp.TRecord(
        collection = sp.TAddress,
        collaborators = sp.TList(sp.TAddress)).layout(("collection", "collaborators")),
    remove_collaborators = sp.TRecord(
        collection = sp.TAddress,
        collaborators = sp.TList(sp.TAddress)).layout(("collection", "collaborators"))
).layout(("add_collaborators", "remove_collaborators")))

t_ownership_check = sp.TRecord(
    collection = sp.TAddress,
    address = sp.TAddress).layout(("collection", "address"))

#
# Token registry contract.
# NOTE: should be pausable for code updates.
class TL_TokenRegistry(
    contract_metadata_mixin.ContractMetadata,
    basic_permissions_mixin.BasicPermissions,
    pause_mixin.Pausable,
    upgradeable_mixin.Upgradeable,
    sp.Contract):
    def __init__(self, administrator, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")

        self.init_storage(
            private_collections = privateCollectionMapLiteral,
            public_collections = publicCollectionMapLiteral,
            collaborators = collaboratorsMapLiteral
        )
        contract_metadata_mixin.ContractMetadata.__init__(self, administrator = administrator, metadata = metadata)
        basic_permissions_mixin.BasicPermissions.__init__(self, administrator = administrator)
        pause_mixin.Pausable.__init__(self, administrator = administrator)
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
        # get owner from private collection map and check owner
        collection_props = self.data.private_collections.get(collection, message = "INVALID_COLLECTION")
        sp.verify((collection_props.owner == sp.sender), "ONLY_OWNER")

    def onlyOwnerOrCollaboratorPrivate(self, collection):
        # get owner from private collection map and check owner or collaborator
        collection_props = self.data.private_collections.get(collection, message = "INVALID_COLLECTION")
        sp.verify((collection_props.owner == sp.sender) | (self.data.collaborators.contains(sp.record(collection = collection, collaborator = sp.sender))), "ONLY_OWNER_OR_COLLABORATOR")

    #
    # Admin and permitted entry points
    #
    @sp.entry_point(lazify = True)
    def manage_public_collections(self, params):
        """Admin or permitted can add/remove public collections in minter"""
        sp.set_type(params, t_manage_public_collections)

        self.onlyUnpaused()
        self.onlyAdministratorOrPermitted()

        with sp.for_("upd", params) as upd:
            with upd.match_cases() as arg:
                with arg.match("add_collections") as add_collections:
                    with sp.for_("address", add_collections) as address:
                        # public collections cant be private
                        sp.verify(self.data.private_collections.contains(address) == False, "PUBLIC_PRIVATE")
                        self.data.public_collections[address] = sp.unit

                with arg.match("remove_collections") as remove_collections:
                    with sp.for_("address", remove_collections) as address:
                        del self.data.public_collections[address]

    @sp.entry_point(lazify = True)
    def manage_private_collections(self, params):
        """Admin or permitted can add/remove private collections in minter"""
        sp.set_type(params, t_manage_private_collections)

        self.onlyUnpaused()
        self.onlyAdministratorOrPermitted()

        with sp.for_("upd", params) as upd:
            with upd.match_cases() as arg:
                with arg.match("add_collections") as add_collections:
                    with sp.for_("collection", add_collections) as collection:
                        # private collections cant be public
                        sp.verify(self.data.public_collections.contains(collection.contract) == False, "PUBLIC_PRIVATE")
                        self.data.private_collections[collection.contract] = sp.record(owner = collection.owner, proposed_owner = sp.none)

                with arg.match("remove_collections") as remove_collections:
                    with sp.for_("address", remove_collections) as address:
                        del self.data.private_collections[address]

    #
    # Private entry points
    #
    @sp.entry_point(lazify = True)
    def manage_collaborators(self, params):
        """User can add/remove collaborators to private collections"""
        sp.set_type(params, t_manage_collaborators)

        self.onlyUnpaused()

        with sp.for_("upd", params) as upd:
            with upd.match_cases() as arg:
                with arg.match("add_collaborators") as add_collaborators:
                    self.onlyOwnerPrivate(add_collaborators.collection)
                    with sp.for_("address", add_collaborators.collaborators) as address:
                        self.data.collaborators[sp.record(collection = add_collaborators.collection, collaborator = address)] = sp.unit

                with arg.match("remove_collaborators") as remove_collaborators:
                    self.onlyOwnerPrivate(remove_collaborators.collection)
                    with sp.for_("address", remove_collaborators.collaborators) as address:
                        del self.data.collaborators[sp.record(collection = remove_collaborators.collection, collaborator = address)]

    @sp.entry_point(lazify = True)
    def transfer_private_ownership(self, params):
        """Proposes to transfer the collection ownership to another address."""
        sp.set_type(params, sp.TRecord(
            collection = sp.TAddress,
            new_owner = sp.TAddress))

        self.onlyUnpaused()
        self.onlyOwnerPrivate(params.collection)

        self.data.private_collections[params.collection].proposed_owner = sp.some(params.new_owner)

    @sp.entry_point(lazify = True)
    def accept_private_ownership(self, collection):
        """The proposed collection owner accepts the responsabilities."""
        sp.set_type(collection, sp.TAddress)

        self.onlyUnpaused()

        the_collection = self.data.private_collections[collection]

        # Check that there is a proposed owner and
        # check that the proposed owner executed the entry point
        sp.verify(sp.some(sp.sender) == the_collection.proposed_owner, message="NOT_PROPOSED_OWNER")

        # Set the new owner address
        the_collection.owner = sp.sender

        # Reset the proposed owner value
        the_collection.proposed_owner = sp.none

    #
    # Views
    #
    @sp.onchain_view(pure=True)
    def is_registered(self, contract):
        # TODO: should we store royalty-type information with registered tokens?
        """Returns true if contract is registered, false otherwise."""
        sp.set_type(contract, sp.TAddress)
        with sp.set_result_type(sp.TBool):
            sp.result(self.data.private_collections.contains(contract) | self.data.public_collections.contains(contract))

    @sp.onchain_view(pure=True)
    def is_private_collection(self, contract):
        """Returns true if contract is a private collection, false otherwise."""
        sp.set_type(contract, sp.TAddress)
        with sp.set_result_type(sp.TBool):
            sp.result(self.data.private_collections.contains(contract))

    @sp.onchain_view(pure=True)
    def is_public_collection(self, contract):
        """Returns true if contract is a public collection, false otherwise."""
        sp.set_type(contract, sp.TAddress)
        with sp.set_result_type(sp.TBool):
            sp.result(self.data.public_collections.contains(contract))

    @sp.onchain_view(pure=True)
    def is_private_owner(self, params):
        """Returns true if address is collection owner, false otherwise.
        Throws INVALID_COLLECTION if collection not in private collections."""
        sp.set_type(params, t_ownership_check)

        with sp.set_result_type(sp.TBool):
            collection_props = self.data.private_collections.get(params.collection, message="INVALID_COLLECTION")
            sp.result(collection_props.owner == params.address)

    @sp.onchain_view(pure=True)
    def is_private_owner_or_collab(self, params):
        """Returns true if address is collection owner or operator, false otherwise.
        Throws INVALID_COLLECTION if collection not in private collections."""
        sp.set_type(params, t_ownership_check)

        with sp.set_result_type(sp.TBool):
            collection_props = self.data.private_collections.get(params.collection, message="INVALID_COLLECTION")
            sp.result((collection_props.owner == params.address) | (self.data.collaborators.contains(sp.record(collection = params.collection, collaborator = params.address))))
