from importlib.metadata import metadata
import smartpy as sp

admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")
pause_mixin = sp.io.import_script_from_url("file:contracts/Pausable.py")
contract_metadata_mixin = sp.io.import_script_from_url("file:contracts/ContractMetadata.py")
upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
minter_contract = sp.io.import_script_from_url("file:contracts/TL_Minter_v2.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")


# TODO: figure out if entrypoints should be lazy!!!!
# TODO: originated FA2 admin should be the general minter!
# TODO: update_settings - token_registry: make sure contract has token_registry ep?
# TODO: update_settings - token_minter: make sure contract has mint eps?
# TODO: basic validation of the metadata? i.e. make sure it's an IPFS link
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
    def __init__(self, administrator, token_registry, token_minter, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")

        administrator = sp.set_type_expr(administrator, sp.TAddress)
        token_registry = sp.set_type_expr(token_registry, sp.TAddress)
        token_minter = sp.set_type_expr(token_minter, sp.TAddress)

        # NOTE: TODO: args don't matter here since we set storage on origination.
        self.collection_contract = tz1andCollection(metadata, administrator)
        
        self.init_storage(
            token_registry = token_registry,
            token_minter = token_minter
        )
        contract_metadata_mixin.ContractMetadata.__init__(self, administrator = administrator, metadata = metadata)
        pause_mixin.Pausable.__init__(self, administrator = administrator)
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
        """Allows the administrator to update the token registry,
        minter, etc"""
        sp.set_type(params, sp.TList(sp.TVariant(
            token_registry = sp.TAddress,
            token_minter = sp.TAddress
        )))

        self.onlyAdministrator()

        with sp.for_("update", params) as update:
            with update.match_cases() as arg:
                with arg.match("token_registry") as address:
                    # TODO: does this make sure contract has token_registry ep?
                    #register_fa2_handle = sp.contract(sp.TList(sp.TAddress), contract, 
                    #    entry_point = "register_fa2").open_some()
                    #
                    #sp.transfer([], sp.mutez(0), register_fa2_handle)
                    self.data.token_registry = address

                # TODO: test this
                with arg.match("token_minter") as address:
                    self.data.token_minter = address

    #
    # Public entry points
    #
    @sp.entry_point(lazify = True)
    def create_token(self, params):
        """Originate an FA2 token contract"""
        sp.set_type(params, sp.TRecord(
            metadata = sp.TBigMap(sp.TString, sp.TBytes)
        ))

        # Basic validation of the metadata, try to make sure it's a somewhat valid ipfs URI.
        # Ipfs cid v0 + proto is 53 chars.
        sp.verify((sp.slice(params.metadata[""], 0, 7).open_some("INVALID_METADATA") == sp.utils.bytes_of_string("ipfs://"))
            & (sp.len(params.metadata[""]) >= sp.nat(53)), "INVALID_METADATA")

        # Originate
        originated_token = sp.create_contract(contract = self.collection_contract, storage = sp.record(
            # The storage we need to modify
            administrator = self.data.token_minter,
            metadata = params.metadata,
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

        # Register with token registry
        register_fa2_handle = sp.contract(sp.TList(sp.TAddress), self.data.token_registry, 
            entry_point = "register_fa2").open_some()

        sp.transfer([originated_token], sp.mutez(0), register_fa2_handle)

        # Add private collection in minter v2
        manage_private_collections_handle = sp.contract(
            minter_contract.t_manage_private_collections,
            self.data.token_minter, 
            entry_point = "manage_private_collections").open_some()

        sp.transfer([sp.variant("add_collections", [sp.record(contract = originated_token, owner = sp.sender)])], sp.mutez(0), manage_private_collections_handle)
