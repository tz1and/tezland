import smartpy as sp

pause_mixin = sp.io.import_script_from_url("file:contracts/Pausable.py")
fa2_admin = sp.io.import_script_from_url("file:contracts/FA2_Administration.py")
upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
contract_metadata_mixin = sp.io.import_script_from_url("file:contracts/ContractMetadata.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")
token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")


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
# TODO: test update_settings

#
# Minter contract.
# NOTE: should be pausable for code updates.
class TL_Minter(
    contract_metadata_mixin.ContractMetadata,
    pause_mixin.Pausable,
    fa2_admin.FA2_Administration,
    upgradeable_mixin.Upgradeable,
    sp.Contract):
    def __init__(self, administrator, token_registry, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")

        self.init_storage(
            token_registry = token_registry
        )
        contract_metadata_mixin.ContractMetadata.__init__(self, administrator = administrator, metadata = metadata)
        pause_mixin.Pausable.__init__(self, administrator = administrator)
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
    def onlyOwnerPrivate(self, collection, address):
        # call registry view to check owner.
        sp.verify(sp.view("is_private_owner", self.data.token_registry,
            sp.set_type_expr(sp.record(
                collection = collection,
                address = address
            ), token_registry_contract.t_ownership_check),
            t = sp.TBool).open_some(), "ONLY_OWNER")

    def onlyOwnerOrCollaboratorPrivate(self, collection, address):
        # call registry view to check owner or collaborator.
        sp.verify(sp.view("is_private_owner_or_collab", self.data.token_registry,
            sp.set_type_expr(sp.record(
                collection = collection,
                address = address
            ), token_registry_contract.t_ownership_check),
            t = sp.TBool).open_some(), "ONLY_OWNER_OR_COLLABORATOR")

    def onlyPublicCollection(self, collection):
        # call registry view to check if public collection.
        sp.verify(sp.view("is_public_collection", self.data.token_registry,
            sp.set_type_expr([collection], sp.TList(sp.TAddress)),
            t = sp.TMap(sp.TAddress, sp.TBool)).open_some().get(collection, default_value=False), "INVALID_COLLECTION")

    #
    # Admin-only entry points
    #
    @sp.entry_point
    def pause_fa2(self, params):
        """The admin can pause/unpause item collection contracts."""
        sp.set_type(params, sp.TRecord(
            tokens = sp.TList(sp.TAddress),
            new_paused = sp.TBool))

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

        self.onlyAdministrator()
    
        with sp.for_("fa2", params) as fa2:
            # call items contract
            update_adhoc_operators_handle = sp.contract(FA2.t_adhoc_operator_params, fa2, 
                entry_point = "update_adhoc_operators").open_some()
                
            sp.transfer(sp.variant("clear_adhoc_operators", sp.unit),
                sp.mutez(0), update_adhoc_operators_handle)

    # TODO: test
    @sp.entry_point(lazify = True)
    def update_settings(self, params):
        """Allows the administrator to update the token registry."""
        sp.set_type(params, sp.TList(sp.TVariant(
            token_registry = sp.TAddress
        )))

        self.onlyAdministrator()

        with sp.for_("update", params) as update:
            with update.match_cases() as arg:
                # TODO: test
                with arg.match("token_registry") as address:
                    # TODO: does this make sure contract has token_registry ep?
                    #register_fa2_handle = sp.contract(sp.TList(sp.TAddress), contract, 
                    #    entry_point = "register_fa2").open_some()
                    #
                    #sp.transfer([], sp.mutez(0), register_fa2_handle)
                    self.data.token_registry = address

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
        self.onlyPublicCollection(params.collection)
        
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
    # Private entry points
    #
    @sp.entry_point(lazify = True)
    def update_private_metadata(self, params):
        """Private collection owner can update its metadata."""
        sp.set_type(params, sp.TRecord(
            collection = sp.TAddress,
            metadata_uri = sp.TBytes))

        self.onlyUnpaused()
        self.onlyOwnerPrivate(params.collection, sp.sender)
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
        self.onlyOwnerOrCollaboratorPrivate(params.collection, sp.sender)

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
