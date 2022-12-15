import smartpy as sp

from contracts.legacy import FA2_legacy, TL_Minter


class TL_Minter_v1_1(TL_Minter.TL_Minter):
    def __init__(self, administrator, items_contract, places_contract, metadata,
        name="tz1and Minter (deprecated)", description="tz1and Items and Places minter", version="1.1.0"):

        TL_Minter.TL_Minter.__init__(self, administrator,
            items_contract, places_contract, metadata, name, description, version)

    @sp.entry_point(lazify = True)
    def mint_Place(self, params):
        """This upgraded entrypoint allows the admin to update
        the v1 minter's metadata."""
        sp.set_type(params, FA2_legacy.t_mint_nft_batch)

        self.onlyAdministrator()

        sp.verify(sp.len(params) == 1, "INVALID_LENGTH")

        with sp.for_("item", params) as item:
            self.data.metadata[""] = item.metadata.get("metadata_uri", message = "NO_METADATA_URI")
