import smartpy as sp

from tz1and_contracts_smartpy.mixins.Administrable import Administrable
from tz1and_contracts_smartpy.mixins.Pausable import Pausable
from tz1and_contracts_smartpy.mixins.Upgradeable import Upgradeable
from tz1and_contracts_smartpy.mixins.ContractMetadata import ContractMetadata
from tz1and_contracts_smartpy.mixins.MetaSettings import MetaSettings
from contracts.mixins.Fees import Fees

from contracts import TL_TokenRegistry, TL_RoyaltiesAdapter
from contracts.utils import FA2Utils, ErrorMessages
from tz1and_contracts_smartpy.utils import Utils


# Optional ext argument type.
# Map val can contain about anything and be
# unpacked with sp.unpack.
extensionArgType = sp.TOption(sp.TMap(sp.TString, sp.TBytes))

t_swap_key_partial = sp.TRecord(
    fa2 = sp.TAddress,
    token_id = sp.TNat,
    price = sp.TMutez,
    primary = sp.TBool
).layout(("fa2", ("token_id", ("price", "primary"))))

t_swap_key = sp.TRecord(
    id = sp.TNat,
    owner = sp.TAddress,
    partial = t_swap_key_partial
).layout(("id", ("owner", "partial")))

#
# Marketplace contract
# NOTE: should be pausable for code updates.
class TL_Marketplace(
    Administrable,
    ContractMetadata,
    Pausable,
    Fees,
    Upgradeable,
    MetaSettings,
    sp.Contract):
    """A swap and collect marketplace contract."""

    def __init__(self, administrator, registry, royalties_adapter, metadata, exception_optimization_level="default-line"):
        sp.Contract.__init__(self)

        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")
        
        self.init_storage(
            swaps = sp.big_map(tkey=t_swap_key, tvalue=sp.TNat),
            next_swap_id = sp.nat(0)
        )

        self.addMetaSettings([
            # Token registry contract
            ("registry", registry, sp.TAddress, lambda x : Utils.onlyContract(x)),
            # Royalties adapter
            ("royalties_adapter", royalties_adapter, sp.TAddress, lambda x : Utils.onlyContract(x))
        ])

        Administrable.__init__(self, administrator = administrator, include_views = False)
        Pausable.__init__(self, include_views = False)
        ContractMetadata.__init__(self, metadata = metadata)
        Fees.__init__(self, fees_to = administrator)
        MetaSettings.__init__(self)
        Upgradeable.__init__(self)

        self.generateContractMetadata("tz1and Marketplace", "tz1and Marketplace swap and collect marketplace contract",
            authors=["852Kerfunkle <https://github.com/852Kerfunkle>"],
            source_location="https://github.com/tz1and",
            homepage="https://www.tz1and.com", license="UNLICENSED",
            version="2.0.0")


    #
    # Public entry points
    #
    @sp.entry_point(lazify = True)
    def swap(self, params):
        """Create a token swap.

        Tokens are transferred to marketplace contract.
        amount must be >= 1.
        """
        sp.set_type(params, sp.TRecord(
            swap_key_partial = t_swap_key_partial,
            token_amount = sp.TNat,
            ext = extensionArgType
        ).layout(("swap_key_partial", ("token_amount", "ext"))))

        self.onlyUnpaused()

        # Check swap params,
        sp.verify((params.token_amount >= sp.nat(1)), "INVALID_PARAM")

        # Only tokens in registry allowed.
        sp.compute(TL_TokenRegistry.onlyRegistered(self.data.settings.registry, sp.set([params.swap_key_partial.fa2])).open_some())

        # Transfer item from owner to this contract.
        FA2Utils.fa2_transfer(params.swap_key_partial.fa2, sp.sender, sp.self_address, params.swap_key_partial.token_id, params.token_amount)

        swap_key = sp.record(
            id=self.data.next_swap_id,
            owner=sp.sender,
            partial=params.swap_key_partial)

        # Create swap.
        self.data.swaps[swap_key] = params.token_amount

        # Increment next id.
        self.data.next_swap_id += 1


    @sp.entry_point(lazify = True)
    def cancel(self, params):
        """Cancel a swap.

        Given it is owned.
        Tokens are returned to owner.
        """
        sp.set_type(params, sp.TRecord(
            swap_key = t_swap_key,
            ext = extensionArgType
        ).layout(("swap_key", "ext")))

        self.onlyUnpaused()

        # Make sure sender is owner.
        sp.verify(params.swap_key.owner == sp.sender, ErrorMessages.not_owner())

        token_amount = self.data.swaps.get(params.swap_key, message="INVALID_SWAP")

        # Transfer remaining amout to the owner.
        FA2Utils.fa2_transfer(params.swap_key.partial.fa2, sp.self_address, sp.sender, params.swap_key.partial.token_id, token_amount)

        # Delete the swap.
        del self.data.swaps[params.swap_key]


    @sp.entry_point(lazify = True)
    def collect(self, params):
        """Collect."""
        sp.set_type(params, sp.TRecord(
            swap_key = t_swap_key,
            ext = extensionArgType
        ).layout(("swap_key", "ext")))

        self.onlyUnpaused()

        # check if correct value was sent.
        sp.verify(sp.amount == params.swap_key.partial.price, message = ErrorMessages.wrong_amount())

        token_amount = sp.local("token_amount", self.data.swaps.get(params.swap_key, message="INVALID_SWAP"))

        # check the swap has items left.
        # NOTE: should really never happen!
        sp.verify(token_amount.value >= 1, message = "INVALID_SWAP")

        # Transfer royalties, value, fees, etc.
        with sp.if_(sp.amount != sp.mutez(0)):
            # Get the royalties for this item
            item_royalty_info = sp.compute(TL_RoyaltiesAdapter.getRoyalties(
                self.data.settings.royalties_adapter, sp.record(fa2 = params.swap_key.partial.fa2, id = params.swap_key.partial.token_id)).open_some())

            # Send fees, royalties, value.
            TL_RoyaltiesAdapter.sendValueRoyaltiesFeesInline(self.data.settings.fees, self.data.settings.fees_to, sp.amount,
                params.swap_key.owner, item_royalty_info, params.swap_key.partial.primary)

        # Transfer item from this contract to buyer.
        FA2Utils.fa2_transfer(params.swap_key.partial.fa2, sp.self_address, sp.sender, params.swap_key.partial.token_id, 1)

        # Reduce the item amount in storage or remove it.
        with sp.if_(token_amount.value > 1):
            # NOTE: fine to use abs here, token amout is checked to be > 1.
            token_amount.value = abs(token_amount.value - 1)
            self.data.swaps[params.swap_key] = token_amount.value
        with sp.else_():
            del self.data.swaps[params.swap_key]


    #
    # Views
    #

    # NOTE: does it make sense to even have get_swap?
    # without being able to get the indices...
    @sp.onchain_view(pure=True)
    def get_swap(self, swap_key):
        """Returns information about a swap."""
        sp.set_type(swap_key, t_swap_key)
        sp.result(self.data.swaps.get(swap_key, message="INVALID_SWAP"))
