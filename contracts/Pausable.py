import smartpy as sp

manager_contract = sp.io.import_script_from_url("file:contracts/Manageable.py")

# TODO: add is_paused onchain view?

class Pausable(manager_contract.Manageable):
    #def __init__(self, manager):
    #    self.init_storage(
    #        paused = False
    #        )

    def isPaused(self):
        return self.data.paused

    def onlyUnpaused(self):
        sp.verify(self.isPaused() == False, 'ONLY_UNPAUSED')

    def onlyPaused(self):
        sp.verify(self.isPaused() == True, 'ONLY_PAUSED')

    @sp.entry_point
    def set_paused(self, new_paused):
        self.onlyManager()
        self.data.paused = new_paused
        