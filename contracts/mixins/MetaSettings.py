import smartpy as sp


# Required mixins: Administrable
class MetaSettings:
    """IMPORTANT: Must be initialised after all eps using meta settings but
    before Upgradeable, in order to work correctly."""
    def __init__(self):
        if not hasattr(self, 'available_settings'):
            raise Exception("ERROR: MetaSettings.available_settings not set!")

        if self.available_settings:
            def update_settings(self, params):
                """Allows the administrator to update various settings.
                
                Parameters are metaprogrammed with self.available_settings"""
                sp.set_type(params, sp.TList(sp.TVariant(
                    **{setting[0]: setting[1] for setting in self.available_settings})))

                self.onlyAdministrator()

                with sp.for_("update", params) as update:
                    with update.match_cases() as arg:
                        for setting in self.available_settings:
                            with arg.match(setting[0]) as value:
                                if setting[2] != None:
                                    setting[2](value)
                                setattr(self.data, setting[0], value)

            self.update_settings = sp.entry_point(update_settings, lazify=True)
        else: print("\x1b[33;20mWARNING: MetaSettings used but available_settings is empty!\x1b[0m")
