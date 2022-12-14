import smartpy as sp

from tz1and_contracts_smartpy.mixins.Administrable import Administrable
from contracts.utils.GenericLambdaProxy import GenericLambdaProxy
from contracts.legacy import FA2_legacy


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

from contracts import FA2


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
        FA2.MintFungible.__init__(self)
        FA2.Royalties.__init__(self)
        Administrable.__init__(self, admin, include_views = False)

def generateItemCollectionProxy():
    # TODO: add name/description to args.
    # TODO: should places/interiors also be a proxy?
    # TODO: should anything even be a proxy?
    class ItemCollection(
        Administrable,
        FA2.ChangeMetadata,
        FA2.MintFungible,
        FA2.BurnFungible,
        FA2.Royalties,
        FA2.Fa2Fungible,
    ):
        """tz1and Collection"""

        def __init__(self, metadata, admin, blacklist, include_views=True):
            FA2.Fa2Fungible.__init__(
                self, metadata=metadata,
                name="tz1and Collection", description="A collection of tz1and Item NFTs.",
                # NOTE: If proxied, the FA2 doesn't need to be pausable - can
                # just nuke the transfer/mint/burn entrypoints in case of emergency.
                # NOTE: similarly, invalid/banned/compromised FA2s can have their parent set to
                # the null address instead of pausing them.
                #policy=FA2.BlacklistTransfer(blacklist, FA2.PauseTransfer(FA2.OwnerOrOperatorAdhocTransfer()), True, True),
                #policy=FA2.PauseTransfer(FA2.OwnerOrOperatorAdhocTransfer()).
                #policy=FA2.BlacklistTransfer(blacklist, FA2.OwnerOrOperatorAdhocTransfer(), True, True),
                policy=FA2.OwnerOrOperatorAdhocTransfer(),
                has_royalties=True,
                allow_mint_existing=False,
                include_views=include_views
            )
            FA2.MintFungible.__init__(self)
            FA2.Royalties.__init__(self, include_views = include_views)
            Administrable.__init__(self, admin, include_views = False)

    return GenericLambdaProxy(ItemCollection)

ItemCollectionProxyBase, ItemCollectionProxyParent, ItemCollectionProxyChild = generateItemCollectionProxy()


def generatePlaceTokenProxy():
    # TODO: add name/description to args.
    # TODO: should places/interiors also be a proxy?
    # TODO: should anything even be a proxy?
    class Place(
        Administrable,
        FA2.ChangeMetadata,
        FA2.MintNft,
        FA2.OnchainviewCountTokens,
        FA2.Fa2Nft,
    ):
        """tz1and Places"""

        def __init__(self, metadata, admin, blacklist, name, description, include_views=True):
            FA2.Fa2Nft.__init__(
                self, metadata=metadata,
                name=name, description=description,
                #policy=FA2.BlacklistTransfer(blacklist, FA2.PauseTransfer(FA2.OwnerOrOperatorAdhocTransfer()), True, True),
                policy=FA2.PauseTransfer(FA2.OwnerOrOperatorAdhocTransfer()),
                include_views=include_views
            )
            FA2.MintNft.__init__(self)
            FA2.OnchainviewCountTokens.__init__(self, include_views)
            Administrable.__init__(self, admin, include_views = False)

    return GenericLambdaProxy(Place)

PlaceTokenProxyBase, PlaceTokenProxyParent, PlaceTokenProxyChild = generatePlaceTokenProxy()


# TODO: use item token proxy for public collection as well?