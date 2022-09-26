import smartpy as sp

pause_mixin = sp.io.import_script_from_url("file:contracts/Pausable.py")
mod_mixin = sp.io.import_script_from_url("file:contracts/Moderation.py")
fa2_admin = sp.io.import_script_from_url("file:contracts/FA2_Administration.py")
upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
contract_metadata_mixin = sp.io.import_script_from_url("file:contracts/ContractMetadata.py")
basic_permissions_mixin = sp.io.import_script_from_url("file:contracts/BasicPermissions.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")


# TODO: collaborators for user collections. i.e. permissions for minting and maybe setting metadata.
#       could maybe do invitations? have a flag for invitation accepted. or maybe not...
# TODO: record of private and public collections.
# TODO: a way to add user collections, with permission checks. so factory can add collections.
# TODO: set metadata for public/private collections.
# TODO: decide laziness of entrypoints...
# TODO: make mixin for permissions
# TODO: should we address collections by id or by address???? shouldn't make a diff in bigmap keys...
# TODO: figure out if the minter should also be the token registry or have similar functionality, to be used by the token registry (which could be replaced as it's upgraded)
#       + maybe: token registry checks minter and also provides roylaties. that way the oncahin royalty provider (registry) can always be updated and can also use merkle
#         trees for objkt.com tokens, etc.
# TODO: private is weird nomenclature. rename to colleciton and public/shared collection maybe.
# TODO: test is_collection view.
# TODO: layouts!!!

privateCollectionValueType = sp.TRecord(
    owner = sp.TAddress,
    proposed_owner = sp.TOption(sp.TAddress))
privateCollectionMapType = sp.TBigMap(sp.TAddress, privateCollectionValueType)
privateCollectionMapLiteral = sp.big_map(tkey = sp.TAddress, tvalue = privateCollectionValueType)

publicCollectionMapType = sp.TBigMap(sp.TAddress, sp.TUnit)
publicCollectionMapLiteral = sp.big_map(tkey = sp.TAddress, tvalue = sp.TUnit)

collaboratorsKeyType = sp.TRecord(collection = sp.TAddress, collaborator = sp.TAddress).layout(("collection", "collaborator"))
collaboratorsMapType = sp.TBigMap(collaboratorsKeyType, sp.TUnit)
collaboratorsMapLiteral = sp.big_map(tkey = collaboratorsKeyType, tvalue = sp.TUnit)

t_manage_public_collections = sp.TList(sp.TVariant(
    add_collections = sp.TList(sp.TAddress),
    remove_collections = sp.TList(sp.TAddress)))

t_manage_private_collections = sp.TList(sp.TVariant(
    add_collections = sp.TList(sp.TRecord(
        contract = sp.TAddress,
        owner = sp.TAddress
    )),
    remove_collections = sp.TList(sp.TAddress)))

t_manage_collaborators = sp.TList(sp.TVariant(
    add_collaborators = sp.TRecord(
        collection = sp.TAddress,
        collaborators = sp.TList(sp.TAddress)),
    remove_collaborators = sp.TRecord(
        collection = sp.TAddress,
        collaborators = sp.TList(sp.TAddress))))

#
# Minter contract.
# NOTE: should be pausable for code updates.
class TL_Minter(
    contract_metadata_mixin.ContractMetadata,
    basic_permissions_mixin.BasicPermissions,
    pause_mixin.Pausable,
    mod_mixin.Moderation,
    fa2_admin.FA2_Administration,
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
        mod_mixin.Moderation.__init__(self, administrator = administrator)
        fa2_admin.FA2_Administration.__init__(self, administrator = administrator)
        upgradeable_mixin.Upgradeable.__init__(self, administrator = administrator)
        self.generate_contract_metadata()

    def generate_contract_metadata(self):
        """Generate a metadata json file with all the contract's offchain views
        and standard TZIP-12 and TZIP-016 key/values."""
        metadata_base = {
            "name": 'tz1and Minter',
            "description": 'tz1and Item Collection minter',
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
    # Admin-only entry points
    #
    @sp.entry_point
    def pause_fa2(self, params):
        """The admin can pause/unpause item collection contracts."""
        sp.set_type(params, sp.TRecord(
            tokens = sp.TList(sp.TAddress),
            new_paused = sp.TBool))

        #self.onlyUnpaused() # TODO
        self.onlyAdministrator()

        with sp.for_("fa2", params.tokens) as fa2:
            # call items contract
            set_paused_handle = sp.contract(sp.TBool, fa2, 
                entry_point = "set_pause").open_some()
                
            sp.transfer(params.new_paused, sp.mutez(0), set_paused_handle)

    @sp.entry_point
    def clear_adhoc_operators_fa2(self, params):
        """The admin can clear adhoc ops for item collections."""
        sp.set_type(params, sp.TList(sp.TAddress))

        #self.onlyUnpaused() # TODO
        self.onlyAdministrator()
    
        with sp.for_("fa2", params) as fa2:
            # call items contract
            update_adhoc_operators_handle = sp.contract(FA2.t_adhoc_operator_params, fa2, 
                entry_point = "update_adhoc_operators").open_some()
                
            sp.transfer(sp.variant("clear_adhoc_operators", sp.unit),
                sp.mutez(0), update_adhoc_operators_handle)

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
    # Public entry points
    #
    @sp.entry_point(lazify = True)
    def mint_public(self, params):
        """Minting items in a public collection"""
        sp.set_type(params, sp.TRecord(
            collection = sp.TAddress,
            to_ = sp.TAddress,
            amount = sp.TNat,
            royalties = sp.TNat,
            contributors = FA2.t_contributor_list,
            metadata = sp.TBytes
        ).layout(("collection", ("to_", ("amount", ("royalties", ("contributors", "metadata")))))))

        self.onlyUnpaused()
        
        sp.verify((params.amount > 0) & (params.amount <= 10000) & ((params.royalties >= 0) & (params.royalties <= 250)),
            message = "PARAM_ERROR")

        # make sure collection is indeed a public collection
        sp.verify(self.data.public_collections.contains(params.collection) == True, message = "INVALID_COLLECTION")

        utils.fa2_fungible_royalties_mint(
            [sp.record(
                to_=params.to_,
                amount=params.amount,
                token=sp.variant("new", sp.record(
                    metadata={ '' : params.metadata },
                    royalties=sp.record(
                        royalties=params.royalties,
                        contributors=params.contributors)
                    )
                )
            )],
            params.collection
        )

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

        # Check that there is a proposed owner
        sp.verify(the_collection.proposed_owner.is_some(), message="NO_OWNER_TRANSFER")

        # Check that the proposed owner executed the entry point
        sp.verify(sp.sender == the_collection.proposed_owner.open_some(), message="NOT_PROPOSED_OWNER")

        # Set the new owner address
        the_collection.owner = sp.sender

        # Reset the proposed owner value
        the_collection.proposed_owner = sp.none

    @sp.entry_point(lazify = True)
    def update_private_metadata(self, params):
        """Private collection owner can update its metadata."""
        sp.set_type(params, sp.TRecord(
            collection = sp.TAddress,
            metadata_uri = sp.TBytes))

        self.onlyUnpaused()
        self.onlyOwnerPrivate(params.collection)
        utils.validate_ipfs_uri(params.metadata_uri)

        utils.contract_set_metadata(params.collection, params.metadata_uri)

    @sp.entry_point(lazify = True)
    def mint_private(self, params):
        """Minting items in a private collection."""
        sp.set_type(params, sp.TRecord(
            collection = sp.TAddress,
            to_ = sp.TAddress,
            amount = sp.TNat,
            royalties = sp.TNat,
            contributors = FA2.t_contributor_list,
            metadata = sp.TBytes
        ).layout(("collection", ("to_", ("amount", ("royalties", ("contributors", "metadata")))))))

        self.onlyUnpaused()
        self.onlyOwnerOrCollaboratorPrivate(params.collection)

        sp.verify((params.amount > 0) & (params.amount <= 10000) & ((params.royalties >= 0) & (params.royalties <= 250)),
            message = "PARAM_ERROR")

        utils.fa2_fungible_royalties_mint(
            [sp.record(
                to_=params.to_,
                amount=params.amount,
                token=sp.variant("new", sp.record(
                    metadata={ '' : params.metadata },
                    royalties=sp.record(
                        royalties=params.royalties,
                        contributors=params.contributors)
                    )
                )
            )],
            params.collection
        )

    #
    # Views
    #
    @sp.onchain_view(pure=True)
    def is_collection(self, contract):
        """Returns true if contract is a collection, false otherwise."""
        sp.set_type(contract, sp.TAddress)
        with sp.set_result_type(sp.TBool):
            sp.result(self.data.private_collections.contains(contract) | self.data.public_collections.contains(contract))