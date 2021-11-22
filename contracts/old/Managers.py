import smartpy as sp

class TL_Managers(sp.Contract):
    #def __init__(self, manager):
    #    self.init_storage(
    #        managers = sp.set([manager], t = sp.TAddress)
    #        )

    def isManager(self, address):
        return self.data.managers.contains(address)

    def onlyManager(self):
        sp.verify(self.isManager(sp.sender), 'onlyManager')

    @sp.entry_point
    def add_manager(self, manager):
        sp.set_type(manager, sp.TAddress)
        self.onlyManager()
        self.data.managers.add(manager)

    @sp.entry_point
    def remove_manager(self, manager):
        sp.set_type(manager, sp.TAddress)
        self.onlyManager()
        self.data.managers.remove(manager)