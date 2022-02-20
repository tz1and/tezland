import smartpy as sp

class FA2_Royalties(sp.Contract):
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

    def __init__(self):
        self.update_initial_storage(
            token_royalties=sp.big_map(tkey=sp.TNat, tvalue=FA2_Royalties.ROYALTIES_TYPE)
        )

    def validateRoyalties(self, royalties):
        """Inline function to validate royalties."""
        # royalties is of ROYALTIES_TYPE
        # Make sure absolute royalties and splits are in valid range.
        sp.verify((royalties.royalties >= FA2_Royalties.MIN_ROYALTIES) &
            (royalties.royalties <= FA2_Royalties.MAX_ROYALTIES), message="FA2_ROYALTIES_ERROR")
        sp.verify(sp.len(royalties.contributors) <= FA2_Royalties.MAX_CONTRIBUTORS, message="FA2_ROYALTIES_ERROR")
        
        # Valdate individual splits and that they add up to 1000
        total_relative = sp.local("total_splits", sp.nat(0))
        sp.for contribution in royalties.contributors.values():
            total_relative.value += contribution.relative_royalties
            # TODO: require minter role?
        sp.verify(total_relative.value == 1000, message="FA2_ROYALTIES_ERROR")

    def setRoyalties(self, token_id, royalties):
        """Inline function to be used in mint."""
        # royalties is of ROYALTIES_TYPE
        self.data.token_royalties[token_id] = royalties

    @sp.onchain_view(pure=True)
    def get_token_royalties(self, token_id):
        """Returns the token royalties information"""
        sp.set_type(token_id, sp.TNat)
        sp.result(self.data.token_royalties.get(token_id, default_value=sp.record(royalties=sp.nat(0), contributors={})))

    # TODO: implement versum views?