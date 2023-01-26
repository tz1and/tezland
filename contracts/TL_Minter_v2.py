import smartpy as sp

from tz1and_contracts_smartpy.mixins.Administrable import Administrable
from tz1and_contracts_smartpy.mixins.Pausable import Pausable
from tz1and_contracts_smartpy.mixins.Upgradeable import Upgradeable
from tz1and_contracts_smartpy.mixins.ContractMetadata import ContractMetadata, contractSetMetadata
from tz1and_contracts_smartpy.mixins.MetaSettings import MetaSettings

from contracts import TL_TokenRegistry, FA2
from contracts.utils import ErrorMessages
from tz1and_contracts_smartpy.utils import Utils


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
    def __init__(self, administrator, registry, metadata, version="2.0.0", exception_optimization_level="default-line"):
        sp.Contract.__init__(self)

        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")

        self.init_storage()

        self.addMetaSettings([
            ("registry", registry, sp.TAddress, lambda x : Utils.onlyContract(x)),
            ("max_contributors", 3, sp.TNat, lambda x : sp.verify(x >= sp.nat(1), ErrorMessages.parameter_error())),
            ("max_royalties", 250, sp.TNat, None)
        ])

        Administrable.__init__(self, administrator = administrator, include_views = False)
        Pausable.__init__(self, include_views = False)
        ContractMetadata.__init__(self, metadata = metadata)
        MetaSettings.__init__(self)
        Upgradeable.__init__(self)

        self.generateContractMetadata("tz1and Minter", "tz1and Item Collection minter",
            authors=["852Kerfunkle <https://github.com/852Kerfunkle>"],
            source_location="https://github.com/tz1and",
            homepage="https://www.tz1and.com", license="UNLICENSED",
            version=version)


    #
    # Some inline helpers
    #
    def onlyOwnerPrivate(self, collection, address):
        sp.verify(TL_TokenRegistry.isPrivateOwnerOrCollab(
            self.data.settings.registry, collection, address) == sp.some(sp.bounded("owner")), ErrorMessages.only_owner())


    def onlyOwnerOrCollaboratorPrivate(self, collection, address):
        sp.compute(TL_TokenRegistry.isPrivateOwnerOrCollab(self.data.settings.registry, collection, address)
            .open_some())


    def onlyPublicCollection(self, collection):
        # call registry view to check if public collection.
        sp.verify(TL_TokenRegistry.getCollectionInfo(self.data.settings.registry, collection)
            .open_some().collection_type == TL_TokenRegistry.collectionPublic, ErrorMessages.not_public())


    #
    # Admin-only/owner-only entry points
    #
    @sp.entry_point(lazify = True)
    def token_administration(self, params):
        sp.set_type(params, sp.TList(sp.TVariant(
            transfer_fa2_administrator = sp.TMap(sp.TAddress, sp.TAddress), # contract to proposed admin
            accept_fa2_administrator = sp.TSet(sp.TAddress), # set of contracts
            update_collection_metadata = sp.TMap(sp.TAddress, sp.TBytes), # contract to metadata uri as bytes
            clear_adhoc_operators = sp.TSet(sp.TAddress), # set of contracts
            pause = sp.TMap(sp.TAddress, sp.TBool) # contract to new paused state
        ).layout(("transfer_fa2_administrator", ("accept_fa2_administrator",
            ("update_collection_metadata", ("clear_adhoc_operators", "pause")))))))

        # Must be administrator.
        self.onlyAdministrator()

        with sp.for_("task", params) as task:
            with task.match_cases() as arg:
                with arg.match("transfer_fa2_administrator") as transfer_fa2_administrator:
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
                    with sp.for_("fa2", clear_adhoc_operators.elements()) as fa2:
                        # call items contract
                        update_adhoc_operators_handle = sp.contract(FA2.t_adhoc_operator_params, fa2, 
                            entry_point = "update_adhoc_operators").open_some()
                            
                        sp.transfer(sp.variant("clear_adhoc_operators", sp.unit),
                            sp.mutez(0), update_adhoc_operators_handle)

                with arg.match("pause") as pause:
                    with sp.for_("contract_item", pause.items()) as contract_item:
                        # call items contract
                        set_paused_handle = sp.contract(sp.TBool, contract_item.key, 
                            entry_point = "set_pause").open_some()
                            
                        sp.transfer(contract_item.value, sp.mutez(0), set_paused_handle)

                with arg.match("update_collection_metadata") as update_collection_metadata:
                    # Admin can update metadata of any collection owned by minter
                    with sp.for_("contract_item", update_collection_metadata.items()) as contract_item:
                        Utils.validateIpfsUri(contract_item.value)
                        contractSetMetadata(contract_item.key, contract_item.value)


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

        sp.verify((params.amount > 0) & (params.amount <= 10000), message = ErrorMessages.parameter_error())

        FA2.validateRoyalties(params.royalties, self.data.settings.max_royalties, self.data.settings.max_contributors)

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
    @sp.entry_point(lazify=True, parameter_type=sp.TMap(sp.TAddress, sp.TBytes)) # contract to metadata uri as bytes
    def update_private_metadata(self, params):
        """Allow private collection owners to update their collections metadata."""
        self.onlyUnpaused()

        with sp.for_("contract_item", params.items()) as contract_item:
            # Must be private owner.
            self.onlyOwnerPrivate(contract_item.key, sp.sender)
            Utils.validateIpfsUri(contract_item.value)

            contractSetMetadata(contract_item.key, contract_item.value)


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

        sp.verify((params.amount > 0) & (params.amount <= 10000), message = ErrorMessages.parameter_error())

        FA2.validateRoyalties(params.royalties, self.data.settings.max_royalties, self.data.settings.max_contributors)

        FA2.fa2_fungible_royalties_mint(
            [sp.record(
                to_=params.to_,
                amount=params.amount,
                token=sp.variant("new", sp.record(
                    metadata={ '' : params.metadata },
                    royalties=params.royalties))
            )],
            params.collection)
