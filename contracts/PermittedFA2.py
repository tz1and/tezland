import smartpy as sp

admin_contract = sp.io.import_script_from_url("file:contracts/Administrable.py")

# TODO: is_fa2_permitted/get_fa2_permitted is probably not needed? maybe for interop...

permittedFA2MapValueType = sp.TRecord(
    swap_allowed = sp.TBool, # If the token is allowed to be swapped. This is a little extra.
    has_royalties = sp.TBool, # If the token has royalties.
    royalties_view = sp.TBool # If the token has a tz1and-like royalties view.
).layout(("swap_allowed", ("has_royalties", "royalties_view")))

#
# Lazy map of permitted FA2 tokens for 'other' type.
class Permitted_fa2_map:
    def make(self, default_permitted):
        return sp.big_map(l = default_permitted, tkey = sp.TAddress, tvalue = permittedFA2MapValueType)
    def add(self, map, fa2, allow_swap):
        map[fa2] = allow_swap
    def remove(self, map, fa2):
        del map[fa2]
    def is_permitted(self, map, fa2):
        return map.contains(fa2)
    def get_props(self, map, fa2):
        return map.get(fa2)

class Permitted_fa2_param:
    def get_add_type(self):
        return sp.TRecord(
            fa2 = sp.TAddress,
            props = permittedFA2MapValueType
        ).layout(("fa2", "props"))
    def make_add(self, fa2, props):
        r = sp.record(fa2 = fa2,
            props = props)
        return sp.set_type_expr(r, self.get_add_type())
    def get_remove_type(self):
        return sp.TAddress
    def make_remove(self, fa2):
        return sp.set_type_expr(fa2, self.get_remove_type())


# NOTE:
# When a permitted FA2 is removed, that will break swaps, auctions, etc.
# I think this is desired. But make sure to give a good error message.


class PermittedFA2(admin_contract.Administrable):
    def __init__(self, administrator, default_permitted = {}):
        self.permitted_fa2_map = Permitted_fa2_map()
        self.permitted_fa2_param = Permitted_fa2_param()
        self.update_initial_storage(
            permitted_fa2 = self.permitted_fa2_map.make(default_permitted),
        )
        admin_contract.Administrable.__init__(self, administrator = administrator)

    def onlyPermittedFA2(self, fa2):
        """Fails if not permitted"""
        sp.verify(self.permitted_fa2_map.is_permitted(self.data.permitted_fa2, fa2),
            message = "TOKEN_NOT_PERMITTED")

    def getPermittedFA2Props(self, fa2):
        """Returns permitted props or fails if not permitted"""
        sp.verify(self.permitted_fa2_map.is_permitted(self.data.permitted_fa2, fa2),
            message = "TOKEN_NOT_PERMITTED")
        return sp.compute(self.permitted_fa2_map.get_props(self.data.permitted_fa2, fa2))

    @sp.entry_point
    def set_fa2_permitted(self, params):
        """Call to add/remove fa2 contract from
        token contracts permitted for 'other' type items."""
        sp.set_type(params, sp.TList(sp.TVariant(
            add_permitted = self.permitted_fa2_param.get_add_type(),
            remove_permitted = self.permitted_fa2_param.get_remove_type()
        ).layout(("add_permitted", "remove_permitted"))))

        self.onlyAdministrator()
        
        # NOTE: DON'T add Items or Places, lol. Not going to verify, should probably be.
        # TODO: validate?
        
        sp.for update in params:
            with update.match_cases() as arg:
                with arg.match("add_permitted") as upd:
                    self.permitted_fa2_map.add(self.data.permitted_fa2, upd.fa2, upd.props)
                with arg.match("remove_permitted") as upd:
                    self.permitted_fa2_map.remove(self.data.permitted_fa2, upd)

    @sp.onchain_view(pure=True)
    def is_fa2_permitted(self, fa2):
        """Returns True if an fa2 is permitted."""
        sp.set_type(fa2, sp.TAddress)
        sp.result(self.permitted_fa2_map.is_permitted(self.data.permitted_fa2, fa2))

    @sp.onchain_view(pure=True)
    def get_fa2_permitted(self, fa2):
        """Returns permitted fa2 props."""
        sp.set_type(fa2, sp.TAddress)
        sp.result(self.permitted_fa2_map.get_props(self.data.permitted_fa2, fa2))

