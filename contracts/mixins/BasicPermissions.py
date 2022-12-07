import smartpy as sp


# Mixins required: Administrable
class BasicPermissions:
    """(Mixin) Provide basic permission checks.

    Requires the `Administrable` mixin.
    """
    def __init__(self, default_permitted_accounts = sp.big_map({}), lazy_ep = False):
        default_permitted_accounts = sp.set_type_expr(default_permitted_accounts, sp.TBigMap(sp.TAddress, sp.TUnit))

        self.update_initial_storage(
            permitted_accounts = default_permitted_accounts #sp.big_map(default_permitted_accounts, tkey=sp.TAddress, tvalue=sp.TUnit)
        )

        # Admin-only entry point
        def manage_permissions(self, params):
            """Allows the administrator to add accounts permitted
            to register FA2s"""
            sp.set_type(params, sp.TList(sp.TVariant(
                add_permissions = sp.TSet(sp.TAddress),
                remove_permissions = sp.TSet(sp.TAddress)
            ).layout(("add_permissions", "remove_permissions"))))

            self.onlyAdministrator()

            with sp.for_("update", params) as update:
                with update.match_cases() as arg:
                    with arg.match("add_permissions") as addresses:
                        with sp.for_("address", addresses.elements()) as address:
                            self.data.permitted_accounts[address] = sp.unit

                    with arg.match("remove_permissions") as addresses:
                        with sp.for_("address", addresses.elements()) as address:
                            del self.data.permitted_accounts[address]

        self.manage_permissions = sp.entry_point(manage_permissions, lazify=lazy_ep)

    # Inline helpers
    def onlyAdministratorOrPermitted(self):
        sp.verify(self.isAdministrator(sp.sender) | self.data.permitted_accounts.contains(sp.sender), 'NOT_PERMITTED')

    def onlyPermitted(self):
        sp.verify(self.data.permitted_accounts.contains(sp.sender), 'NOT_PERMITTED')
