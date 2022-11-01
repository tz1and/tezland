import smartpy as sp

pause_mixin = sp.io.import_script_from_url("file:contracts/Pausable.py")
upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
contract_metadata_mixin = sp.io.import_script_from_url("file:contracts/ContractMetadata.py")
basic_permissions_mixin = sp.io.import_script_from_url("file:contracts/BasicPermissions.py")
merkle_tree = sp.io.import_script_from_url("file:contracts/MerkleTree.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")


# TODO: store information about a contracts royalties?
# TODO: convert tz1and royalties to the more common decimals and shares format? (see fa2 metadata)
# TODO: merkle tree for royalties - test
# TODO: merkle tree for registry - test
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
# TODO: finish get_token_royalties view
# TODO: test update_settings
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

# View params
t_ownership_check = sp.TRecord(
    collection = sp.TAddress,
    address = sp.TAddress).layout(("collection", "address"))

t_registry_param = sp.TList(sp.TAddress)
t_registry_merkle_param = sp.TList(merkle_tree.t_fa2_with_merkle_proof)
t_registry_result = sp.TMap(sp.TAddress, sp.TBool)

t_get_token_royalties = sp.TRecord(
    fa2 = sp.TAddress,
    token_id = sp.TNat,
    merkle_proof = sp.TOption(merkle_tree.royalties.MerkleProofType)
).layout(("fa2", ("token_id", "merkle_proof")))

#
# Token registry contract.
# NOTE: should be pausable for code updates.
class TL_TokenRegistry(
    contract_metadata_mixin.ContractMetadata,
    basic_permissions_mixin.BasicPermissions,
    pause_mixin.Pausable,
    upgradeable_mixin.Upgradeable,
    sp.Contract):
    def __init__(self, administrator, royalties_merkle_root, collections_merkle_root, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")

        royalties_merkle_root = sp.set_type_expr(royalties_merkle_root, sp.TBytes)
        collections_merkle_root = sp.set_type_expr(collections_merkle_root, sp.TBytes)

        self.init_storage(
            private_collections = privateCollectionMapLiteral,
            public_collections = publicCollectionMapLiteral,
            collaborators = collaboratorsMapLiteral,
            royalties_merkle_root = royalties_merkle_root,
            collections_merkle_root = collections_merkle_root
        )

        self.available_settings = [
            ("royalties_merkle_root", sp.TBytes, None),
            ("collections_merkle_root", sp.TBytes, None)
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
    def update_settings(self, params):
        """Allows the administrator to update various settings.
        
        Parameters are metaprogrammed with self.available_settings"""
        sp.set_type(params, sp.TList(sp.TVariant(
            **{setting[0]: setting[1] for setting in self.available_settings})))

        # NOTE: Currently this means updating the merkle tree root nodes
        # would require admin permissions, which is tricky, should this
        # ever be automated. But in that case this ep can be upgraded.
        self.onlyAdministrator()

        with sp.for_("update", params) as update:
            with update.match_cases() as arg:
                for setting in self.available_settings:
                    with arg.match(setting[0]) as value:
                        if setting[2] != None:
                            setting[2](value)
                        setattr(self.data, setting[0], value)

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
    def is_registered(self, contract_list):
        # TODO: should we store royalty-type information with registered tokens?
        """Returns true if contract is registered, false otherwise."""
        sp.set_type(contract_list, t_registry_merkle_param)

        with sp.set_result_type(t_registry_result):
            result_map = sp.local("result_map", {}, t_registry_result)

            with sp.for_("contract", contract_list) as contract:
                with contract.merkle_proof.match_cases() as arg:
                    with arg.match("None"):
                        result_map.value[contract.fa2] = self.data.private_collections.contains(contract.fa2) | self.data.public_collections.contains(contract.fa2)

                    with arg.match("Some") as proof_open:
                        # Make sure leaf matches input.
                        sp.verify(contract.fa2 == merkle_tree.collections.unpack_leaf(proof_open.leaf), "LEAF_DATA_DOES_NOT_MATCH")
                        # Registered state true if merkle proof is valid.
                        result_map.value[contract.fa2] = merkle_tree.collections.validate_merkle_root(proof_open.proof, proof_open.leaf, self.data.collections_merkle_root)

            sp.result(result_map.value)

    @sp.onchain_view(pure=True)
    def is_private_collection(self, contract_list):
        """Returns true if contract is a private collection, false otherwise."""
        sp.set_type(contract_list, t_registry_param)

        with sp.set_result_type(t_registry_result):
            result_map = sp.local("result_map", {}, t_registry_result)
            with sp.for_("contract", contract_list) as contract:
                result_map.value[contract] = self.data.private_collections.contains(contract)
            sp.result(result_map.value)

    @sp.onchain_view(pure=True)
    def is_public_collection(self, contract_list):
        """Returns true if contract is a public collection, false otherwise."""
        sp.set_type(contract_list, t_registry_param)

        with sp.set_result_type(t_registry_result):
            result_map = sp.local("result_map", {}, t_registry_result)
            with sp.for_("contract", contract_list) as contract:
                result_map.value[contract] = self.data.public_collections.contains(contract)
            sp.result(result_map.value)

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

    @sp.onchain_view(pure=True)
    def get_token_royalties(self, params):
        sp.set_type(params, t_get_token_royalties)

        # returns v2 royalties format
        with sp.set_result_type(FA2.t_royalties_v2):
            # If a merkle proof is supplied
            with params.merkle_proof.match_cases() as arg:
                with arg.match("Some") as merkle_proof_open:
                    # for which royalties are requested.
                    # Verify that the computed merkle root from proof matches the actual merkle root
                    sp.verify(merkle_tree.royalties.validate_merkle_root(merkle_proof_open.proof, merkle_proof_open.leaf, self.data.royalties_merkle_root),
                        "INVALID_MERKLE_PROOF")

                    # TODO: leaf should match fa and token id. so it can be varified against the token.
                    unpacked_leaf = sp.compute(merkle_tree.royalties.unpack_leaf(merkle_proof_open.leaf))
                    sp.verify((params.fa2 == unpacked_leaf.fa2) & (params.token_id == unpacked_leaf.token_id), "LEAF_DATA_DOES_NOT_MATCH")

                    sp.result(unpacked_leaf.token_royalties)

                with arg.match("None"):
                    # TODO: check if token is registered and valid, if it is, return royalties.
                    # based on roylties type defined in registry.
                    #with sp.if_(is_v1_royalties):
                    #    # TODO: convert v1 to v2 royalties.
                    #    royalties = sp.none
                    #    sp.result(royalties)
                    #with sp.else_():
                    with sp.if_(self.data.private_collections.contains(params.fa2) | self.data.public_collections.contains(params.fa2)):
                        royalties = sp.compute(utils.tz1and_items_get_royalties(params.fa2, params.token_id))

                        royalties_v2 = sp.local("royalties_v2", sp.record(decimals = 3, shares = []), FA2.t_royalties_v2)

                        with sp.for_("contributor", royalties.contributors) as contributor:
                            royalties_v2.value.shares.push(sp.record(
                                address = contributor.address,
                                share = contributor.relative_royalties * royalties.royalties / 1000))

                        sp.result(royalties_v2.value)

                        # TODO: if v2 royalties, just return those.
                    with sp.else_():
                        sp.failwith("INVALID_COLLECTION")
