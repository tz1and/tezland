import smartpy as sp


# TODO: update_ep variant layout?

# Mixins required: Administrable
class Upgradeable:
    def __init__(self):
        # get lazy entry points
        self.upgradeable_entrypoints = []
        for f in dir(self):
            attr = getattr(self, f)
            if isinstance(attr, sp.Entrypoint) and attr.message.lazify == True:
                self.upgradeable_entrypoints.append(attr.message.fname)

        # if there are any, add the update ep
        if len(self.upgradeable_entrypoints) > 0:
            #print(f'{self.__class__.__name__}: {self.upgradeable_entrypoints}')
            def update_ep(self, params):
                # Build a variant from upgradeable_entrypoints.
                sp.set_type(params.ep_name, sp.TVariant(
                    **{entrypoint: sp.TUnit for entrypoint in self.upgradeable_entrypoints}))
                self.onlyAdministrator()

                # Build a matcher for upgradeable_entrypoints
                with params.ep_name.match_cases() as arg:
                    for entrypoint in self.upgradeable_entrypoints:
                        with arg.match(entrypoint):
                            sp.set_entry_point(entrypoint, params.new_code)

            self.update_ep = sp.entry_point(update_ep, lazify=False)
