import smartpy as sp

admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")

#
# Lazy map of allowed place tokens.
class Allowed_place_token_map:
    def make(self, default_allowed):
        # TODO: does this need to be a bigmap???
        return sp.big_map(l = default_allowed, tkey = sp.TAddress, tvalue = sp.TUnit)

    def add(self, map, fa2):
        map[fa2] = sp.unit

    def remove(self, map, fa2):
        del map[fa2]

    def is_allowed(self, map, fa2):
        return map.contains(fa2)

class Allowed_place_token_param:
    def get_add_type(self):
        return sp.TAddress

    def make_add(self, fa2):
        return sp.set_type_expr(fa2, self.get_add_type())

    def get_remove_type(self):
        return sp.TAddress

    def make_remove(self, fa2):
        return sp.set_type_expr(fa2, self.get_remove_type())


# NOTE:
# When a allowed place token is removed, that may lock tokens into the world.
# I think this is desired. One should make sure to only check it on adding items to places.


class AllowedPlaceTokens(admin_mixin.Administrable):
    def __init__(self, administrator, default_allowed = {}):
        self.allowed_place_tokens_map = Allowed_place_token_map()
        self.allowed_place_tokens_param = Allowed_place_token_param()
        self.update_initial_storage(
            allowed_place_tokens = self.allowed_place_tokens_map.make(default_allowed),
        )
        admin_mixin.Administrable.__init__(self, administrator = administrator)


    def onlyAllowedPlaceTokens(self, fa2):
        """Fails if not allowed"""
        fa2 = sp.set_type_expr(fa2, sp.TAddress)
        sp.verify(self.allowed_place_tokens_map.is_allowed(self.data.allowed_place_tokens, fa2),
            message = "PLACE_TOKEN_NOT_ALLOWED")


    def isAllowedPlaceToken(self, fa2):
        """Returns if place token is allowed"""
        fa2 = sp.set_type_expr(fa2, sp.TAddress)
        return sp.compute(self.allowed_place_tokens_map.is_allowed(self.data.allowed_place_tokens, fa2))


    @sp.entry_point
    def set_place_token_allowed(self, params):
        """Call to add/remove place token contracts from
        token contracts allowed in the world."""
        sp.set_type(params, sp.TList(sp.TVariant(
            add_allowed_place_token = self.allowed_place_tokens_param.get_add_type(),
            remove_allowed_place_token = self.allowed_place_tokens_param.get_remove_type()
        ).layout(("add_allowed_place_token", "remove_allowed_place_token"))))

        self.onlyAdministrator()
        
        with sp.for_("update", params) as update:
            with update.match_cases() as arg:
                with arg.match("add_allowed_place_token") as upd:
                    self.allowed_place_tokens_map.add(self.data.allowed_place_tokens, upd)
                with arg.match("remove_allowed_place_token") as upd:
                    self.allowed_place_tokens_map.remove(self.data.allowed_place_tokens, upd)


    @sp.onchain_view(pure=True)
    def is_place_token_allowed(self, fa2):
        """Returns True if an fa2 place token is allowed."""
        sp.set_type(fa2, sp.TAddress)
        sp.result(self.allowed_place_tokens_map.is_allowed(self.data.allowed_place_tokens, fa2))

