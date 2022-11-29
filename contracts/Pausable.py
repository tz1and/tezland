import smartpy as sp


# Mixins required: Administrable
class Pausable:
    def __init__(self, paused = False, meta_settings = False):
        self.update_initial_storage(
            paused = paused
        )

        if meta_settings:
            self.available_settings.append(
                ("paused", sp.TBool, None)
            )
            setattr(self, "set_paused", sp.entry_point(None, None))

    def isPaused(self):
        return self.data.paused

    def onlyUnpaused(self):
        sp.verify(self.isPaused() == False, 'ONLY_UNPAUSED')

    def onlyPaused(self):
        sp.verify(self.isPaused() == True, 'ONLY_PAUSED')

    @sp.entry_point
    def set_paused(self, new_paused):
        self.onlyAdministrator()
        self.data.paused = new_paused

    @sp.onchain_view(pure=True)
    def is_paused(self):
        sp.result(self.isPaused())