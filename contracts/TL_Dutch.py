import smartpy as sp

pausable_contract = sp.io.import_script_from_url("file:contracts/Pausable.py")
whitelist_contract = sp.io.import_script_from_url("file:contracts/Whitelist.py")
fees_contract = sp.io.import_script_from_url("file:contracts/Fees.py")
permitted_fa2 = sp.io.import_script_from_url("file:contracts/PermittedFA2.py")
fa2_royalties = sp.io.import_script_from_url("file:contracts/FA2_Royalties.py")
upgradeable = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")

# TODO: test royalties for item token
# TODO: allow auctions on other FA2, based on props.
# TODO: layouts

#
# Dutch auction contract.
# NOTE: should be pausable for code updates.
class TL_Dutch(pausable_contract.Pausable, whitelist_contract.Whitelist,
    fees_contract.Fees, upgradeable.Upgradeable, permitted_fa2.PermittedFA2):
    """A simple dutch auction.
    
    The price keeps dropping until end_time is reached. First valid bid gets the token.
    """
    AUCTION_TYPE = sp.TRecord(
        owner=sp.TAddress,
        token_id=sp.TNat,
        start_price=sp.TMutez,
        end_price=sp.TMutez,
        start_time=sp.TTimestamp,
        end_time=sp.TTimestamp,
        fa2=sp.TAddress
    ).layout(("owner", ("token_id", ("start_price",
        ("end_price", ("start_time", ("end_time", "fa2")))))))

    def __init__(self, administrator, items_contract, places_contract, metadata, exception_optimization_level="default-unit"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")
        
        self.init_storage(
            items_contract = items_contract,
            metadata = metadata,
            auction_id = sp.nat(0), # the auction id counter.
            granularity = sp.nat(60), # Globally controls the granularity of price drops. in seconds.
            auctions = sp.big_map(tkey=sp.TNat, tvalue=TL_Dutch.AUCTION_TYPE)
        )
        pausable_contract.Pausable.__init__(self, administrator = administrator)
        whitelist_contract.Whitelist.__init__(self, administrator = administrator)
        fees_contract.Fees.__init__(self, administrator = administrator)
        upgradeable.Upgradeable.__init__(self, administrator = administrator,
            entrypoints = ['create', 'cancel', 'bid'])

        default_permitted = { places_contract : sp.record(
            swap_allowed = True,
            has_royalties = False,
            royalties_view = False) }
        permitted_fa2.PermittedFA2.__init__(self, administrator = administrator, default_permitted = default_permitted)

    #
    # Manager-only entry points
    #
    @sp.entry_point
    def set_granularity(self, granularity):
        """Call to set granularity in seconds."""
        sp.set_type(granularity, sp.TNat)
        self.onlyAdministrator()
        self.data.granularity = granularity

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
            token_id = sp.TNat,
            start_price = sp.TMutez,
            end_price = sp.TMutez,
            start_time = sp.TTimestamp,
            end_time = sp.TTimestamp,
            fa2 = sp.TAddress
        ).layout(("token_id", ("start_price", ("end_price",
            ("start_time", ("end_time", "fa2")))))))

        self.onlyUnpaused()
        self.onlyAdminIfWhitelistEnabled()

        # verify inputs
        self.onlyPermittedFA2(params.fa2)
        sp.verify((params.start_time >= sp.now) &
            (params.start_time < params.end_time) &
            (abs(params.end_time - params.start_time) > self.data.granularity) &
            (params.start_price > params.end_price), message = "INVALID_PARAM")

        # call fa2_balance or is_operator to avoid burning gas on bigmap insert.
        sp.verify(utils.fa2_get_balance(params.fa2, params.token_id, sp.sender) > 0, message = "NOT_OWNER")

        # Create auction
        self.data.auctions[self.data.auction_id] = sp.record(
            owner=sp.sender,
            token_id=params.token_id,
            start_price=params.start_price,
            end_price=params.end_price,
            start_time=params.start_time,
            end_time=params.end_time,
            fa2=params.fa2
        )

        self.data.auction_id += 1

        # Transfer token (place)
        utils.fa2_transfer(params.fa2, sp.sender, sp.self_address, params.token_id, 1)


    @sp.entry_point(lazify = True)
    def cancel(self, auction_id):
        """Cancel an auction.

        Given it is owned.
        Token is transferred back to auction owner.
        """
        sp.set_type(auction_id, sp.TNat)

        self.onlyUnpaused()
        # no need to call self.onlyAdminIfWhitelistEnabled() 

        the_auction = self.data.auctions[auction_id]

        sp.verify(the_auction.owner == sp.sender, message = "NOT_OWNER")

        # transfer token back to auction owner.
        utils.fa2_transfer(the_auction.fa2, sp.self_address, the_auction.owner, the_auction.token_id, 1)

        del self.data.auctions[auction_id]


    @sp.entry_point(lazify = True)
    def bid(self, auction_id):
        """Bid on an auction.

        The first valid bid (value >= ask_price) gets the token.
        Overpay is transferred back to sender.
        """
        sp.set_type(auction_id, sp.TNat)

        self.onlyUnpaused()
        self.onlyWhitelisted()

        the_auction = sp.local("the_auction", self.data.auctions[auction_id])

        # check auction has started
        sp.verify(sp.now >= the_auction.value.start_time, message = "NOT_STARTED")

        # calculate current price and verify amount sent
        ask_price = self.get_auction_price_inline(the_auction.value)
        #sp.trace(sp.now)
        #sp.trace(ask_price)

        # check if correct value was sent. probably best to send back overpay instead of cancel.
        sp.verify(sp.amount >= ask_price, message = "WRONG_AMOUNT")

        # Send back overpay, if there was any.
        overpay = sp.amount - ask_price
        utils.send_if_value(sp.sender, overpay)

        sp.if ask_price != sp.tez(0):
            token_royalty_info = sp.compute(self.get_royalties_if_item_inline(the_auction.value.token_id, the_auction.value.fa2))

            # Calculate fees.
            fee = sp.compute(sp.utils.mutez_to_nat(ask_price) * (token_royalty_info.royalties + self.data.fees) / sp.nat(1000))
            royalties = sp.compute(token_royalty_info.royalties * fee / (token_royalty_info.royalties + self.data.fees))

            # If there are any royalties to be paid.
            sp.if royalties > sp.nat(0):
                # Pay each contributor his relative share.
                sp.for contributor in token_royalty_info.contributors.items():
                    # Calculate amount to be paid from relative share.
                    absolute_amount = sp.compute(sp.utils.nat_to_mutez(royalties * contributor.value.relative_royalties / 1000))
                    utils.send_if_value(contributor.key, absolute_amount)

            # send management fees
            utils.send_if_value(self.data.fees_to, sp.utils.nat_to_mutez(abs(fee - royalties)))
            # send rest of the value to seller
            utils.send_if_value(the_auction.value.owner, ask_price - sp.utils.nat_to_mutez(fee))

        # transfer item to buyer
        utils.fa2_transfer(the_auction.value.fa2, sp.self_address, sp.sender, the_auction.value.token_id, 1)

        self.removeFromWhitelist(sp.sender)

        del self.data.auctions[auction_id]


    def get_auction_price_inline(self, the_auction):
        """Inlined into bid and get_auction_price view"""
        the_auction = sp.set_type_expr(the_auction, TL_Dutch.AUCTION_TYPE)
        
        # Local var for the result.
        result = sp.local("result", sp.tez(0))
        # return start price if it hasn't started
        sp.if sp.now <= the_auction.start_time:
            result.value = the_auction.start_price
        sp.else:
            # return end price if it's over
            sp.if sp.now >= the_auction.end_time:
                result.value = the_auction.end_price
            sp.else:
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


    def get_royalties_if_item_inline(self, token_id, auction_fa2):
        """Inlined into bid to be upgradeable."""
        token_id = sp.set_type_expr(token_id, sp.TNat)
        auction_fa2 = sp.set_type_expr(auction_fa2, sp.TAddress)

        token_royalty_info = sp.local("token_royalty_info",
            sp.record(royalties=0, contributors={}),
            t=fa2_royalties.FA2_Royalties.ROYALTIES_TYPE)
        sp.if (auction_fa2 == self.data.items_contract):
            token_royalty_info.value = utils.fa2_get_token_royalties(auction_fa2, token_id)
        
        return token_royalty_info.value

    #
    # Views
    #
    # TODO: does it make sense to even have this?
    # without being able to get the indices...
    @sp.onchain_view(pure=True)
    def get_auction(self, auction_id):
        """Returns information about an auction."""
        sp.set_type(auction_id, sp.TNat)
        sp.result(self.data.auctions[auction_id])

    @sp.onchain_view(pure=True)
    def get_auction_price(self, auction_id):
        """Returns the current price of an auction."""
        sp.set_type(auction_id, sp.TNat)
        the_auction = sp.local("the_auction", self.data.auctions[auction_id])
        sp.result(self.get_auction_price_inline(the_auction.value))
