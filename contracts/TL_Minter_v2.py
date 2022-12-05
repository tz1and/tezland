import smartpy as sp

Administrable = sp.io.import_script_from_url("file:contracts/mixins/Administrable.py").Administrable
Pausable = sp.io.import_script_from_url("file:contracts/mixins/Pausable.py").Pausable
Upgradeable = sp.io.import_script_from_url("file:contracts/mixins/Upgradeable.py").Upgradeable
ContractMetadata = sp.io.import_script_from_url("file:contracts/mixins/ContractMetadata.py").ContractMetadata
MetaSettings = sp.io.import_script_from_url("file:contracts/mixins/MetaSettings.py").MetaSettings

token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")
FA2_legacy = sp.io.import_script_from_url("file:contracts/legacy/FA2_legacy.py")
utils = sp.io.import_script_from_url("file:contracts/utils/Utils.py")


# TODO: test update_settings: registry, max_contributors, max_royalties

#
# Minter contract.
# NOTE: should be pausable for code updates.
class TL_Minter_v2(
    Administrable,
    ContractMetadata,
    Pausable,
    MetaSettings,
    Upgradeable,
    sp.Contract):
    def __init__(self, administrator, registry, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")

        self.init_storage(
            registry = registry,
            max_contributors = sp.nat(3),
            max_royalties = sp.nat(250)
        )

        self.available_settings = [
            ("registry", sp.TAddress, lambda x : utils.onlyContract(x)),
            ("max_contributors", sp.TNat, lambda x : sp.verify(x >= sp.nat(1), "PARAM_ERROR")),
            ("max_royalties", sp.TNat, None)
        ]

        Administrable.__init__(self, administrator = administrator, include_views = False)
        Pausable.__init__(self, include_views = False)
        ContractMetadata.__init__(self, metadata = metadata)
        MetaSettings.__init__(self)
        Upgradeable.__init__(self)

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
    # Some inline helpers
    #
    def onlyOwnerPrivate(self, collection, address):
        # call registry view to check owner.
        sp.verify(sp.view("is_private_owner_or_collab", self.data.registry,
            sp.set_type_expr(sp.record(
                collection = collection,
                address = address
            ), token_registry_contract.t_ownership_check),
            t = token_registry_contract.t_ownership_result) == sp.some(sp.bounded("owner")), "ONLY_OWNER")


    def onlyOwnerOrCollaboratorPrivate(self, collection, address):
        # call registry view to check owner or collaborator.
        sp.compute(sp.view("is_private_owner_or_collab", self.data.registry,
            sp.set_type_expr(sp.record(
                collection = collection,
                address = address
            ), token_registry_contract.t_ownership_check),
            t = token_registry_contract.t_ownership_result).open_some())


    def getCollectionInfo(self, collection):
        # call registry view to check if public collection.
        return sp.view("get_collection_info", self.data.registry,
            sp.set_type_expr(collection, sp.TAddress),
            t = token_registry_contract.collectionType).open_some()

    def onlyPublicCollection(self, collection):
        # call registry view to check if public collection.
        sp.verify(
            self.getCollectionInfo(collection).collection_type == token_registry_contract.collectionPublic,
            "NOT_PUBLIC")


    #
    # Admin-only/owner-only entry points
    #
    @sp.entry_point(lazify = True)
    def token_administration(self, params):
        sp.set_type(params, sp.TList(sp.TVariant(
            transfer_fa2_administrator = sp.TMap(sp.TAddress, sp.TAddress), # contract to proposed admin
            accept_fa2_administrator = sp.TSet(sp.TAddress), # set of contracts
            update_private_metadata = sp.TMap(sp.TAddress, sp.TBytes), # contract to metadata uri as bytes
            clear_adhoc_operators = sp.TSet(sp.TAddress), # set of contracts
            pause = sp.TMap(sp.TAddress, sp.TBool) # contract to new paused state
        ).layout(("transfer_fa2_administrator", ("accept_fa2_administrator",
            ("update_private_metadata", ("clear_adhoc_operators", "pause")))))))

        with sp.for_("task", params) as task:
            with task.match_cases() as arg:
                with arg.match("transfer_fa2_administrator") as transfer_fa2_administrator:
                    # Must be administrator.
                    self.onlyAdministrator()

                    with sp.for_("transfer_item", transfer_fa2_administrator.items()) as transfer_item:
                        # Get a handle on the FA2 contract transfer_administator entry point
                        fa2_transfer_administrator_handle = sp.contract(
                            t=sp.TAddress,
                            address=transfer_item.key,
                            entry_point="transfer_administrator").open_some()

                        # Propose to transfer the FA2 token contract administrator
                        sp.transfer(
                            arg=transfer_item.value,
                            amount=sp.mutez(0),
                            destination=fa2_transfer_administrator_handle)

                with arg.match("accept_fa2_administrator") as accept_fa2_administrator:
                    # Must be administrator.
                    self.onlyAdministrator()

                    with sp.for_("fa2", accept_fa2_administrator.elements()) as fa2:
                        # Get a handle on the FA2 contract accept_administrator entry point
                        fa2_accept_administrator_handle = sp.contract(
                            t=sp.TUnit,
                            address=fa2,
                            entry_point="accept_administrator").open_some()

                        # Accept the FA2 token contract administrator responsabilities
                        sp.transfer(
                            arg=sp.unit,
                            amount=sp.mutez(0),
                            destination=fa2_accept_administrator_handle)

                with arg.match("clear_adhoc_operators") as clear_adhoc_operators:
                    # Must be administrator.
                    self.onlyAdministrator()

                    with sp.for_("fa2", clear_adhoc_operators.elements()) as fa2:
                        # call items contract
                        update_adhoc_operators_handle = sp.contract(FA2.t_adhoc_operator_params, fa2, 
                            entry_point = "update_adhoc_operators").open_some()
                            
                        sp.transfer(sp.variant("clear_adhoc_operators", sp.unit),
                            sp.mutez(0), update_adhoc_operators_handle)

                with arg.match("pause") as pause:
                    # Must be administrator.
                    self.onlyAdministrator()

                    with sp.for_("contract_item", pause.items()) as contract_item:
                        # call items contract
                        set_paused_handle = sp.contract(sp.TBool, contract_item.key, 
                            entry_point = "set_pause").open_some()
                            
                        sp.transfer(contract_item.value, sp.mutez(0), set_paused_handle)

                with arg.match("update_private_metadata") as update_private_metadata:
                    self.onlyUnpaused()

                    with sp.for_("contract_item", update_private_metadata.items()) as contract_item:
                        # Must be private owner.
                        self.onlyOwnerPrivate(contract_item.key, sp.sender)
                        utils.validateIpfsUri(contract_item.value)

                        utils.contractSetMetadata(contract_item.key, contract_item.value)


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
            royalties = FA2.t_royalties_shares,
            metadata = sp.TBytes
        ).layout(("collection", ("to_", ("amount", ("royalties", "metadata"))))))

        self.onlyUnpaused()
        self.onlyPublicCollection(params.collection)

        sp.verify((params.amount > 0) & (params.amount <= 10000), message = "PARAM_ERROR")

        FA2.validateRoyalties(params.royalties, self.data.max_royalties, self.data.max_contributors)

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

        FA2.validateRoyalties(params.royalties, self.data.max_royalties, self.data.max_contributors)

        FA2.fa2_fungible_royalties_mint(
            [sp.record(
                to_=params.to_,
                amount=params.amount,
                token=sp.variant("new", sp.record(
                    metadata={ '' : params.metadata },
                    royalties=params.royalties))
            )],
            params.collection)
