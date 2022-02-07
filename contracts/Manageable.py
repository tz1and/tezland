import smartpy as sp

# TODO: figure out if a get_manager onchain view is useful.

class Manageable(sp.Contract):
    #def __init__(self, manager):
    #    self.init_storage(
    #        managers = sp.set([manager], t = sp.TAddress)
    #        )

    def isManager(self, address):
        return self.data.manager == address

    def onlyManager(self):
        sp.verify(self.isManager(sp.sender), 'ONLY_MANAGER')

    @sp.entry_point
    def set_manager(self, new_manager):
        self.onlyManager()
        self.data.manager = new_manager
