import smartpy as sp

# TODO: should get_token_royalties fail if token doesn't exist?

class FA2_Royalties:
    CONTRIBUTOR_MAP_TYPE = sp.TMap(
        sp.TAddress,
        # The relative royalties, per contributor, must add up to 1000. And the role.
        sp.TRecord(
            relative_royalties=sp.TNat,
            role=sp.TString
        ).layout(("relative_royalties", "role")))

    ROYALTIES_TYPE = sp.TRecord(
        # The absolute royalties in permille.
        royalties=sp.TNat,
        # The minter address
        contributors=CONTRIBUTOR_MAP_TYPE
    ).layout(("royalties", "contributors"))

    MIN_ROYALTIES = sp.nat(0)
    MAX_ROYALTIES = sp.nat(250)
    MAX_CONTRIBUTORS = sp.nat(3)

    def validateRoyalties(self, royalties):
        """Inline function to validate royalties."""
        royalties = sp.set_type_expr(royalties, FA2_Royalties.ROYALTIES_TYPE)
        # Make sure absolute royalties and splits are in valid range.
        sp.verify((royalties.royalties >= FA2_Royalties.MIN_ROYALTIES) &
            (royalties.royalties <= FA2_Royalties.MAX_ROYALTIES), message="FA2_ROYALTIES_ERROR")
        sp.verify(sp.len(royalties.contributors) <= FA2_Royalties.MAX_CONTRIBUTORS, message="FA2_ROYALTIES_ERROR")
        
        # Valdate individual splits and that they add up to 1000
        total_relative = sp.local("total_splits", sp.nat(0))
        with sp.for_("contribution", royalties.contributors.values()) as contribution:
            total_relative.value += contribution.relative_royalties
            # TODO: require minter role?
        sp.verify(total_relative.value == 1000, message="FA2_ROYALTIES_ERROR")

    @sp.onchain_view(pure=True)
    def get_token_royalties(self, token_id):
        """Returns the token royalties information"""
        sp.set_type(token_id, sp.TNat)
        # TODO: should this fail if token doesn't exist?
        with sp.if_(self.data.token_extra.contains(token_id)):
            sp.result(self.data.token_extra[token_id].royalty_info)
        with sp.else_():
            sp.result(sp.record(royalties=sp.nat(0), contributors={}))

    # TODO: implement versum views?