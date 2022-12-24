import smartpy as sp

from tz1and_contracts_smartpy.mixins.Administrable import Administrable
from tz1and_contracts_smartpy.mixins.Pausable import Pausable
from tz1and_contracts_smartpy.mixins.Upgradeable import Upgradeable
from tz1and_contracts_smartpy.mixins.ContractMetadata import ContractMetadata
from tz1and_contracts_smartpy.mixins.MetaSettings import MetaSettings
from contracts.mixins.Fees import Fees
from contracts.mixins.FA2PermissionsAndWhitelist import FA2PermissionsAndWhitelist

from contracts import TL_World_v2, FA2
from contracts.utils import TokenTransfer, FA2Utils, ErrorMessages
from tz1and_contracts_smartpy.utils import Utils


# TODO: private lambda to shrink view? getAuctionPriceInline


# Optional ext argument type.
# Map val can contain about anything and be
# unpacked with sp.unpack.
extensionArgType = sp.TOption(sp.TMap(sp.TString, sp.TBytes))

t_auction_key = sp.TRecord(
    fa2 = sp.TAddress,
    token_id = sp.TNat,
    owner = sp.TAddress
).layout(("fa2", ("token_id", "owner")))

t_auction_params = sp.TRecord(
    start_price=sp.TMutez,
    end_price=sp.TMutez,
    start_time=sp.TTimestamp,
    end_time=sp.TTimestamp
).layout(("start_price", ("end_price", ("start_time", "end_time"))))

t_auction = sp.TRecord(
    auction_params=t_auction_params,
    is_primary=sp.TBool
).layout(("auction_params", "is_primary"))

#
# Dutch auction contract.
# NOTE: should be pausable for code updates.
class TL_Dutch_v2(
    Administrable,
    ContractMetadata,
    Pausable,
    Fees,
    FA2PermissionsAndWhitelist,
    Upgradeable,
    MetaSettings,
    sp.Contract):
    """A simple dutch auction.
    
    The price keeps dropping until end_time is reached. First valid bid gets the token.
    """

    def __init__(self, administrator, world_contract, metadata, exception_optimization_level="default-line"):
        sp.Contract.__init__(self)

        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")
        
        self.init_storage(
            auctions = sp.big_map(tkey=t_auction_key, tvalue=t_auction)
        )

        self.addMetaSettings([
            # Globally controls the granularity of price drops. in seconds.
            ("granularity", 60, sp.TNat, None),
            # If the secondary market is enabled.
            ("secondary_enabled", False, sp.TBool, None),
            # The world contract. Needed for some things.
            ("world_contract", world_contract, sp.TAddress, lambda x : Utils.onlyContract(x))
        ])

        Administrable.__init__(self, administrator = administrator, include_views = False)
        Pausable.__init__(self, include_views = False)
        ContractMetadata.__init__(self, metadata = metadata)
        Fees.__init__(self, fees_to = administrator)
        FA2PermissionsAndWhitelist.__init__(self)
        Upgradeable.__init__(self)
        MetaSettings.__init__(self)

        self.generateContractMetadata("tz1and Dutch Auctions", "tz1and Places and Items Dutch auctions",
            authors=["852Kerfunkle <https://github.com/852Kerfunkle>"],
            source_location="https://github.com/tz1and",
            homepage="https://www.tz1and.com", license="UNLICENSED",
            version="2.0.0")


    #
    # Inlineable helpers
    #
    def onlyWhitelistAdminIfSecondaryDisabled(self, fa2_props):
        """Fails if secondary is disabled and sender is not whitelist admin"""
        with sp.if_(~self.data.settings.secondary_enabled):
            sp.verify(sp.sender == fa2_props.whitelist_admin, "ONLY_WHITELIST_ADMIN")

    #
    # Public entry points
    #
    @sp.entry_point(lazify = True)
    def create(self, params):
        """Create a dutch auction.
        
        Does not transfer token to auction contract. Only works with operators.
        
        end_price must be < than start_price.
        end_time must be > than start_time
        """
        sp.set_type(params, sp.TRecord(
            auction_key = t_auction_key,
            auction = t_auction_params,
            ext = extensionArgType
        ).layout(("auction_key", ("auction", "ext"))))

        self.onlyUnpaused()

        # Fails if FA2 not permitted.
        fa2_props = sp.compute(self.getPermittedFA2Props(params.auction_key.fa2))

        self.onlyWhitelistAdminIfSecondaryDisabled(fa2_props)

        # Auction owner in auction_key must be sender.
        sp.verify(params.auction_key.owner == sp.sender, ErrorMessages.not_owner())

        # Check auction params,
        sp.verify((params.auction.start_time >= sp.now) &
            # NOTE: is assumed by next check. sp.as_nat trows if negative.
            # (params.auction.start_time < params.auction.end_time) &
            (sp.as_nat(params.auction.end_time - params.auction.start_time, "INVALID_PARAM") > self.data.settings.granularity) &
            (params.auction.start_price >= params.auction.end_price), "INVALID_PARAM")

        # Auction can not exist already.
        sp.verify(~self.data.auctions.contains(params.auction_key), "AUCTION_EXISTS")

        # Make sure token is owned by owner.
        sp.verify(FA2.getOwner(params.auction_key.fa2, params.auction_key.token_id).open_some() == sp.sender, ErrorMessages.not_owner())

        # Make sure auction contract is operator of token.
        sp.verify(FA2Utils.fa2_is_operator(params.auction_key.fa2, params.auction_key.token_id, sp.sender, sp.self_address), "NOT_OPERATOR")

        # Create auction.
        self.data.auctions[params.auction_key] = sp.record(
            auction_params=params.auction,
            is_primary=(params.auction_key.owner == fa2_props.whitelist_admin))


    @sp.entry_point(lazify = True)
    def cancel(self, params):
        """Cancel an auction.

        Given it is owned.
        Removing operators is on the sender.
        """
        sp.set_type(params, sp.TRecord(
            auction_key = t_auction_key,
            ext = extensionArgType
        ).layout(("auction_key", "ext")))

        self.onlyUnpaused()
        # no need to call self.onlyAdminIfWhitelistEnabled()

        sp.verify(self.data.auctions.contains(params.auction_key), "INVALID_AUCTION")

        sp.verify(params.auction_key.owner == sp.sender, ErrorMessages.not_owner())

        del self.data.auctions[params.auction_key]


    def sendOverpayValueAndFeesInline(self, amount_sent, ask_price, owner):
        """Inline function for sending royalties, fees, etc."""
        sp.set_type(amount_sent, sp.TMutez)
        sp.set_type(ask_price, sp.TMutez)
        sp.set_type(owner, sp.TAddress)

        # Collect amounts to send in a map.
        sendMap = TokenTransfer.TokenSendMap()

        # Send back overpay, if there was any.
        overpay = amount_sent - ask_price
        sendMap.add(sp.sender, overpay)

        with sp.if_(ask_price != sp.mutez(0)):
            # Our fees are in permille.
            fees_amount = sp.compute(sp.split_tokens(ask_price, self.data.settings.fees, sp.nat(1000)))
            sendMap.add(self.data.settings.fees_to, fees_amount)

            # Send rest of the value to seller.
            left_amount = ask_price - fees_amount
            sendMap.add(owner, left_amount)

        # Transfer.
        sendMap.transfer()


    def removeOperator(self, token_contract, token_id, owner):
        sp.set_type(token_contract, sp.TAddress)
        sp.set_type(token_id, sp.TNat)
        sp.set_type(owner, sp.TAddress)

        # Build operator permissions list.
        operator_remove = sp.set_type_expr(sp.record(
            owner=owner,
            operator=sp.self_address,
            token_id=token_id), FA2.t_operator_permission)

        # Call token contract to add operators.
        token_handle = sp.contract(
            FA2.t_update_operators_params,
            token_contract,
            entry_point='update_operators').open_some()
        sp.transfer([sp.variant("remove_operator", operator_remove)],
            sp.mutez(0), token_handle)


    def resetValueToAndItemsToInWorld(self, token_contract, token_id):
        sp.set_type(token_contract, sp.TAddress)
        sp.set_type(token_id, sp.TNat)

        # Build update props param list.
        set_props_args = sp.set_type_expr(sp.record(
            place_key = sp.record(fa2 = token_contract, id = token_id),
            update = sp.variant("owner_props", [
                sp.variant("value_to", sp.none),
                sp.variant("items_to", sp.none)
            ]),
            ext = sp.none), TL_World_v2.updatePlaceType)

        # Call token contract to add operators.
        world_handle = sp.contract(
            TL_World_v2.updatePlaceType,
            self.data.settings.world_contract,
            entry_point='update_place').open_some()
        sp.transfer(set_props_args, sp.mutez(0), world_handle)

    
    def validatePlaceSequenceHash(self, token_contract, token_id, expected_hash):
        current_hash = sp.sha3(sp.pack(sp.view("get_place_seqnum", self.data.settings.world_contract,
            sp.set_type_expr(
                sp.record(place_key=sp.record(fa2 = token_contract, id = token_id), chunk_ids=sp.none),
                TL_World_v2.placeSeqNumParam),
            t = TL_World_v2.seqNumResultType).open_some()))
        sp.verify(current_hash == expected_hash, "NOT_EXPECTED_SEQ_HASH")


    @sp.entry_point(lazify = True)
    def bid(self, params):
        """Bid on an auction.

        The first valid bid (value >= ask_price) gets the token.
        Overpay is transferred back to sender.
        """
        sp.set_type(params, sp.TRecord(
            auction_key = t_auction_key,
            seq_hash = sp.TBytes,
            ext = extensionArgType
        ).layout(("auction_key", ("seq_hash", "ext"))))

        self.onlyUnpaused()

        the_auction = sp.local("the_auction", self.data.auctions.get(params.auction_key, message="AUCTION_NOT_FOUND"))

        # If whitelist is enabled for this token, sender must be whitelisted.
        self.onlyWhitelistedForFA2(params.auction_key.fa2, sp.sender)

        # check auction has started
        sp.verify(sp.now >= the_auction.value.auction_params.start_time, message = "NOT_STARTED")

        # calculate current price and verify amount sent
        ask_price = self.getAuctionPriceInline(the_auction.value.auction_params)
        #sp.trace(sp.now)
        #sp.trace(ask_price)

        # check if correct value was sent. probably best to send back overpay instead of cancel.
        sp.verify(sp.amount >= ask_price, message = ErrorMessages.wrong_amount())

        # validate sequence hash, to prevent front-running.
        self.validatePlaceSequenceHash(params.auction_key.fa2, params.auction_key.token_id, params.seq_hash)

        # Send fees, etc, if any.
        self.sendOverpayValueAndFeesInline(sp.amount, ask_price, params.auction_key.owner)

        # Transfer place from owner to this contract.
        FA2Utils.fa2_transfer(params.auction_key.fa2, params.auction_key.owner, sp.self_address, params.auction_key.token_id, 1, nonstandard_transfer=True)

        # Reset the place's value_to and items_to property.
        self.resetValueToAndItemsToInWorld(params.auction_key.fa2, params.auction_key.token_id)

        # Transfer place from this contract to buyer.
        FA2Utils.fa2_transfer(params.auction_key.fa2, sp.self_address, sp.sender, params.auction_key.token_id, 1, nonstandard_transfer=True)

        # After transfer, remove own operator rights for token.
        self.removeOperator(params.auction_key.fa2, params.auction_key.token_id, params.auction_key.owner)

        # If it was a whitelist required auction, remove from whitelist.
        with sp.if_(the_auction.value.is_primary):
            self.removeFromFA2Whitelist(params.auction_key.fa2, sp.sender)

        # Delete auction.
        del self.data.auctions[params.auction_key]


    # TODO: private lambda to shrink view?
    def getAuctionPriceInline(self, the_auction):
        """Inlined into bid and get_auction_price view"""
        sp.set_type(the_auction, t_auction_params)
        
        # Local var for the result.
        result = sp.local("result", sp.mutez(0))
        # return start price if it hasn't started
        with sp.if_(sp.now <= the_auction.start_time):
            result.value = the_auction.start_price
        with sp.else_():
            # return end price if it's over
            with sp.if_(sp.now >= the_auction.end_time):
                result.value = the_auction.end_price
            with sp.else_():
                # alright, this works well enough. make 100% sure the math
                # checks out (overflow, abs, etc) probably by validating
                # the input in create. to make sure intervals can't be negative.
                # NOTE: can use abs here, because end time is checked to be
                # larger than start_time on auction creation.
                duration = abs(the_auction.end_time - the_auction.start_time) // self.data.settings.granularity
                # NOTE: can use abs here because we check sp.now > start time.
                time_since_start = abs(sp.now - the_auction.start_time) // self.data.settings.granularity
                # NOTE: this can lead to a division by 0. auction duration must be > granularity.
                mutez_per_interval = sp.utils.mutez_to_nat(the_auction.start_price - the_auction.end_price) // duration
                time_deduction = mutez_per_interval * time_since_start

                current_price = the_auction.start_price - sp.utils.nat_to_mutez(time_deduction)

                result.value = current_price
        return result.value


    #
    # Views
    #

    # NOTE: does it make sense to even have get_auction?
    # without being able to get the indices...
    @sp.onchain_view(pure=True)
    def get_auction(self, auction_key):
        """Returns information about an auction."""
        sp.set_type(auction_key, t_auction_key)
        sp.result(self.data.auctions.get(auction_key, message="AUCTION_NOT_FOUND"))

    @sp.onchain_view(pure=True)
    def get_auction_price(self, auction_key):
        """Returns the current price of an auction."""
        sp.set_type(auction_key, t_auction_key)
        the_auction = sp.local("the_auction", self.data.auctions.get(auction_key, message="AUCTION_NOT_FOUND"))
        sp.result(self.getAuctionPriceInline(the_auction.value.auction_params))

    @sp.onchain_view(pure=True)
    def is_secondary_enabled(self):
        """Returns true if secondary is enabled."""
        sp.result(self.data.settings.secondary_enabled)
