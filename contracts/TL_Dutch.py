import smartpy as sp

pausable_contract = sp.io.import_script_from_url("file:contracts/Pausable.py")

# TODO: test royalties for item token
# TODO: test auction with end price 0!!!!!
# TODO: use lazy set? probably not, should never allow anything other than places and items.

class TL_Dutch(pausable_contract.Pausable):
    """A simple dutch auction.
    
    The price keeps dropping until end_time is reached. First valid bid gets the token.
    """
    def __init__(self, manager, items_contract, places_contract, minter, metadata):
        self.init_storage(
            manager = manager,
            items_contract = items_contract,
            permitted_fa2 = sp.set([places_contract], t=sp.TAddress),
            minter = minter,
            metadata = metadata,
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
                fa2=sp.TAddress
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
        Fees must be <= than 60 permille.
        """
        sp.set_type(fees, sp.TNat)
        self.onlyManager()
        sp.verify(fees <= 60, message = "FEE_ERROR") # let's not get greedy
        self.data.fees = fees

    @sp.entry_point
    def set_permitted_fa2(self, params):
        """Call to add/remove fa2 contract from
        token contracts permitted for auctions."""
        sp.set_type(params.fa2, sp.TAddress)
        sp.set_type(params.permitted, sp.TBool)
        self.onlyManager()
        sp.if params.permitted == True:
            self.data.permitted_fa2.add(params.fa2)
        sp.else:
            self.data.permitted_fa2.remove(params.fa2)

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
        sp.set_type(params.fa2, sp.TAddress)

        self.onlyUnpaused()

        # verify inputs
        sp.verify(self.data.permitted_fa2.contains(params.fa2), message = "TOKEN_NOT_PERMITTED")
        sp.verify(params.start_time < params.end_time, message = "INVALID_PARAM")
        sp.verify(params.start_price > params.end_price, message = "INVALID_PARAM")

        # call fa2_balance or is_operator to avoid burning gas on bigmap insert.
        sp.verify(self.fa2_get_balance(params.fa2, params.token_id, sp.sender) > 0, message = "NOT_OWNER")

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
        self.fa2_transfer(params.fa2, sp.sender, sp.self_address, params.token_id, 1)


    @sp.entry_point(lazify = True)
    def cancel(self, auction_id):
        """Cancel an auction.

        Given it is owned.
        Token is transferred back to auction owner.
        """
        sp.set_type(auction_id, sp.TNat)

        self.onlyUnpaused()

        the_auction = self.data.auctions[auction_id]

        sp.verify(the_auction.owner == sp.sender, message = "NOT_OWNER")

        # transfer token back to auction owner.
        self.fa2_transfer(the_auction.fa2, sp.self_address, the_auction.owner, the_auction.token_id, 1)

        del self.data.auctions[auction_id]


    @sp.entry_point(lazify = True)
    def bid(self, auction_id):
        """Bid on an auction.

        The first valid bid (value >= ask_price) gets the token.
        Overpay is transferred back to sender.
        """
        sp.set_type(auction_id, sp.TNat)

        self.onlyUnpaused()

        the_auction = sp.local("the_auction", self.data.auctions[auction_id])

        # check auction has started
        sp.verify(sp.now >= the_auction.value.start_time, message = "NOT_STARTED")

        # calculate current price and verify amount sent
        ask_price = sp.local("ask_price", sp.view("get_auction_price",
            sp.self_address,
            auction_id,
            t = sp.TMutez).open_some())
        #sp.trace(sp.now)
        #sp.trace(ask_price.value)

        # check if correct value was sent. probably best to send back overpay instead of cancel.
        sp.verify(sp.amount >= ask_price.value, message = "WRONG_AMOUNT")

        # Send back overpay, if there was any.
        overpay = sp.amount - ask_price.value
        sp.if overpay > sp.tez(0):
            sp.send(sp.sender, overpay)

        sp.if ask_price.value != sp.tez(0):
            token_royalties = sp.compute(self.get_royalties_if_item(the_auction.value.token_id, the_auction.value.fa2))

            # calculate fees
            fee = sp.compute(sp.utils.mutez_to_nat(ask_price.value) * (token_royalties.royalties + self.data.fees) / sp.nat(1000))
            royalties = sp.compute(token_royalties.royalties * fee / (token_royalties.royalties + self.data.fees))

            # send royalties to creator, if any.
            sp.if royalties > 0:
                sp.send(token_royalties.creator, sp.utils.nat_to_mutez(royalties))

            # send management fees
            sp.send(self.data.manager, sp.utils.nat_to_mutez(abs(fee - royalties)))
            # send rest of the value to seller
            sp.send(the_auction.value.owner, ask_price.value - sp.utils.nat_to_mutez(fee))

         # transfer item to buyer
        self.fa2_transfer(the_auction.value.fa2, sp.self_address, sp.sender, the_auction.value.token_id, 1)

        del self.data.auctions[auction_id]


    #
    # Views
    #
    @sp.onchain_view()
    def get_auction(self, auction_id):
        """Returns information about an auction."""
        sp.set_type(auction_id, sp.TNat)
        sp.result(self.data.auctions[auction_id])


    @sp.onchain_view()
    def get_auction_price(self, auction_id):
        """Returns the current price of an auction."""
        sp.set_type(auction_id, sp.TNat)
        the_auction = self.data.auctions[auction_id]

        # return start price if it hasn't started
        sp.if sp.now <= the_auction.start_time:
            sp.result(the_auction.start_price)
        sp.else:
            # return end price if it's over
            sp.if sp.now >= the_auction.end_time:
                sp.result(the_auction.end_price)
            sp.else:
                # alright, this works well enough. make 100% sure the math checks out (overflow, abs, etc)
                # probably by validating the input in create. to make sure intervals can't be negative.
                duration = abs(the_auction.end_time - the_auction.start_time) // self.data.granularity
                time_since_start = abs(sp.now - the_auction.start_time) // self.data.granularity
                mutez_per_interval = sp.utils.mutez_to_nat(the_auction.start_price - the_auction.end_price) // duration
                time_deduction = mutez_per_interval * time_since_start

                current_price = the_auction.start_price - sp.utils.nat_to_mutez(time_deduction)

                sp.result(current_price)
    
    @sp.onchain_view()
    def get_permitted_fa2(self):
        """Returns the set of permitted fa2 contracts."""
        sp.result(self.data.permitted_fa2)


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
    def fa2_transfer(self, fa2, from_, to_, token_id, item_amount):
        c = sp.contract(sp.TList(sp.TRecord(from_=sp.TAddress, txs=sp.TList(sp.TRecord(amount=sp.TNat, to_=sp.TAddress, token_id=sp.TNat).layout(("to_", ("token_id", "amount")))))), fa2, entry_point='transfer').open_some()
        sp.transfer(sp.list([sp.record(from_=from_, txs=sp.list([sp.record(amount=item_amount, to_=to_, token_id=token_id)]))]), sp.mutez(0), c)

    def fa2_get_balance(self, fa2, token_id, owner):
        return sp.view("get_balance", fa2,
            sp.set_type_expr(
                sp.record(owner = owner, token_id = token_id),
                sp.TRecord(
                    owner = sp.TAddress,
                    token_id = sp.TNat
                ).layout(("owner", "token_id"))),
            t = sp.TNat).open_some()

    def minter_get_item_royalties(self, token_id):
        return sp.view("get_item_royalties",
            self.data.minter,
            token_id,
            t = sp.TRecord(creator=sp.TAddress, royalties=sp.TNat)).open_some()

    def get_royalties_if_item(self, token_id, auction_fa2):
        sp.set_type(token_id, sp.TNat)
        sp.set_type(auction_fa2, sp.TAddress)

        token_royalties = sp.local("token_royalties", sp.record(creator=sp.self_address, royalties=0))
        sp.if (auction_fa2 == self.data.items_contract):
            token_royalties.value = self.minter_get_item_royalties(token_id)
        
        return token_royalties.value
