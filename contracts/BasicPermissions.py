import smartpy as sp

admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")


class BasicPermissions(admin_mixin.Administrable):
    """(Mixin) Provide basic permission checks.

    Requires the `Administrable` mixin.
    """
    def __init__(self, administrator, default_permitted_accounts = {}):
        self.address_set = utils.Address_set()
        self.update_initial_storage(
            permitted_accounts = self.address_set.make(default_permitted_accounts) # accounts permitted
        )
        admin_mixin.Administrable.__init__(self, administrator = administrator)

    # Inline helpers
    def onlyAdministratorOrPermitted(self):
        sp.verify(self.isAdministrator(sp.sender) | self.data.permitted_accounts.contains(sp.sender), 'NOT_PERMITTED')

    def onlyPermitted(self):
        sp.verify(self.data.permitted_accounts.contains(sp.sender), 'NOT_PERMITTED')

    #
    # Admin-only entry points
    #
    @sp.entry_point()
    def manage_permissions(self, params):
        """Allows the administrator to add accounts permitted
        to register FA2s"""
        sp.set_type(params, sp.TList(sp.TVariant(
            add_permissions = sp.TList(sp.TAddress),
            remove_permissions = sp.TList(sp.TAddress)
        )))

        self.onlyAdministrator()

        with sp.for_("update", params) as update:
            with update.match_cases() as arg:
                with arg.match("add_permissions") as addresses:
                    with sp.for_("address", addresses) as address:
                        self.address_set.add(self.data.permitted_accounts, address)

                with arg.match("remove_permissions") as addresses:
                    with sp.for_("address", addresses) as address:
                        self.address_set.remove(self.data.permitted_accounts, address)