import smartpy as sp

from contracts import TL_Dutch
from contracts.utils import FA2Utils, ErrorMessages


class TL_Dutch_v1_1(TL_Dutch.TL_Dutch):
    def __init__(self, administrator, items_contract, places_contract, metadata,
        name="tz1and Dutch Auctions (deprecated)", description="tz1and Places and Items Dutch auctions", version="1.1.0"):

        TL_Dutch.TL_Dutch.__init__(self, administrator,
            items_contract, places_contract, metadata, name, description, version)


    @sp.entry_point(lazify = True)
    def cancel(self, params):
        """Upgraded ep to cancel an auction.

        Administrator now has permissio to cancel auctions. Needed for upgrade.
        """
        sp.set_type(params, sp.TRecord(
            auction_id = sp.TNat,
            extension = TL_Dutch.extensionArgType
        ).layout(("auction_id", "extension")))

        the_auction = self.data.auctions[params.auction_id]

        # If sender is not administrator, check onlyUnpaused and auction owner.
        with sp.if_(~self.isAdministrator(sp.sender)):
            self.onlyUnpaused()
            sp.verify(the_auction.owner == sp.sender, message = ErrorMessages.not_owner())

        # transfer token back to auction owner.
        FA2Utils.fa2_transfer(the_auction.fa2, sp.self_address, the_auction.owner, the_auction.token_id, 1)

        del self.data.auctions[params.auction_id]


    @sp.entry_point(lazify = True)
    def bid(self, params):
        """Upgraded ep - repurposed to update metadata."""
        sp.set_type(params, sp.TRecord(
            auction_id = sp.TNat,
            extension = TL_Dutch.extensionArgType
        ).layout(("auction_id", "extension")))

        self.onlyAdministrator()

        # Get ext map.
        ext_map = params.extension.open_some(message = "NO_EXT_PARAMS")

        # Make sure metadata_uri exists and update contract metadata.
        self.data.metadata[""] = ext_map.get("metadata_uri", message = "NO_METADATA_URI")