import smartpy as sp

admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")


# TODO: is_fa2_permitted/get_fa2_permitted is probably not needed? maybe for interop...
# TODO: test getRoyaltiesForPermittedFA2

permittedFA2MapValueType = sp.TRecord(
    whitelist_enabled = sp.TBool, # If the token is whitelisted.
    whitelist_admin = sp.TAddress, # The account that is the whitelist admin
).layout(("whitelist_enabled", "whitelist_admin"))

#
# Lazy map of permitted FA2 tokens for 'other' type.
class PermittedFA2Map(utils.GenericMap):
    def __init__(self) -> None:
        super().__init__(sp.TAddress, permittedFA2MapValueType, default_value=None, get_error="TOKEN_NOT_PERMITTED")

class PermittedFA2Params:
    @classmethod
    def get_add_type(cls):
        return sp.TRecord(
            fa2 = sp.TAddress,
            props = permittedFA2MapValueType
        ).layout(("fa2", "props"))

    @classmethod
    def make_add(cls, fa2, props):
        r = sp.record(fa2 = fa2,
            props = props)
        return sp.set_type_expr(r, cls.get_add_type())

    @classmethod
    def get_remove_type(cls):
        return sp.TAddress

    @classmethod
    def make_remove(cls, fa2):
        return sp.set_type_expr(fa2, cls.get_remove_type())


# NOTE:
# When a permitted FA2 is removed, that will break swaps, auctions, etc.
# I think this is desired. But make sure to give a good error message.


class FA2PermissionsAndWhitelist(admin_mixin.Administrable):
    def __init__(self, administrator, default_permitted = {}):
        self.permitted_fa2_map = PermittedFA2Map()

        self.update_initial_storage(
            permitted_fa2 = self.permitted_fa2_map.make(default_permitted),
        )

        admin_mixin.Administrable.__init__(self, administrator = administrator)


    def onlyPermittedFA2(self, fa2):
        """Fails if not permitted"""
        sp.set_type(fa2, sp.TAddress)
        sp.verify(self.permitted_fa2_map.contains(self.data.permitted_fa2, fa2),
            message = "TOKEN_NOT_PERMITTED")


    def getPermittedFA2Props(self, fa2):
        """Returns permitted props or fails if not permitted"""
        sp.set_type(fa2, sp.TAddress)
        return sp.compute(self.permitted_fa2_map.get(self.data.permitted_fa2, fa2))


    @sp.entry_point
    def set_fa2_permitted(self, params):
        """Call to add/remove fa2 contract from
        token contracts permitted for 'other' type items."""
        sp.set_type(params, sp.TList(sp.TVariant(
            add_permitted = PermittedFA2Params.get_add_type(),
            remove_permitted = PermittedFA2Params.get_remove_type()
        ).layout(("add_permitted", "remove_permitted"))))

        self.onlyAdministrator()
        
        with sp.for_("update", params) as update:
            with update.match_cases() as arg:
                with arg.match("add_permitted") as upd:
                    self.permitted_fa2_map.add(self.data.permitted_fa2, upd.fa2, upd.props)
                with arg.match("remove_permitted") as upd:
                    self.permitted_fa2_map.remove(self.data.permitted_fa2, upd)


    @sp.onchain_view(pure=True)
    def is_fa2_permitted(self, fa2):
        """Returns True if an fa2 is permitted."""
        sp.set_type(fa2, sp.TAddress)
        sp.result(self.permitted_fa2_map.contains(self.data.permitted_fa2, fa2))


    @sp.onchain_view(pure=True)
    def get_fa2_permitted(self, fa2):
        """Returns permitted fa2 props."""
        sp.set_type(fa2, sp.TAddress)
        sp.result(self.permitted_fa2_map.get(self.data.permitted_fa2, fa2))

