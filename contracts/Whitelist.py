import smartpy as sp

admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")


class Whitelist(admin_mixin.Administrable):
    def __init__(self, administrator):
        self.address_set = utils.Address_set()
        self.update_initial_storage(
            whitelist_enabled = True, # enabled by default
            whitelist = self.address_set.make(), # administrator doesn't need to be whitelisted
        )
        admin_mixin.Administrable.__init__(self, administrator = administrator)

    def isWhitelisted(self, address):
        """if an address is whitelisted"""
        address = sp.set_type_expr(address, sp.TAddress)
        return self.address_set.contains(self.data.whitelist, address)

    def onlyWhitelisted(self):
        """fails if whitelist enabled address is not whitelisted """
        sp.if self.data.whitelist_enabled:
            sp.verify(self.address_set.contains(self.data.whitelist, sp.sender), message="ONLY_WHITELISTED")

    def onlyAdminIfWhitelistEnabled(self):
        """fails if whitelist is enabled and sender is not admin"""
        sp.if self.data.whitelist_enabled:
            self.onlyAdministrator()

    def removeFromWhitelist(self, address):
        """removes an address from the whitelist"""
        address = sp.set_type_expr(address, sp.TAddress)
        # NOTE: probably ok to skip the check and always remove from whitelist.
        #sp.if self.data.whitelist_enabled:
        self.address_set.remove(self.data.whitelist, address)

    @sp.entry_point
    def manage_whitelist(self, updates):
        """Manage the whitelist"""
        sp.set_type(updates, sp.TList(sp.TVariant(
            whitelist_add=sp.TList(sp.TAddress),
            whitelist_remove=sp.TList(sp.TAddress),
            whitelist_enabled=sp.TBool
        ).layout(("whitelist_add", ("whitelist_remove", "whitelist_enabled")))))
        self.onlyAdministrator()
        sp.for update in updates:
            with update.match_cases() as arg:
                with arg.match("whitelist_add") as upd:
                    sp.for addr in upd:
                        self.address_set.add(self.data.whitelist, addr)
                with arg.match("whitelist_remove") as upd:
                    sp.for addr in upd:
                        self.address_set.remove(self.data.whitelist, addr)
                with arg.match("whitelist_enabled") as upd:
                    self.data.whitelist_enabled = upd

    @sp.onchain_view(pure=True)
    def is_whitelisted(self, address):
        """returns true if an address is whitelisted"""
        sp.set_type(address, sp.TAddress)
        sp.result(self.address_set.contains(self.data.whitelist, address))

    @sp.onchain_view(pure=True)
    def is_whitelist_enabled(self):
        """returns true if whitelist is enabled"""
        sp.result(self.data.whitelist_enabled)
