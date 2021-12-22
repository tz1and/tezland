import smartpy as sp

pausable_contract = sp.io.import_script_from_url("file:contracts/Pausable.py")

class TL_Dutch(pausable_contract.Pausable):
    """A simple dutch auction.
    
    The price keeps dropping until end_time is reached. First valid bid gets the token.
    """
    def __init__(self, manager, items_contract, places_contract, minter):
        self.init_storage(
            manager = manager,
            items_contract = items_contract, # TODO: instead, add a set of allow FA2 contracts
            places_contract = places_contract,
            minter = minter,
            auction_id = sp.nat(0), # the auction id counter.
            granularity = sp.nat(60), # Globally controls the granularity of price drops. in seconds.
            fees = sp.nat(25),
            paused = False,
            auctions = sp.big_map(tkey=sp.TNat, tvalue=sp.TRecord(
                owner=sp.TAddress,
                #token_address? to be able to support both items and places
                token_id=sp.TNat,
                start_price=sp.TMutez,
                end_price=sp.TMutez,
                start_time=sp.TTimestamp,
                end_time=sp.TTimestamp,
                state=sp.TNat # 0 = open, 1 = closed, 2 = cancelled. TODO
                ))
            )


    @sp.entry_point
    def set_granularity(self, granularity):
        """Call to set granularity in seconds."""
        sp.set_type(granularity, sp.TNat)
        self.onlyManager()
        self.data.granularity = granularity


    @sp.entry_point
    def set_fees(self, fees):
        """Call to set fees in permille.
        fees must be <= than 60 permille.
        """
        sp.set_type(fees, sp.TNat)
        self.onlyManager()
        sp.verify(fees <= 60, message = "FEE_ERROR") # let's not get greedy
        self.data.fees = fees


    @sp.entry_point(lazify = True)
    def create(self, params):
        """Create a dutch auction.
        
        Transfers token to auction contract.
        
        end_price must be < than start_price.
        end_time must be > than start_time
        """
        sp.set_type(params.token_id, sp.TNat)
        sp.set_type(params.start_price, sp.TMutez)
        sp.set_type(params.end_price, sp.TMutez)
        sp.set_type(params.start_time, sp.TTimestamp)
        sp.set_type(params.end_time, sp.TTimestamp)

        self.onlyUnpaused()

        # TODO: verify inputs
        sp.verify(params.start_time < params.end_time, message = "INVALID_PARAM")
        sp.verify(params.start_price > params.end_price, message = "INVALID_PARAM")

        # Create auction
        self.data.auctions[self.data.auction_id] = sp.record(
            owner=sp.sender,
            token_id=params.token_id,
            start_price=params.start_price,
            end_price=params.end_price,
            start_time=params.start_time,
            end_time=params.end_time,
            state=0
            )

        self.data.auction_id += 1

        # Transfer token (place)
        self.fa2_transfer(self.data.places_contract, sp.sender, sp.self_address, params.token_id, 1)


    @sp.entry_point(lazify = True)
    def cancel(self, auction_id):
        """Cancel an auction.

        Given it is in a cancelable state (eg 0) and owned.
        Token is transferred back to auction owner.
        """
        sp.set_type(auction_id, sp.TNat)

        self.onlyUnpaused()

        the_auction = self.data.auctions[auction_id]

        # verify ownership (manager can cancel all???)
        sp.if ~self.isManager(sp.sender):
            sp.verify(the_auction.owner == sp.sender, message = "NOT_OWNER")

        # and if it's in cancleable state
        sp.verify(the_auction.state == sp.nat(0), message = "WRONG_STATE")

        the_auction.state = sp.nat(2)

        # transfer token back to auction owner.
        self.fa2_transfer(self.data.places_contract, sp.self_address, the_auction.owner, the_auction.token_id, 1)

        # TODO: delete auction or set it to state = 2 (cancelled)?
        #del self.data.auctions[auction_id]


    @sp.entry_point(lazify = True)
    def bid(self, auction_id):
        """Bid on an auction.

        The first valid bid (value >= ask_price) gets the token.
        Overpay is transferred back to sender.
        """
        sp.set_type(auction_id, sp.TNat)

        self.onlyUnpaused()

        the_auction = self.data.auctions[auction_id]

        # make sure auction is in biddable state
        sp.verify(the_auction.state == sp.nat(0), message = "WRONG_STATE")

        # NOTE: no need to check auction has started, get_auction_price does.

        # calculate current price and verify amount sent
        # TODO: figure out if calling view on self is a good idea
        ask_price = sp.local("ask_price", sp.view("get_auction_price",
            sp.self_address,
            auction_id,
            t = sp.TMutez).open_some())
        #sp.trace(sp.now)
        #sp.trace(ask_price.value)
        # check if correct value was sent. probably best to send back overpay instead of cancel.
        sp.verify(sp.amount >= ask_price.value, message = "WRONG_AMOUNT")

        # set state to finished.
        the_auction.state = sp.nat(1)

        # Send back overpay, if there was any.
        overpay = sp.amount - ask_price.value
        sp.if overpay > sp.tez(0):
            sp.send(sp.sender, overpay)

        # calculate fees
        fee = sp.local("fee", sp.utils.mutez_to_nat(ask_price.value) * self.data.fees / sp.nat(1000))
        # send management fees
        sp.send(self.data.manager, sp.utils.nat_to_mutez(fee.value))
        # send rest of the value to seller
        sp.send(the_auction.owner, ask_price.value - sp.utils.nat_to_mutez(fee.value))

         # transfer item to buyer
        self.fa2_transfer(self.data.places_contract, sp.self_address, sp.sender, the_auction.token_id, 1)

        # TODO: delete auction or mark is as finished?
        #del self.data.auctions[auction_id]


    #
    # Views
    #
    @sp.onchain_view()
    def get_auction(self, auction_id):
        """Returns information about an auction."""
        sp.set_type(auction_id, sp.TNat)
        # TODO: decide if we want this view to error
        #sp.if self.data.auctions.contains(auction_id) == False:
        #    sp.result(sp.record(
        #        ...
        #        ))
        #sp.else:
        sp.result(self.data.auctions[auction_id])


    @sp.onchain_view()
    def get_auction_price(self, auction_id):
        """Returns the current price of an auction."""
        the_auction = self.data.auctions[auction_id]

        # check auction has started
        sp.verify(sp.now >= the_auction.start_time, "NOT_STARTED")
        # TODO: check auction state is 0.

        sp.if sp.now >= the_auction.end_time:
            sp.result(the_auction.end_price)
        sp.else:
            # alright, this works well enough. make 100% sure the math checks out (overflow, abs, etc)
            # probably by validating the input in create. to make sure intervals can't be negative.
            duration = abs(the_auction.end_time - the_auction.start_time) // self.data.granularity
            time_since_start = abs(sp.now - the_auction.start_time) // self.data.granularity
            mutez_per_sec = sp.utils.mutez_to_nat(the_auction.start_price - the_auction.end_price) // duration
            time_deduction = mutez_per_sec * time_since_start

            current_price = the_auction.start_price - sp.utils.nat_to_mutez(time_deduction)

            sp.result(current_price)


    #
    # Update code
    #
    @sp.entry_point
    def update_create(self, new_code):
        self.onlyManager()
        sp.set_entry_point("create", new_code)

    @sp.entry_point
    def update_cancel(self, new_code):
        self.onlyManager()
        sp.set_entry_point("cancel", new_code)

    @sp.entry_point
    def update_bid(self, new_code):
        self.onlyManager()
        sp.set_entry_point("bid", new_code)


    #
    # Misc
    #
    def fa2_transfer(self, fa2, from_, to_, item_id, item_amount):
        c = sp.contract(sp.TList(sp.TRecord(from_=sp.TAddress, txs=sp.TList(sp.TRecord(amount=sp.TNat, to_=sp.TAddress, token_id=sp.TNat).layout(("to_", ("token_id", "amount")))))), fa2, entry_point='transfer').open_some()
        sp.transfer(sp.list([sp.record(from_=from_, txs=sp.list([sp.record(amount=item_amount, to_=to_, token_id=item_id)]))]), sp.mutez(0), c)