import smartpy as sp

pause_mixin = sp.io.import_script_from_url("file:contracts/Pausable.py")
fees_mixin = sp.io.import_script_from_url("file:contracts/Fees.py")
permitted_fa2 = sp.io.import_script_from_url("file:contracts/FA2PermissionsAndWhitelist.py")
upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
contract_metadata_mixin = sp.io.import_script_from_url("file:contracts/ContractMetadata.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")

# TODO: test royalties for item token
# TODO: document reasoning for not limiting bids on secondary disable
# TODO: document (or fix!) issue with admin transfer and whitelist!
# TODO: per-fa2-per-user whitelist
# TODO: load whitelist settings from permitted FA2
# TODO: etc...
# TODO: Make sure auction contract is operator of token

# Optional extension argument type.
# Map val can contain about anything and be
# unpacked with sp.unpack.
extensionArgType = sp.TOption(sp.TMap(sp.TString, sp.TBytes))

t_auction_key = sp.TRecord(
    fa2 = sp.TAddress,
    token_id = sp.TNat,
    owner = sp.TAddress
).layout(("fa2", ("token_id", "owner")))

# TODO: can probably get rid of fa2, token_id and owner,
# since they are implicit in the key :)
t_auction = sp.TRecord(
    start_price=sp.TMutez,
    end_price=sp.TMutez,
    start_time=sp.TTimestamp,
    end_time=sp.TTimestamp
).layout(("start_price", ("end_price", ("start_time", "end_time"))))

#
# Lazy map of auctions.
class AuctionMap(utils.GenericMap):
    def __init__(self) -> None:
        super().__init__(t_auction_key, t_auction, default_value=None, get_error="AUCTION_NOT_FOUND")

#
# Dutch auction contract.
# NOTE: should be pausable for code updates.
class TL_Dutch(
    contract_metadata_mixin.ContractMetadata,
    pause_mixin.Pausable,
    fees_mixin.Fees,
    upgradeable_mixin.Upgradeable,
    permitted_fa2.FA2PermissionsAndWhitelist,
    sp.Contract):
    """A simple dutch auction.
    
    The price keeps dropping until end_time is reached. First valid bid gets the token.
    """

    def __init__(self, administrator, places_contract, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")

        self.auction_map = AuctionMap()
        
        self.init_storage(
            metadata = metadata, # TODO: use ContractMetadata mixin for v2...
            secondary_enabled = sp.bool(False), # If the secondary market is enabled.
            granularity = sp.nat(60), # Globally controls the granularity of price drops. in seconds.
            auctions = self.auction_map.make()
        )

        self.available_settings = [
            ("granularity", sp.TNat, None),
            ("secondary_enabled", sp.TBool, None)
        ]

        contract_metadata_mixin.ContractMetadata.__init__(self, administrator = administrator, metadata = metadata, meta_settings = True)
        pause_mixin.Pausable.__init__(self, administrator = administrator, meta_settings = True)
        fees_mixin.Fees.__init__(self, administrator = administrator, meta_settings = True)

        default_permitted = { places_contract : sp.record(
            whitelist_enabled = True,
            whitelist_admin = administrator )}
        permitted_fa2.FA2PermissionsAndWhitelist.__init__(self, administrator = administrator, default_permitted = default_permitted)
        upgradeable_mixin.Upgradeable.__init__(self, administrator = administrator)

        self.generate_contract_metadata()

    def generate_contract_metadata(self):
        """Generate a metadata json file with all the contract's offchain views
        and standard TZIP-12 and TZIP-016 key/values."""
        metadata_base = {
            "name": 'tz1and Dutch Auctions',
            "description": 'tz1and Places and Items Dutch auctions',
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
            "license": { "name": "MIT" }
        }
        offchain_views = []
        for f in dir(self):
            attr = getattr(self, f)
            if isinstance(attr, sp.OnOffchainView):
                # Include onchain views as tip 16 offchain views
                offchain_views.append(attr)
        metadata_base["views"] = offchain_views
        self.init_metadata("metadata_base", metadata_base)


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
    # Inlineable helpers
    #
    def onlyWhitelistAdminIfSecondaryDisabled(self, fa2_props):
        """Fails if secondary is disabled and sender is not whitelist admin"""
        with sp.if_(~self.data.secondary_enabled):
            sp.verify(sp.sender == fa2_props.whitelist_admin, "ONLY_WHITELIST_ADMIN")

    #
    # Public entry points
    #
    @sp.entry_point(lazify = True)
    def create(self, params):
        """Create a dutch auction.
        
        Transfers token to auction contract.
        
        end_price must be < than start_price.
        end_time must be > than start_time
        """
        sp.set_type(params, sp.TRecord(
            auction_key = t_auction_key,
            auction = t_auction,
            extension = extensionArgType
        ).layout(("auction_key", ("auction", "extension"))))

        self.onlyUnpaused()

        # Fails if FA2 not permitted.
        fa2_props = sp.compute(self.getPermittedFA2Props(params.auction_key.fa2))

        self.onlyWhitelistAdminIfSecondaryDisabled(fa2_props)

        # Auction owner in auction_key must be sender.
        sp.verify(params.auction_key.owner == sp.sender, "NOT_OWNER")

        # Check auction params,
        sp.verify((params.auction.start_time >= sp.now) &
            (params.auction.start_time < params.auction.end_time) &
            (abs(params.auction.end_time - params.auction.start_time) > self.data.granularity) &
            (params.auction.start_price >= params.auction.end_price), message = "INVALID_PARAM")

        # Auction can not exist already.
        sp.verify(~self.auction_map.contains(self.data.auctions, params.auction_key), message = "AUCTION_EXISTS")

        # Make sure token is owned by owner.
        sp.verify(utils.fa2_get_balance(params.auction_key.fa2, params.auction_key.token_id, sp.sender) > 0, message = "NOT_OWNER")

        # TODO: Make sure auction contract is operator of token

        # Create auction
        self.auction_map.add(self.data.auctions, params.auction_key, params.auction)


    @sp.entry_point(lazify = True)
    def cancel(self, params):
        """Cancel an auction.

        Given it is owned.
        Token is transferred back to auction owner.
        """
        sp.set_type(params, sp.TRecord(
            auction_key = t_auction_key,
            extension = extensionArgType
        ).layout(("auction_key", "extension")))

        self.onlyUnpaused()
        # no need to call self.onlyAdminIfWhitelistEnabled()

        sp.verify(self.auction_map.contains(self.data.auctions, params.auction_key), message = "INVALID_AUCTION")

        sp.verify(params.auction_key.owner == sp.sender, message = "NOT_OWNER")

        self.auction_map.remove(self.data.auctions, params.auction_key)


    def sendOverpayValueAndFeesInline(self, amount_sent, ask_price, owner):
        """Inline function for sending royalties, fees, etc."""
        sp.set_type(amount_sent, sp.TMutez)
        sp.set_type(ask_price, sp.TMutez)
        sp.set_type(owner, sp.TAddress)

        # Collect amounts to send in a map.
        sendMap = utils.TokenSendMap()

        # Send back overpay, if there was any.
        overpay = amount_sent - ask_price
        sendMap.add(sp.sender, overpay)

        with sp.if_(ask_price != sp.mutez(0)):
            # Our fees are in permille.
            fees_amount = sp.compute(sp.split_tokens(ask_price, self.data.fees, sp.nat(1000)))
            sendMap.add(self.data.fees_to, fees_amount)

            # Send rest of the value to seller.
            left_amount = ask_price - fees_amount
            sendMap.add(owner, left_amount)

        # Transfer.
        sendMap.transfer()


    @sp.entry_point(lazify = True)
    def bid(self, params):
        """Bid on an auction.

        The first valid bid (value >= ask_price) gets the token.
        Overpay is transferred back to sender.
        """
        sp.set_type(params, sp.TRecord(
            auction_key = t_auction_key,
            extension = extensionArgType
        ).layout(("auction_key", "extension")))

        self.onlyUnpaused()

        the_auction = sp.local("the_auction", self.auction_map.get(self.data.auctions, params.auction_key))

        # If whitelist is enabled for this token, sender must be whitelisted.
        fa2_props = self.onlyWhitelistedForFA2(params.auction_key.fa2, sp.sender)

        # check auction has started
        sp.verify(sp.now >= the_auction.value.start_time, message = "NOT_STARTED")

        # calculate current price and verify amount sent
        ask_price = self.getAuctionPriceInline(the_auction.value)
        #sp.trace(sp.now)
        #sp.trace(ask_price)

        # check if correct value was sent. probably best to send back overpay instead of cancel.
        sp.verify(sp.amount >= ask_price, message = "WRONG_AMOUNT")

        # Send fees, etc, if any.
        self.sendOverpayValueAndFeesInline(sp.amount, ask_price, params.auction_key.owner)

        # Transfer item from owner to buyer.
        utils.fa2_transfer(params.auction_key.fa2, params.auction_key.owner, sp.sender, params.auction_key.token_id, 1)

        # If it was a whitelist required auction, remove from whitelist.
        with sp.if_(params.auction_key.owner == fa2_props.whitelist_admin):
            self.removeFromFA2Whitelist(params.auction_key.fa2, sp.sender)

        # Delete auction.
        self.auction_map.remove(self.data.auctions, params.auction_key)


    # TODO: private lambda to shrink view?
    def getAuctionPriceInline(self, the_auction):
        """Inlined into bid and get_auction_price view"""
        sp.set_type(the_auction, t_auction)
        
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
                # alright, this works well enough. make 100% sure the math checks out (overflow, abs, etc)
                # probably by validating the input in create. to make sure intervals can't be negative.
                duration = abs(the_auction.end_time - the_auction.start_time) // self.data.granularity
                time_since_start = abs(sp.now - the_auction.start_time) // self.data.granularity
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
        sp.result(self.auction_map.get(self.data.auctions, auction_key))

    @sp.onchain_view(pure=True)
    def get_auction_price(self, auction_key):
        """Returns the current price of an auction."""
        sp.set_type(auction_key, t_auction_key)
        the_auction = sp.local("the_auction", self.auction_map.get(self.data.auctions, auction_key))
        sp.result(self.getAuctionPriceInline(the_auction.value))

    @sp.onchain_view(pure=True)
    def is_secondary_enabled(self):
        """Returns true if secondary is enabled."""
        sp.result(self.data.secondary_enabled)
