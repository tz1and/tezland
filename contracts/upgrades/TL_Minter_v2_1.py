import smartpy as sp

from contracts import FA2, TL_Minter_v2, TL_Blacklist
from contracts.utils import ErrorMessages


class TL_Minter_v2_1(TL_Minter_v2.TL_Minter_v2):
    def __init__(self, administrator, registry, blacklist, metadata, version="2.1.0"):
        self.blacklist = sp.set_type_expr(blacklist, sp.TAddress)
        TL_Minter_v2.TL_Minter_v2.__init__(self, administrator,
            registry, metadata, version)

    #
    # Public entry points
    #
    @sp.entry_point(lazify = True)
    def mint_public(self, params):
        """Minting items in a public collection"""
        sp.set_type(params, sp.TRecord(
            collection = sp.TAddress,
            to_ = sp.TAddress,
            amount = sp.TNat,
            royalties = FA2.t_royalties_shares,
            metadata = sp.TBytes
        ).layout(("collection", ("to_", ("amount", ("royalties", "metadata"))))))

        self.onlyUnpaused()
        self.onlyPublicCollection(params.collection)

        sp.compute(TL_Blacklist.checkBlacklisted(self.blacklist, sp.set([sp.sender, params.to_])).open_some(sp.unit))

        sp.verify((params.amount > 0) & (params.amount <= 10000), message = ErrorMessages.parameter_error())

        FA2.validateRoyalties(params.royalties, self.data.settings.max_royalties, self.data.settings.max_contributors)

        FA2.fa2_fungible_royalties_mint(
            [sp.record(
                to_=params.to_,
                amount=params.amount,
                token=sp.variant("new", sp.record(
                    metadata={ '' : params.metadata },
                    royalties=params.royalties))
            )],
            params.collection)


    #
    # Private entry points
    #
    @sp.entry_point(lazify = True)
    def mint_private(self, params):
        """Minting items in a private collection."""
        sp.set_type(params, sp.TRecord(
            collection = sp.TAddress,
            to_ = sp.TAddress,
            amount = sp.TNat,
            royalties = FA2.t_royalties_shares,
            metadata = sp.TBytes
        ).layout(("collection", ("to_", ("amount", ("royalties", "metadata"))))))

        self.onlyUnpaused()
        self.onlyOwnerOrCollaboratorPrivate(params.collection, sp.sender)

        sp.compute(TL_Blacklist.checkBlacklisted(self.blacklist, sp.set([sp.sender, params.to_])).open_some(sp.unit))

        sp.verify((params.amount > 0) & (params.amount <= 10000), message = ErrorMessages.parameter_error())

        FA2.validateRoyalties(params.royalties, self.data.settings.max_royalties, self.data.settings.max_contributors)

        FA2.fa2_fungible_royalties_mint(
            [sp.record(
                to_=params.to_,
                amount=params.amount,
                token=sp.variant("new", sp.record(
                    metadata={ '' : params.metadata },
                    royalties=params.royalties))
            )],
            params.collection)
