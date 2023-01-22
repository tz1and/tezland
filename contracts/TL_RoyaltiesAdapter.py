import smartpy as sp

from contracts import TL_TokenRegistry, TL_LegacyRoyalties, TL_RoyaltiesAdapterLegacyAndV1, FA2
from contracts.utils import EnvUtils, ErrorMessages, TokenTransfer


def sendValueRoyaltiesFeesInline(fees, fees_to, rate, issuer, item_royalty_info, primary):
    """Inline function for sending royalties, fees, etc."""
    sp.set_type(fees, sp.TNat)
    sp.set_type(fees_to, sp.TAddress)
    sp.set_type(rate, sp.TMutez)
    sp.set_type(issuer, sp.TAddress)
    sp.set_type(item_royalty_info, FA2.t_royalties_interop)
    sp.set_type(primary, sp.TBool)

    # Collect amounts to send in a map.
    sendMap = TokenTransfer.TokenSendMap()

    # First, we take our fees are in permille.
    fees_amount = sp.compute(sp.split_tokens(rate, fees, sp.nat(1000)))
    sendMap.add(fees_to, fees_amount)

    value_after_fees = sp.compute(rate - fees_amount)

    # If a primary sale, split entire value (minus fees) according to royalties.
    total_shares = sp.local("total_shares", item_royalty_info.total)
    with sp.if_(primary):
        # Loop over all the shares to find the total shares.
        with sp.for_("share_value", item_royalty_info.shares.values()) as share_value:
            total_shares.value += share_value

    # Send royalties according to total and send remaining value to issuer or place owner.
    total_royalties = sp.local("total_royalties", sp.mutez(0))
    with sp.for_("share_item", item_royalty_info.shares.items()) as share_item:
        # Calculate amount to be paid from absolute share.
        share_mutez = sp.compute(sp.split_tokens(value_after_fees, share_item.value, total_shares.value))
        sendMap.add(share_item.key, share_mutez)
        total_royalties.value += share_mutez

    # Send rest of the value to seller. Should throw if royalties total > rate.
    left_amount = sp.compute(sp.sub_mutez(value_after_fees, total_royalties.value).open_some(ErrorMessages.royalties_error()))
    sendMap.add(issuer, left_amount)

    # Make sure it all adds up correctly!
    sp.verify((fees_amount + total_royalties.value + left_amount) == rate, ErrorMessages.royalties_error())

    # Transfer.
    sendMap.transfer()


@EnvUtils.view_helper
def getRoyalties(royalties_adaper, token_key) -> sp.Expr:
    return sp.view("get_royalties", sp.set_type_expr(royalties_adaper, sp.TAddress),
        sp.set_type_expr(token_key, TL_LegacyRoyalties.t_token_key),
        t = FA2.t_royalties_interop)


#
# Royalties adapter contract.
class TL_RoyaltiesAdapter(sp.Contract):
    def __init__(self, registry, v1_and_legacy_adapter, exception_optimization_level="default-line"):
        sp.Contract.__init__(self)

        self.add_flag("exceptions", exception_optimization_level)
        #self.add_flag("erase-comments")

        registry = sp.set_type_expr(registry, sp.TAddress)
        v1_and_legacy_adapter = sp.set_type_expr(v1_and_legacy_adapter, sp.TAddress)

        self.init_storage(
            registry = registry,
            v1_and_legacy_adapter = v1_and_legacy_adapter
        )


    @sp.entry_point
    def default(self):
        sp.failwith(sp.unit)


    @sp.onchain_view(pure=True)
    def get_royalties(self, token_key):
        """Gets token royalties and/or validate signed royalties."""
        sp.set_type(token_key, TL_LegacyRoyalties.t_token_key)

        royalties_type = sp.compute(TL_TokenRegistry.getRoyaltiesType(self.data.registry, token_key.fa2).open_some(sp.unit))

        with sp.if_(royalties_type == TL_TokenRegistry.royaltiesTz1andV2):
            # Just return V2 royalties.
            sp.result(FA2.getRoyalties(token_key.fa2, token_key.id).open_some(sp.unit))
        with sp.else_():
            # Call the V1 and legacy adapter.
            sp.result(TL_RoyaltiesAdapterLegacyAndV1.getRoyalties(self.data.v1_and_legacy_adapter,
                token_key, royalties_type).open_some(sp.unit))
