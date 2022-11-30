import smartpy as sp

Administrable = sp.io.import_script_from_url("file:contracts/Administrable.py").Administrable
FA2_legacy = sp.io.import_script_from_url("file:contracts/legacy/FA2_legacy.py")


class tz1andPlaces(
    Administrable,
    FA2_legacy.ChangeMetadata,
    FA2_legacy.MintNft,
    FA2_legacy.OnchainviewCountTokens,
    FA2_legacy.Fa2Nft,
):
    """tz1and Places"""

    def __init__(self, metadata, admin):
        FA2_legacy.Fa2Nft.__init__(
            self, metadata=metadata,
            name="tz1and Places", description="tz1and Place FA2 Tokens.",
            policy=FA2_legacy.PauseTransfer(FA2_legacy.OwnerOrOperatorAdhocTransfer())
        )
        Administrable.__init__(self, admin)

class tz1andItems(
    Administrable,
    FA2_legacy.ChangeMetadata,
    FA2_legacy.MintFungible,
    FA2_legacy.BurnFungible,
    FA2_legacy.Royalties,
    FA2_legacy.Fa2Fungible,
):
    """tz1and Items"""

    def __init__(self, metadata, admin):
        FA2_legacy.Fa2Fungible.__init__(
            self, metadata=metadata,
            name="tz1and Items", description="tz1and Item FA2 Tokens.",
            policy=FA2_legacy.PauseTransfer(FA2_legacy.OwnerOrOperatorAdhocTransfer()), has_royalties=True,
            allow_mint_existing=False
        )
        FA2_legacy.Royalties.__init__(self)
        Administrable.__init__(self, admin)

class tz1andDAO(
    Administrable,
    FA2_legacy.ChangeMetadata,
    FA2_legacy.MintSingleAsset,
    FA2_legacy.Fa2SingleAsset,
):
    """tz1and DAO"""

    def __init__(self, metadata, admin):
        FA2_legacy.Fa2SingleAsset.__init__(
            self, metadata=metadata,
            name="tz1and DAO", description="tz1and DAO FA2 Tokens."
        )
        Administrable.__init__(self, admin)

# V2

FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")

class tz1andInteriors(
    Administrable,
    FA2.ChangeMetadata,
    FA2.MintNft,
    FA2.OnchainviewCountTokens,
    FA2.Fa2Nft,
):
    """tz1and Interiors"""

    def __init__(self, metadata, admin):
        FA2.Fa2Nft.__init__(
            self, metadata=metadata,
            name="tz1and Interiors", description="tz1and Interior FA2 Tokens.",
            policy=FA2.PauseTransfer(FA2.OwnerOrOperatorAdhocTransfer())
        )
        Administrable.__init__(self, admin, include_views = False)

class tz1andPlaces_v2(
    Administrable,
    FA2.ChangeMetadata,
    FA2.MintNft,
    FA2.OnchainviewCountTokens,
    FA2.Fa2Nft,
):
    """tz1and Places"""

    def __init__(self, metadata, admin):
        FA2.Fa2Nft.__init__(
            self, metadata=metadata,
            name="tz1and Places", description="tz1and Place FA2 Tokens (v2).",
            policy=FA2.PauseTransfer(FA2.OwnerOrOperatorAdhocTransfer())
        )
        Administrable.__init__(self, admin, include_views = False)

class tz1andItems_v2(
    Administrable,
    FA2.ChangeMetadata,
    FA2.MintFungible,
    FA2.BurnFungible,
    FA2.Royalties,
    FA2.Fa2Fungible,
):
    """tz1and Items"""

    def __init__(self, metadata, admin):
        FA2.Fa2Fungible.__init__(
            self, metadata=metadata,
            name="tz1and Items", description="tz1and Item FA2 Tokens.",
            policy=FA2.PauseTransfer(FA2.OwnerOrOperatorAdhocTransfer()), has_royalties=True,
            allow_mint_existing=False
        )
        FA2.Royalties.__init__(self)
        Administrable.__init__(self, admin, include_views = False)