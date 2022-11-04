import smartpy as sp

FA2_legacy = sp.io.import_script_from_url("file:contracts/legacy/FA2_legacy.py")
admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")

class tz1andPlaces(
    admin_mixin.Administrable,
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
        admin_mixin.Administrable.__init__(self, admin)

class tz1andItems(
    admin_mixin.Administrable,
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
        admin_mixin.Administrable.__init__(self, admin)

class tz1andDAO(
    admin_mixin.Administrable,
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
        admin_mixin.Administrable.__init__(self, admin)

# V2

FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")

class tz1andInteriors(
    admin_mixin.Administrable,
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
        admin_mixin.Administrable.__init__(self, admin)

class tz1andPlaces_v2(
    admin_mixin.Administrable,
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
        admin_mixin.Administrable.__init__(self, admin)