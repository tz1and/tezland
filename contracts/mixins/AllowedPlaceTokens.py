import smartpy as sp


allowedPlaceLimitsType = sp.TRecord(
    chunk_limit = sp.TNat,
    chunk_item_limit = sp.TNat
).layout(("chunk_limit", "chunk_item_limit"))

#
# Lazy map of allowed place tokens.
class Allowed_place_token_map:
    def make(self, default_allowed):
        return sp.map(l = default_allowed, tkey = sp.TAddress, tvalue = allowedPlaceLimitsType)

    def add(self, map, fa2, place_limits):
        map[fa2] = place_limits

    def remove(self, map, fa2):
        del map[fa2]

    def is_allowed(self, map, fa2):
        return map.contains(fa2)

    def get_limits(self, map, fa2):
        return map.get(fa2, message = "PLACE_TOKEN_NOT_ALLOWED")

t_set_allowed_place_token_params = sp.TList(sp.TVariant(
    add = sp.TMap(sp.TAddress, allowedPlaceLimitsType),
    remove = sp.TSet(sp.TAddress)
).layout(("add", "remove")))


# NOTE:
# When a allowed place token is removed, that may lock tokens into the world.
# I think this is desired. One should make sure to only check it on adding items to places.


# Mixins required: Administrable
class AllowedPlaceTokens:
    def __init__(self, default_allowed = {}):
        self.allowed_place_tokens_map = Allowed_place_token_map()
        self.update_initial_storage(
            place_tokens = self.allowed_place_tokens_map.make(default_allowed),
        )


    def onlyAllowedPlaceTokens(self, fa2):
        """Fails if not allowed"""
        sp.set_type(fa2, sp.TAddress)
        sp.verify(self.allowed_place_tokens_map.is_allowed(self.data.place_tokens, fa2),
            message = "PLACE_TOKEN_NOT_ALLOWED")


    def isAllowedPlaceToken(self, fa2):
        """Returns if place token is allowed"""
        sp.set_type(fa2, sp.TAddress)
        return sp.compute(self.allowed_place_tokens_map.is_allowed(self.data.place_tokens, fa2))


    def getAllowedPlaceTokenLimits(self, fa2):
        """Returns allowed place limits or fails"""
        sp.set_type(fa2, sp.TAddress)
        return sp.compute(self.allowed_place_tokens_map.get_limits(self.data.place_tokens, fa2))


    @sp.entry_point(lazify=True, parameter_type=t_set_allowed_place_token_params)
    def set_allowed_place_token(self, params):
        """Call to add/remove place token contracts from
        token contracts allowed in the world."""
        self.onlyAdministrator()
        
        with sp.for_("update", params) as update:
            with update.match_cases() as arg:
                with arg.match("add") as add:
                    with sp.for_("add_item", add.items()) as add_item:
                        self.allowed_place_tokens_map.add(self.data.place_tokens, add_item.key, add_item.value)
                with arg.match("remove") as remove:
                    with sp.for_("remove_element", remove.elements()) as remove_element:
                        self.allowed_place_tokens_map.remove(self.data.place_tokens, remove_element)


    @sp.onchain_view(pure=True)
    def get_allowed_place_tokens(self):
        """Returns allowed place token limits."""
        sp.result(self.data.place_tokens)

