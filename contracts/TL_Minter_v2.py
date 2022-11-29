import smartpy as sp

admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")
pause_mixin = sp.io.import_script_from_url("file:contracts/Pausable.py")
fa2_admin = sp.io.import_script_from_url("file:contracts/FA2_Administration.py")
upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
contract_metadata_mixin = sp.io.import_script_from_url("file:contracts/ContractMetadata.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")
FA2_legacy = sp.io.import_script_from_url("file:contracts/legacy/FA2_legacy.py")
token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")


# TODO: decide laziness of entrypoints...
# TODO: test update_settings
# TODO: update_private_metadata is probably a registry task.

#
# Minter contract.
# NOTE: should be pausable for code updates.
class TL_Minter(
    admin_mixin.Administrable,
    contract_metadata_mixin.ContractMetadata,
    pause_mixin.Pausable,
    fa2_admin.FA2_Administration,
    upgradeable_mixin.Upgradeable,
    sp.Contract):
    def __init__(self, administrator, registry, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")

        self.init_storage(
            registry = registry
        )

        self.available_settings = [
            ("registry", sp.TAddress, None)
        ]

        admin_mixin.Administrable.__init__(self, administrator = administrator)
        pause_mixin.Pausable.__init__(self, meta_settings = True)
        contract_metadata_mixin.ContractMetadata.__init__(self, metadata = metadata, meta_settings = True)
        fa2_admin.FA2_Administration.__init__(self)
        upgradeable_mixin.Upgradeable.__init__(self)

        self.generate_contract_metadata()

    def generate_contract_metadata(self):
        """Generate a metadata json file with all the contract's offchain views."""
        metadata_base = {
            "name": 'tz1and Minter',
            "description": 'tz1and Item Collection minter',
            "version": "2.0.0",
            "interfaces": ["TZIP-016"],
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
    # Some constants
    #
    MAX_ROYALTIES = sp.nat(250)
    MAX_CONTRIBUTORS = sp.nat(3)

    #
    # Some inline helpers
    #
    def onlyOwnerPrivate(self, collection, address):
        # call registry view to check owner.
        sp.verify(sp.view("is_private_owner_or_collab", self.data.registry,
            sp.set_type_expr(sp.record(
                collection = collection,
                address = address
            ), token_registry_contract.t_ownership_check),
            t = token_registry_contract.t_ownership_result).open_some() == sp.bounded("owner"), "ONLY_OWNER")

    def onlyOwnerOrCollaboratorPrivate(self, collection, address):
        # call registry view to check owner or collaborator.
        sp.compute(sp.view("is_private_owner_or_collab", self.data.registry,
            sp.set_type_expr(sp.record(
                collection = collection,
                address = address
            ), token_registry_contract.t_ownership_check),
            t = token_registry_contract.t_ownership_result).open_some())

    def onlyPublicCollection(self, collection):
        # call registry view to check if public collection.
        sp.verify(sp.view("get_collection_info", self.data.registry,
            sp.set_type_expr(collection, sp.TAddress),
            t = token_registry_contract.collectionType).open_some()
            .collection_type == token_registry_contract.collectionPublic, "NOT_PUBLIC")

    #
    # Admin-only entry points
    #
    @sp.entry_point
    def pause_fa2(self, params):
        """The admin can pause/unpause item collection contracts."""
        sp.set_type(params, sp.TMap(sp.TAddress, sp.TBool))

        self.onlyAdministrator()

        with sp.for_("contract_item", params.items()) as contract_item:
            # call items contract
            set_paused_handle = sp.contract(sp.TBool, contract_item.key, 
                entry_point = "set_pause").open_some()
                
            sp.transfer(contract_item.value, sp.mutez(0), set_paused_handle)

    @sp.entry_point
    def clear_adhoc_operators_fa2(self, params):
        """The admin can clear adhoc ops for item collections."""
        sp.set_type(params, sp.TSet(sp.TAddress))

        self.onlyAdministrator()
    
        with sp.for_("fa2", params.elements()) as fa2:
            # call items contract
            update_adhoc_operators_handle = sp.contract(FA2.t_adhoc_operator_params, fa2, 
                entry_point = "update_adhoc_operators").open_some()
                
            sp.transfer(sp.variant("clear_adhoc_operators", sp.unit),
                sp.mutez(0), update_adhoc_operators_handle)

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
    @sp.entry_point(lazify = True)
    def mint_public_v1(self, params):
        """Minting items in the v1 public collection"""
        sp.set_type(params, sp.TRecord(
            collection = sp.TAddress,
            to_ = sp.TAddress,
            amount = sp.TNat,
            royalties = sp.TNat,
            contributors = FA2_legacy.t_contributor_list,
            metadata = sp.TBytes
        ).layout(("collection", ("to_", ("amount", ("royalties", ("contributors", "metadata")))))))

        self.onlyUnpaused()
        self.onlyPublicCollection(params.collection)
        
        sp.verify((params.amount > 0) & (params.amount <= 10000), message = "PARAM_ERROR")

        # NOTE: legacy FA2 royalties are validated in the legacy FA2 contract

        FA2_legacy.fa2_fungible_royalties_mint(
            [sp.record(
                to_=params.to_,
                amount=params.amount,
                token=sp.variant("new", sp.record(
                    metadata={ '' : params.metadata },
                    royalties=sp.record(
                        royalties=params.royalties,
                        contributors=params.contributors)))
            )],
            params.collection)

    @sp.entry_point(lazify = True)
    def mint_public(self, params):
        """Minting items in a public collection"""
        sp.set_type(params, sp.TRecord(
            collection = sp.TAddress,
            to_ = sp.TAddress,
            amount = sp.TNat,
            royalties = FA2.t_royalties_shares,
            metadata = sp.TBytes
        ).layout(("collection", ("to_", ("amount", ("royalties", "metadata"))))))

        self.onlyUnpaused()
        self.onlyPublicCollection(params.collection)
        
        sp.verify((params.amount > 0) & (params.amount <= 10000), message = "PARAM_ERROR")

        FA2.validateRoyalties(params.royalties, self.MAX_ROYALTIES, self.MAX_CONTRIBUTORS)

        FA2.fa2_fungible_royalties_mint(
            [sp.record(
                to_=params.to_,
                amount=params.amount,
                token=sp.variant("new", sp.record(
                    metadata={ '' : params.metadata },
                    royalties=params.royalties))
            )],
            params.collection)

    #
    # Private entry points
    #
    @sp.entry_point(lazify = True)
    def update_private_metadata(self, params):
        """Private collection owner can update its metadata."""
        sp.set_type(params, sp.TRecord(
            collection = sp.TAddress,
            metadata_uri = sp.TBytes
        ).layout(("collection", "metadata_uri")))

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
            royalties = FA2.t_royalties_shares,
            metadata = sp.TBytes
        ).layout(("collection", ("to_", ("amount", ("royalties", "metadata"))))))

        self.onlyUnpaused()
        self.onlyOwnerOrCollaboratorPrivate(params.collection, sp.sender)

        sp.verify((params.amount > 0) & (params.amount <= 10000), message = "PARAM_ERROR")

        FA2.validateRoyalties(params.royalties, self.MAX_ROYALTIES, self.MAX_CONTRIBUTORS)

        FA2.fa2_fungible_royalties_mint(
            [sp.record(
                to_=params.to_,
                amount=params.amount,
                token=sp.variant("new", sp.record(
                    metadata={ '' : params.metadata },
                    royalties=params.royalties))
            )],
            params.collection)
