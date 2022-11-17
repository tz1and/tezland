import smartpy as sp

admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")


# TODO: get_fa2_permitted is probably not needed? maybe for interop...


permittedFA2MapValueType = sp.TRecord(
    whitelist_enabled = sp.TBool, # If the token is whitelisted.
    whitelist_admin = sp.TAddress, # The account that is the whitelist admin
).layout(("whitelist_enabled", "whitelist_admin"))

#
# Map of permitted FA2 tokens for 'other' type.
class PermittedFA2Map(utils.GenericMap):
    def __init__(self) -> None:
        super().__init__(sp.TAddress, permittedFA2MapValueType, default_value=None, get_error="TOKEN_NOT_PERMITTED", big_map=False)

#
# Lazy map of whitelist entries.
t_whitelist_key = sp.TRecord(
    fa2 = sp.TAddress,
    user = sp.TAddress
).layout(("fa2", "user"))

class FA2WhitelistMap(utils.GenericMap):
    def __init__(self) -> None:
        super().__init__(t_whitelist_key, sp.TUnit, default_value=sp.unit, get_error="NOT_WHITELISTED")

#
# Parameters for permitted fa2 management ep.
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
        self.whitelist_map = FA2WhitelistMap()

        self.update_initial_storage(
            permitted_fa2 = self.permitted_fa2_map.make(default_permitted),
            whitelist = self.whitelist_map.make()
        )

        admin_mixin.Administrable.__init__(self, administrator = administrator)


    def getPermittedFA2Props(self, fa2):
        """Returns permitted props or fails if not permitted"""
        sp.set_type(fa2, sp.TAddress)
        return sp.compute(self.permitted_fa2_map.get(self.data.permitted_fa2, fa2))

    def isWhitelistedForFA2(self, fa2, user):
        """If an address is whitelisted."""
        sp.set_type(fa2, sp.TAddress)
        sp.set_type(user, sp.TAddress)
        return self.whitelist_map.contains(self.data.whitelist, sp.record(fa2=fa2, user=user))

    def onlyWhitelistedForFA2(self, fa2, user):
        """Fails if whitelist enabled address is not whitelisted.
        and returns fa2 props."""
        sp.set_type(fa2, sp.TAddress)
        sp.set_type(user, sp.TAddress)
        fa2_props = sp.compute(self.getPermittedFA2Props(fa2))
        with sp.if_(fa2_props.whitelist_enabled):
            sp.verify(self.whitelist_map.contains(self.data.whitelist, sp.record(fa2=fa2, user=user)), message="ONLY_WHITELISTED")
        return fa2_props

    def removeFromFA2Whitelist(self, fa2, user):
        """Removes an address from the whitelist."""
        sp.set_type(fa2, sp.TAddress)
        sp.set_type(user, sp.TAddress)
        # NOTE: probably ok to skip the check and always remove from whitelist.
        #fa2_props = self.getPermittedFA2Props(fa2)
        #with sp.if_(fa2_props.whitelist_enabled):
        self.whitelist_map.remove(self.data.whitelist, sp.record(fa2=fa2, user=user))


    #
    # Admin only entrypoints
    #
    @sp.entry_point(lazify=True)
    def manage_whitelist(self, params):
        """Manage the permitted contracts and whitelist."""
        sp.set_type(params, sp.TList(sp.TVariant(
            # for managing permitted fa2s
            add_permitted = PermittedFA2Params.get_add_type(),
            remove_permitted = PermittedFA2Params.get_remove_type(),
            # for managing the whitelist
            whitelist_add=sp.TList(t_whitelist_key),
            whitelist_remove=sp.TList(t_whitelist_key)
        ).layout(("add_permitted", ("remove_permitted", ("whitelist_add", "whitelist_remove"))))))

        self.onlyAdministrator()
        
        with sp.for_("update", params) as update:
            with update.match_cases() as arg:
                with arg.match("add_permitted") as upd:
                    self.permitted_fa2_map.add(self.data.permitted_fa2, upd.fa2, upd.props)

                with arg.match("remove_permitted") as upd:
                    self.permitted_fa2_map.remove(self.data.permitted_fa2, upd)

                with arg.match("whitelist_add") as upd:
                    with sp.for_("key", upd) as key:
                        self.whitelist_map.add(self.data.whitelist, key)

                with arg.match("whitelist_remove") as upd:
                    with sp.for_("key", upd) as key:
                        self.whitelist_map.remove(self.data.whitelist, key)


    #
    # Views
    #
    @sp.onchain_view(pure=True)
    def get_fa2_permitted(self, fa2):
        """Returns permitted fa2 props."""
        sp.set_type(fa2, sp.TAddress)
        sp.result(self.permitted_fa2_map.get(self.data.permitted_fa2, fa2))

    @sp.onchain_view(pure=True)
    def is_whitelisted(self, key):
        """Returns true if an address is whitelisted."""
        sp.set_type(key, t_whitelist_key)
        sp.result(self.whitelist_map.contains(self.data.whitelist, key))
