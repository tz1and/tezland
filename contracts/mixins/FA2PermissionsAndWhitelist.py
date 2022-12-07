import smartpy as sp


permittedFA2MapValueType = sp.TRecord(
    whitelist_enabled = sp.TBool, # If the token is whitelisted.
    whitelist_admin = sp.TAddress, # The account that is the whitelist admin
).layout(("whitelist_enabled", "whitelist_admin"))

#
# Lazy map of whitelist entries.
t_whitelist_key = sp.TRecord(
    fa2 = sp.TAddress,
    user = sp.TAddress
).layout(("fa2", "user"))

#
# Parameters for permitted fa2 management ep.
class PermittedFA2Params:
    @classmethod
    def get_add_type(cls):
        return sp.TMap(sp.TAddress, permittedFA2MapValueType)

    @classmethod
    def get_remove_type(cls):
        return sp.TSet(sp.TAddress)


# NOTE:
# When a permitted FA2 is removed, that will break swaps, auctions, etc.
# I think this is desired. But make sure to give a good error message.


# Mixins required: Administrable
class FA2PermissionsAndWhitelist:
    def __init__(self, default_permitted = sp.big_map({})):
        default_permitted = sp.set_type_expr(default_permitted, sp.TBigMap(sp.TAddress, permittedFA2MapValueType))

        self.update_initial_storage(
            permitted_fa2 = default_permitted,
            whitelist = sp.big_map(tkey=t_whitelist_key, tvalue=sp.TUnit)
        )


    def getPermittedFA2Props(self, fa2):
        """Returns permitted props or fails if not permitted"""
        sp.set_type(fa2, sp.TAddress)
        return sp.compute(self.data.permitted_fa2.get(fa2, message="TOKEN_NOT_PERMITTED"))


    def isWhitelistedForFA2(self, fa2, user):
        """If an address is whitelisted."""
        sp.set_type(fa2, sp.TAddress)
        sp.set_type(user, sp.TAddress)
        return self.data.whitelist.contains(sp.record(fa2=fa2, user=user))


    def onlyWhitelistedForFA2(self, fa2, user):
        """Fails if whitelist enabled address is not whitelisted.
        and returns fa2 props."""
        sp.set_type(fa2, sp.TAddress)
        sp.set_type(user, sp.TAddress)
        fa2_props = sp.compute(self.getPermittedFA2Props(fa2))
        with sp.if_(fa2_props.whitelist_enabled):
            sp.verify(self.data.whitelist.contains(sp.record(fa2=fa2, user=user)), message="ONLY_WHITELISTED")
        return fa2_props


    def removeFromFA2Whitelist(self, fa2, user):
        """Removes an address from the whitelist."""
        sp.set_type(fa2, sp.TAddress)
        sp.set_type(user, sp.TAddress)
        # NOTE: probably ok to skip the check and always remove from whitelist.
        #fa2_props = self.getPermittedFA2Props(fa2)
        #with sp.if_(fa2_props.whitelist_enabled):
        del self.data.whitelist[sp.record(fa2=fa2, user=user)]


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
                with arg.match("add_permitted") as add_permitted:
                    with sp.for_("add_permitted_item", add_permitted.items()) as add_permitted_item:
                        self.data.permitted_fa2[add_permitted_item.key] = add_permitted_item.value

                with arg.match("remove_permitted") as remove_permitted:
                    with sp.for_("remove_permitted_item", remove_permitted.elements()) as remove_permitted_element:
                        del self.data.permitted_fa2[remove_permitted_element]

                with arg.match("whitelist_add") as upd:
                    with sp.for_("key", upd) as key:
                        self.data.whitelist[key] = sp.unit

                with arg.match("whitelist_remove") as upd:
                    with sp.for_("key", upd) as key:
                        del self.data.whitelist[key]


    #
    # Views
    #
    @sp.onchain_view(pure=True)
    def get_fa2_permitted(self, fa2):
        """Returns permitted fa2 props."""
        sp.set_type(fa2, sp.TAddress)
        sp.result(self.data.permitted_fa2.get(fa2, message="TOKEN_NOT_PERMITTED"))


    @sp.onchain_view(pure=True)
    def is_whitelisted(self, key):
        """Returns true if an address is whitelisted."""
        sp.set_type(key, t_whitelist_key)
        sp.result(self.data.whitelist.contains(key))
