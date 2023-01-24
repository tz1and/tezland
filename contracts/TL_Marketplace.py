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

#
# Swaps
t_swap_key_partial = sp.TRecord(
    fa2 = sp.TAddress,
    token_id = sp.TNat,
    rate = sp.TMutez,
    primary = sp.TBool,
    expires = sp.TOption(sp.TTimestamp)
).layout(("fa2", ("token_id", ("rate", ("primary", "expires")))))

t_swap_key = sp.TRecord(
    id = sp.TNat,
    owner = sp.TAddress,
    partial = t_swap_key_partial
).layout(("id", ("owner", "partial")))

t_swap = sp.TRecord(
    token_amount = sp.TNat,
    ext = extensionArgType
).layout(("token_amount", "ext"))

#
# Offers
t_offer_key_partial = sp.TRecord(
    fa2 = sp.TAddress,
    token_id = sp.TNat,
    token_amount = sp.TNat,
    rate = sp.TMutez,
    expires = sp.TOption(sp.TTimestamp)
).layout(("fa2", ("token_id", ("token_amount", ("rate", "expires")))))

t_offer_key = sp.TRecord(
    id = sp.TNat,
    owner = sp.TAddress,
    partial = t_offer_key_partial
).layout(("id", ("owner", "partial")))

t_offer = extensionArgType

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
            swaps = sp.big_map(tkey=t_swap_key, tvalue=t_swap),
            offers = sp.big_map(tkey=t_offer_key, tvalue=t_offer),
            next_swap_id = sp.nat(0),
            next_offer_id = sp.nat(0)
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
    # Admin only eps
    #
    @sp.entry_point(lazify = False, parameter_type=sp.TOption(sp.TKeyHash))
    def set_delegate(self, delegate):
        self.onlyAdministrator()

        # Check amount is zero.
        sp.verify(sp.amount == sp.mutez(0), message = ErrorMessages.no_amount())

        sp.set_delegate(delegate)


    #
    # Swaps
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

        # Check amount is zero.
        sp.verify(sp.amount == sp.mutez(0), message = ErrorMessages.no_amount())

        # Check swap params.
        # Token amount must be > 0 and expriy is currently not supported.
        sp.verify((params.token_amount >= sp.nat(1)) & (params.swap_key_partial.expires == sp.none), "INVALID_PARAM")

        # Only tokens in registry allowed.
        sp.compute(TL_TokenRegistry.onlyRegistered(self.data.settings.registry, sp.set([params.swap_key_partial.fa2])).open_some())

        # Transfer item from owner to this contract.
        FA2Utils.fa2_transfer(params.swap_key_partial.fa2, sp.sender, sp.self_address, params.swap_key_partial.token_id, params.token_amount)

        swap_key = sp.record(
            id=self.data.next_swap_id,
            owner=sp.sender,
            partial=params.swap_key_partial)

        # Create swap.
        self.data.swaps[swap_key] = sp.record(
            token_amount = params.token_amount,
            ext = params.ext)

        # Increment next id.
        self.data.next_swap_id += 1


    @sp.entry_point(lazify = True)
    def collect(self, params):
        """Collect."""
        sp.set_type(params, sp.TRecord(
            swap_key = t_swap_key,
            ext = extensionArgType
        ).layout(("swap_key", "ext")))

        self.onlyUnpaused()

        # check if correct value was sent.
        sp.verify(sp.amount == params.swap_key.partial.rate, message = ErrorMessages.wrong_amount())

        the_swap = sp.local("the_swap", self.data.swaps.get(params.swap_key, message="INVALID_SWAP"))

        # check the swap has items left.
        # NOTE: should really never happen!
        sp.verify(the_swap.value.token_amount >= 1, message = "INVALID_SWAP")

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
        with sp.if_(the_swap.value.token_amount > 1):
            # NOTE: fine to use abs here, token amout is checked to be > 1.
            the_swap.value.token_amount = abs(the_swap.value.token_amount - 1)
            self.data.swaps[params.swap_key] = the_swap.value
        with sp.else_():
            del self.data.swaps[params.swap_key]


    @sp.entry_point(lazify = True)
    def cancel_swap(self, params):
        """Cancel a swap.

        Given it is owned.
        Tokens are returned to owner.
        """
        sp.set_type(params, sp.TRecord(
            swap_key = t_swap_key,
            ext = extensionArgType
        ).layout(("swap_key", "ext")))

        self.onlyUnpaused()

        # Check amount is zero.
        sp.verify(sp.amount == sp.mutez(0), message = ErrorMessages.no_amount())

        # Make sure sender is owner.
        sp.verify(params.swap_key.owner == sp.sender, ErrorMessages.not_owner())

        the_swap = self.data.swaps.get(params.swap_key, message="INVALID_SWAP")

        # Transfer remaining amout to the owner.
        FA2Utils.fa2_transfer(params.swap_key.partial.fa2, sp.self_address, sp.sender, params.swap_key.partial.token_id, the_swap.token_amount)

        # Delete the swap.
        del self.data.swaps[params.swap_key]

    #
    # Offers
    #
    @sp.entry_point(lazify = True)
    def offer(self, params):
        """Make an offer for a certain token.

        Locks tez into the contract, until claimed with the token.
        """
        sp.set_type(params, sp.TRecord(
            offer_key_partial = t_offer_key_partial,
            ext = extensionArgType
        ).layout(("offer_key_partial", "ext")))

        self.onlyUnpaused()

        # Check swap params.
        # token_amount must be == 1 for now, expiry currently not supported.
        sp.verify((params.offer_key_partial.token_amount == sp.nat(1)) & (params.offer_key_partial.expires == sp.none), "INVALID_PARAM")
        # Sent amount must be == rate
        sp.verify(sp.amount == params.offer_key_partial.rate, ErrorMessages.wrong_amount())

        # Only tokens in registry allowed.
        sp.compute(TL_TokenRegistry.onlyRegistered(self.data.settings.registry, sp.set([params.offer_key_partial.fa2])).open_some())

        offer_key = sp.record(
            id=self.data.next_offer_id,
            owner=sp.sender,
            partial=params.offer_key_partial)

        # Create swap.
        self.data.offers[offer_key] = params.ext

        # Increment next id.
        self.data.next_offer_id += 1


    @sp.entry_point(lazify = True)
    def fulfill_offer(self, params):
        """Fulfill an offer.

        Transfer tez to sender, token to offer owner.
        """
        sp.set_type(params, sp.TRecord(
            offer_key = t_offer_key,
            ext = extensionArgType
        ).layout(("offer_key", "ext")))

        self.onlyUnpaused()

        # Check amount is zero.
        sp.verify(sp.amount == sp.mutez(0), message = ErrorMessages.no_amount())

        # Offer must exist.
        sp.verify(self.data.offers.contains(params.offer_key), message="INVALID_OFFER")

        # Transfer royalties, value, fees, etc.
        with sp.if_(params.offer_key.partial.rate != sp.mutez(0)):
            # Get the royalties for this item
            item_royalty_info = sp.compute(TL_RoyaltiesAdapter.getRoyalties(
                self.data.settings.royalties_adapter, sp.record(fa2 = params.offer_key.partial.fa2, id = params.offer_key.partial.token_id)).open_some())

            # Send fees, royalties, value.
            TL_RoyaltiesAdapter.sendValueRoyaltiesFeesInline(self.data.settings.fees, self.data.settings.fees_to, params.offer_key.partial.rate,
                sp.sender, item_royalty_info, False)

        # Transfer item from sender to offer owner.
        FA2Utils.fa2_transfer(params.offer_key.partial.fa2, sp.sender, params.offer_key.owner, params.offer_key.partial.token_id, params.offer_key.partial.token_amount)

        # Delete the offer.
        del self.data.offers[params.offer_key]


    @sp.entry_point(lazify = True)
    def cancel_offer(self, params):
        """Cancel an offer.

        Given it is owned. Return tez to sender.
        """
        sp.set_type(params, sp.TRecord(
            offer_key = t_offer_key,
            ext = extensionArgType
        ).layout(("offer_key", "ext")))

        self.onlyUnpaused()

        # Check amount is zero.
        sp.verify(sp.amount == sp.mutez(0), message = ErrorMessages.no_amount())

        # Make sure sender is owner.
        sp.verify(params.offer_key.owner == sp.sender, ErrorMessages.not_owner())

        # Offer must exist.
        sp.verify(self.data.offers.contains(params.offer_key), message="INVALID_OFFER")

        # Transfer amount back to offer owner.
        sp.send(sp.sender, params.offer_key.partial.rate)

        # Delete the offer.
        del self.data.offers[params.offer_key]

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

    @sp.onchain_view(pure=True)
    def get_offer(self, offer_key):
        """Returns information about an offer."""
        sp.set_type(offer_key, t_offer_key)
        sp.result(self.data.offers.get(offer_key, message="INVALID_OFFER"))
