import smartpy as sp

admin_contract = sp.io.import_script_from_url("file:contracts/Administrable.py")

# TODO: update_ep variant layout

class Upgradeable(admin_contract.Administrable):
    def __init__(self, administrator, entrypoints: list[str]):
        self.upgradeable_entrypoints = entrypoints
        admin_contract.Administrable.__init__(self, administrator = administrator)

    @sp.entry_point
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
