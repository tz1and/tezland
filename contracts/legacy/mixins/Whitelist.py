import smartpy as sp


# NOTE: deprecated for now.


# Mixins required: Administrable
class Whitelist:
    def __init__(self):
        self.update_initial_storage(
            whitelist_enabled = True, # enabled by default
            whitelist = sp.big_map(tkey=sp.TAddress, tvalue=sp.TUnit), # administrator doesn't need to be whitelisted
        )

    def isWhitelisted(self, address):
        """If an address is whitelisted."""
        address = sp.set_type_expr(address, sp.TAddress)
        return self.data.whitelist.contains(address)

    def onlyWhitelisted(self):
        """Fails if whitelist enabled address is not whitelisted."""
        with sp.if_(self.data.whitelist_enabled):
            sp.verify(self.data.whitelist.contains(sp.sender), message="ONLY_WHITELISTED")

    def onlyAdminIfWhitelistEnabled(self):
        """Fails if whitelist is enabled and sender is not admin."""
        with sp.if_(self.data.whitelist_enabled):
            self.onlyAdministrator()

    def removeFromWhitelist(self, address):
        """Removes an address from the whitelist."""
        address = sp.set_type_expr(address, sp.TAddress)
        # NOTE: probably ok to skip the check and always remove from whitelist.
        #with sp.if_(self.data.whitelist_enabled):
        del self.data.whitelist[address]

    @sp.entry_point
    def manage_whitelist(self, updates):
        """Manage the whitelist."""
        sp.set_type(updates, sp.TList(sp.TVariant(
            whitelist_add=sp.TList(sp.TAddress),
            whitelist_remove=sp.TList(sp.TAddress),
            whitelist_enabled=sp.TBool
        ).layout(("whitelist_add", ("whitelist_remove", "whitelist_enabled")))))
        self.onlyAdministrator()
        with sp.for_("update", updates) as update:
            with update.match_cases() as arg:
                with arg.match("whitelist_add") as upd:
                    with sp.for_("addr", upd) as addr:
                        self.data.whitelist[addr] = sp.unit
                with arg.match("whitelist_remove") as upd:
                    with sp.for_("addr", upd) as addr:
                        del self.data.whitelist[addr]
                with arg.match("whitelist_enabled") as upd:
                    self.data.whitelist_enabled = upd

    @sp.onchain_view(pure=True)
    def is_whitelisted(self, address):
        """Returns true if an address is whitelisted."""
        sp.set_type(address, sp.TAddress)
        sp.result(self.data.whitelist.contains(address))

    @sp.onchain_view(pure=True)
    def is_whitelist_enabled(self):
        """Returns true if whitelist is enabled."""
        sp.result(self.data.whitelist_enabled)
