import smartpy as sp

manager_contract = sp.io.import_script_from_url("file:contracts/Manageable.py")


class Whitelist(manager_contract.Manageable):
    #def __init__(self, manager):
    #    self.init_storage(
    #        managers = sp.set([manager], t = sp.TAddress)
    #        )

    def isWhitelisted(self, address):
        """if an address is whitelisted"""
        return self.address_set.contains(self.data.whitelist, address)

    def onlyWhitelisted(self):
        """fails if whitelist enabled address is not whitelisted """
        sp.if self.data.whitelist_enabled:
            sp.verify(self.address_set.contains(self.data.whitelist, sp.sender), message="ONLY_WHITELISTED")

    def onlyManagerIfWhitelistEnabled(self):
        """fails if whitelist is enabled and sender is not manager"""
        sp.if self.data.whitelist_enabled:
            self.onlyManager()

    def removeFromWhitelist(self, address):
        """removes an address from the whitelist"""
        # NOTE: probably ok to skip the check and always remove from whitelist.
        #sp.if self.data.whitelist_enabled:
        self.address_set.remove(self.data.whitelist, address)

    @sp.entry_point
    def manage_whitelist(self, updates):
        """Manage the whitelist"""
        sp.set_type(updates, sp.TList(sp.TVariant(
            whitelist_add=sp.TList(sp.TAddress),
            whitelist_remove=sp.TList(sp.TAddress),
            whitelist_enabled=sp.TBool)))
        self.onlyManager()
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
