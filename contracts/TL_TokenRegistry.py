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
# TODO: t_royalties_signed: decide if data should be packed or not.


privateCollectionValueType = sp.TRecord(
    owner = sp.TAddress,
    proposed_owner = sp.TOption(sp.TAddress),
    royalties_version = sp.TNat
).layout(("owner", ("proposed_owner", "royalties_version")))
privateCollectionMapType = sp.TBigMap(sp.TAddress, privateCollectionValueType)
privateCollectionMapLiteral = sp.big_map(tkey = sp.TAddress, tvalue = privateCollectionValueType)

publicCollectionMapType = sp.TBigMap(sp.TAddress, sp.TNat)
publicCollectionMapLiteral = sp.big_map(tkey = sp.TAddress, tvalue = sp.TNat)

collaboratorsKeyType = sp.TRecord(collection = sp.TAddress, collaborator = sp.TAddress).layout(("collection", "collaborator"))
collaboratorsMapType = sp.TBigMap(collaboratorsKeyType, sp.TUnit)
collaboratorsMapLiteral = sp.big_map(tkey = collaboratorsKeyType, tvalue = sp.TUnit)

t_manage_public_collections = sp.TList(sp.TVariant(
    add = sp.TList(sp.TRecord(
        contract = sp.TAddress,
        royalties_version = sp.TNat
    ).layout(("contract", "royalties_version"))),
    remove = sp.TList(sp.TAddress)
).layout(("add", "remove")))

t_manage_private_collections = sp.TList(sp.TVariant(
    add = sp.TList(sp.TRecord(
        contract = sp.TAddress,
        owner = sp.TAddress,
        royalties_version = sp.TNat
    ).layout(("contract", ("owner", "royalties_version")))),
    remove = sp.TList(sp.TAddress)
).layout(("add", "remove")))

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
t_registry_result = sp.TMap(sp.TAddress, sp.TBool)
t_registry_result_with_pubkey = sp.TRecord(
    result_map = sp.TMap(sp.TAddress, sp.TBool),
    #merkle_root = sp.TBytes,
    public_key = sp.TKey
).layout(("result_map", "public_key"))

t_get_royalties_type_result = sp.TNat

#
# Collections "Trusted" - signed offchain.
#

# Don't need the address here, because it's the map key map.
t_collection_signed = sp.TSignature


def sign_collection(address, private_key):
    address = sp.set_type_expr(address, sp.TAddress)
    # Gives: Type format error atom secret_key
    #private_key = sp.set_type_expr(private_key, sp.TSecretKey)

    packed_collection = sp.pack(address)

    signature = sp.make_signature(
        private_key,
        packed_collection,
        message_format = 'Raw')

    return signature


@sp.inline_result
def getTokenRegistryInfoSigned(token_registry_contract, fa2_list, signed_registries = sp.none, check_signed_registries: bool = True):
    """Get token registry info and/or validate signed registry."""
    sp.set_type(token_registry_contract, sp.TAddress)
    sp.set_type(fa2_list, t_registry_param)
    sp.set_type(signed_registries, sp.TOption(sp.TMap(sp.TAddress, t_collection_signed)))
    registry_info = sp.local("registry_info", sp.view("is_registered", token_registry_contract,
        sp.set_type_expr(
            fa2_list,
            t_registry_param),
        t = t_registry_result_with_pubkey).open_some())

    if check_signed_registries:
        with signed_registries.match("Some") as signed_registries_open:
            with sp.for_("item", signed_registries_open.items()) as item:
                # Verify signature
                sp.verify(sp.check_signature(registry_info.value.public_key, item.value, sp.pack(item.key)), "INVALID_SIGNATURE")
                # Registered state true if signature is valid.
                registry_info.value.result_map[item.key] = True
    
    sp.result(registry_info.value.result_map)


##
## Merkle trees
#
## Tree classes
#merkle_tree_royalties = MerkleTree(t_royalties_offchain)
#merkle_tree_collections = MerkleTree(sp.TAddress)
#
#
#@sp.inline_result
#def getTokenRegistryInfoMerkle(token_registry_contract, fa2_list, merkle_proofs = sp.none, check_merkle_proofs: bool = True):
#    """Get token registry info and validate registry merkle proofs."""
#    sp.set_type(token_registry_contract, sp.TAddress)
#    sp.set_type(fa2_list, t_registry_param)
#    sp.set_type(merkle_proofs, sp.TOption(sp.TMap(sp.TAddress, merkle_tree_collections.MerkleProofType)))
#    registry_info = sp.local("registry_info", sp.view("is_registered", token_registry_contract,
#        sp.set_type_expr(
#            fa2_list,
#            t_registry_param),
#        t = t_registry_result_with_merkle_root_and_pubkey).open_some())
#
#    if check_merkle_proofs:
#        with merkle_proofs.match("Some") as merkle_proofs_open:
#            with sp.for_("item", merkle_proofs_open.items()) as item:
#                # Make sure leaf matches input.
#                sp.verify(item.key == merkle_tree_collections.unpack_leaf(item.value.leaf), "LEAF_DATA_DOES_NOT_MATCH")
#                # Registered state true if merkle proof is valid.
#                registry_info.value.result_map[item.key] = merkle_tree_collections.validate_merkle_root(item.value.proof, item.value.leaf, registry_info.value.merkle_root)
#    
#    sp.result(registry_info.value.result_map)
#
#
#@sp.inline_result
#def getTokenRoyaltiesMerkle(token_registry_contract, fa2, token_id, merkle_proof):
#    """Gets token royalties and validate royalties merkle proofs."""
#    sp.set_type(token_registry_contract, sp.TAddress)
#    sp.set_type(fa2, sp.TAddress)
#    sp.set_type(token_id, sp.TNat)
#    sp.set_type(merkle_proof, sp.TOption(merkle_tree_royalties.MerkleProofType))
#    royalties_type = sp.local("royalties_type", sp.view("get_royalties_type", token_registry_contract,
#        fa2, t = t_get_royalties_type_result).open_some())
#
#    with sp.if_(royalties_type.value.royalties_version == 0):
#        merkle_proof_open = sp.compute(merkle_proof.open_some("NO_MERKLE_PROOF"))
#        # for which royalties are requested.
#        # Verify that the computed merkle root from proof matches the actual merkle root
#        sp.verify(merkle_tree_royalties.validate_merkle_root(merkle_proof_open.proof, merkle_proof_open.leaf, royalties_type.value.merkle_root),
#            "INVALID_MERKLE_PROOF")
#
#        # Leaf should match fa and token id. so it can be verified against the token.
#        unpacked_leaf = sp.compute(merkle_tree_royalties.unpack_leaf(merkle_proof_open.leaf))
#        sp.verify((fa2 == unpacked_leaf.fa2) & (token_id == unpacked_leaf.token_id), "LEAF_DATA_DOES_NOT_MATCH")
#        sp.result(unpacked_leaf.token_royalties)
#
#    with sp.else_():
#        with sp.if_(royalties_type.value.royalties_version == 1):
#            royalties = sp.compute(FA2_legacy.get_token_royalties(fa2, token_id))
#            royalties_v2 = sp.local("royalties_v2", sp.record(total = 1000, shares = []), FA2.t_royalties_interop)
#
#            with sp.for_("contributor", royalties.contributors) as contributor:
#                royalties_v2.value.shares.push(sp.record(
#                    address = contributor.address,
#                    share = contributor.relative_royalties * royalties.royalties / 1000))
#
#            sp.result(royalties_v2.value)
#        with sp.else_():
#            with sp.if_(royalties_type.value.royalties_version == 2):
#                sp.result(FA2.get_token_royalties(fa2, token_id))
#            with sp.else_():
#                sp.failwith("ROYALTIES_NOT_IMPLEMENTED")


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
        self.add_flag("erase-comments")

        #royalties_merkle_root = sp.set_type_expr(royalties_merkle_root, sp.TBytes)
        #collections_merkle_root = sp.set_type_expr(collections_merkle_root, sp.TBytes)

        collections_public_key = sp.set_type_expr(collections_public_key, sp.TKey)

        self.init_storage(
            private_collections = privateCollectionMapLiteral,
            public_collections = publicCollectionMapLiteral,
            collaborators = collaboratorsMapLiteral,
            #royalties_merkle_root = royalties_merkle_root,
            #collections_merkle_root = collections_merkle_root,
            collections_public_key = collections_public_key
        )

        self.available_settings = [
            #("royalties_merkle_root", sp.TBytes, None),
            #("collections_merkle_root", sp.TBytes, None),
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
        # get owner from private collection map and check owner
        collection_props = self.data.private_collections.get(collection, message = "INVALID_COLLECTION")
        sp.verify((collection_props.owner == sp.sender), "ONLY_OWNER")

    def onlyOwnerPrivateGet(self, collection):
        # get owner from private collection map and check owner
        collection_props = sp.compute(self.data.private_collections.get(collection, message = "INVALID_COLLECTION"))
        sp.verify((collection_props.owner == sp.sender), "ONLY_OWNER")
        return collection_props

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
                with arg.match("add") as add:
                    with sp.for_("address", add) as collection:
                        # public collections cant be private
                        sp.verify(self.data.private_collections.contains(collection.contract) == False, "PUBLIC_PRIVATE")
                        self.data.public_collections[collection.contract] = collection.royalties_version

                with arg.match("remove") as remove:
                    with sp.for_("address", remove) as address:
                        del self.data.public_collections[address]

    @sp.entry_point(lazify = True)
    def manage_private_collections(self, params):
        """Admin or permitted can add/remove private collections in minter"""
        sp.set_type(params, t_manage_private_collections)

        self.onlyUnpaused()
        self.onlyAdministratorOrPermitted()

        with sp.for_("upd", params) as upd:
            with upd.match_cases() as arg:
                with arg.match("add") as add:
                    with sp.for_("collection", add) as collection:
                        # private collections cant be public
                        sp.verify(self.data.public_collections.contains(collection.contract) == False, "PUBLIC_PRIVATE")
                        self.data.private_collections[collection.contract] = sp.record(
                            owner = collection.owner,
                            proposed_owner = sp.none,
                            royalties_version = collection.royalties_version)

                with arg.match("remove") as remove:
                    with sp.for_("address", remove) as address:
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
        the_collection = self.onlyOwnerPrivateGet(params.collection)

        # Set proposed owner
        the_collection.proposed_owner = sp.some(params.new_owner)

        # Update collection
        self.data.private_collections[params.collection] = the_collection

    @sp.entry_point(lazify = True)
    def accept_private_ownership(self, collection):
        """The proposed collection owner accepts the responsabilities."""
        sp.set_type(collection, sp.TAddress)

        self.onlyUnpaused()

        the_collection = sp.compute(self.data.private_collections.get(collection, message = "INVALID_COLLECTION"))

        # Check that there is a proposed owner and
        # check that the proposed owner executed the entry point
        sp.verify(sp.some(sp.sender) == the_collection.proposed_owner, message="NOT_PROPOSED_OWNER")

        # Set the new owner address
        the_collection.owner = sp.sender

        # Reset the proposed owner value
        the_collection.proposed_owner = sp.none

        # Update collection
        self.data.private_collections[collection] = the_collection

    #
    # Views
    #
    @sp.onchain_view(pure=True)
    def is_registered(self, contract_list):
        # TODO: should we store royalty-type information with registered tokens?
        """Returns true if contract is registered, false otherwise."""
        sp.set_type(contract_list, t_registry_param)

        with sp.set_result_type(t_registry_result_with_pubkey):
            result_map = sp.local("result_map", {}, t_registry_result)
            with sp.for_("contract", contract_list) as contract:
                result_map.value[contract] = self.data.private_collections.contains(contract) | self.data.public_collections.contains(contract)
            sp.result(sp.record(
                result_map = result_map.value,
                #merkle_root = self.data.collections_merkle_root,
                public_key = self.data.collections_public_key))

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
    def get_royalties_type(self, fa2):
        sp.set_type(fa2, sp.TAddress)

        with sp.set_result_type(t_get_royalties_type_result):
            royalties_version = sp.local("royalties_version", sp.nat(0))

            public_opt = self.data.public_collections.get_opt(fa2)
            with public_opt.match_cases() as public_arg:
                with public_arg.match("Some") as public_some:
                    royalties_version.value = public_some

                with public_arg.match("None", "public_none"):
                    private_opt = self.data.private_collections.get_opt(fa2)

                    with private_opt.match("Some") as private_some:
                        royalties_version.value = private_some.royalties_version

            sp.result(royalties_version.value)

#    @sp.onchain_view(pure=True)
#    def get_collections_merkle_root(self):
#        sp.result(self.data.collections_merkle_root)
#
#    @sp.onchain_view(pure=True)
#    def get_royalties_merkle_root(self):
#        sp.result(self.data.royalties_merkle_root)

    @sp.onchain_view(pure=True)
    def get_collections_public_key(self):
        sp.result(self.data.collections_public_key)