from importlib.metadata import metadata
import smartpy as sp

admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")
pause_mixin = sp.io.import_script_from_url("file:contracts/Pausable.py")
contract_metadata_mixin = sp.io.import_script_from_url("file:contracts/ContractMetadata.py")
upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
token_registry_contract = sp.io.import_script_from_url("file:contracts/TL_TokenRegistry.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")


# TODO: figure out if entrypoints should be lazy!!!!
# TODO: figure out if we *need* FA2.PauseTransfer()

#
# The template FA2 contract.
class tz1andCollection(
    admin_mixin.Administrable,
    FA2.ChangeMetadata,
    FA2.MintFungible,
    FA2.BurnFungible,
    FA2.Royalties,
    FA2.Fa2Fungible,
):
    """tz1and Collection"""

    def __init__(self, metadata, admin):
        admin = sp.set_type_expr(admin, sp.TAddress)

        FA2.Fa2Fungible.__init__(
            self, metadata=metadata,
            name="tz1and Collection", description="tz1and Item Collection.",
            # TODO: figure out if we *need* FA2.PauseTransfer()
            # It might be good to have, simply for security reasons...
            # Then again, if the FA2 is borked, pausing is destructive to value as well.
            # But one could migrate to another FA2 before all value is lost. So maybe worth it...
            policy=FA2.PauseTransfer(FA2.OwnerOrOperatorAdhocTransfer()), has_royalties=True,
            allow_mint_existing=False
        )
        FA2.Royalties.__init__(self)
        admin_mixin.Administrable.__init__(self, admin)

#
# TokenFactory contract.
# NOTE: should be pausable for code updates.
class TL_TokenFactory(
    contract_metadata_mixin.ContractMetadata,
    pause_mixin.Pausable,
    upgradeable_mixin.Upgradeable,
    sp.Contract):
    def __init__(self, administrator, token_registry, minter, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")

        administrator = sp.set_type_expr(administrator, sp.TAddress)
        token_registry = sp.set_type_expr(token_registry, sp.TAddress)
        minter = sp.set_type_expr(minter, sp.TAddress)

        # NOTE: TODO: args don't matter here since we set storage on origination.
        self.collection_contract = tz1andCollection(metadata, administrator)
        
        self.init_storage(
            token_registry = token_registry,
            minter = minter
        )

        self.available_settings = [
            ("token_registry", sp.TAddress, None),
            ("minter", sp.TAddress, None)
        ]

        contract_metadata_mixin.ContractMetadata.__init__(self, administrator = administrator, metadata = metadata, meta_settings = True)
        pause_mixin.Pausable.__init__(self, administrator = administrator, meta_settings = True)
        upgradeable_mixin.Upgradeable.__init__(self, administrator = administrator)
        self.generate_contract_metadata()

    def generate_contract_metadata(self):
        """Generate a metadata json file with all the contract's offchain views
        and standard TZIP-12 and TZIP-016 key/values."""
        metadata_base = {
            "name": 'tz1and TokenFactory',
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
    # Admin-only entry points
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
    # Public entry points
    #
    @sp.entry_point(lazify = True)
    def create_token(self, metadata_uri):
        """Originate an FA2 token contract"""
        sp.set_type(metadata_uri, sp.TBytes)

        self.onlyUnpaused()

        utils.validate_ipfs_uri(metadata_uri)

        # Originate FA2
        originated_token = sp.create_contract(contract = self.collection_contract, storage = sp.record(
            # The storage we need to modify
            administrator = self.data.minter,
            metadata = sp.big_map({"": metadata_uri}),
            # Just the default values
            adhoc_operators = sp.set(),
            last_token_id = 0,
            ledger = sp.big_map(),
            operators = sp.big_map(),
            paused = False,
            proposed_administrator = sp.none,
            token_extra = sp.big_map(),
            token_metadata = sp.big_map()
        ))

        # Add private collection in token registry
        manage_private_collections_handle = sp.contract(
            token_registry_contract.t_manage_private_collections,
            self.data.token_registry, 
            entry_point = "manage_private_collections").open_some()

        # TODO: currently creates tokens with version 1.
        # MAKE SURE THIS IS CORRECT!!!!
        sp.transfer([sp.variant("add_collections", [sp.record(contract = originated_token, owner = sp.sender, royalties_version = 2)])], sp.mutez(0), manage_private_collections_handle)
