import smartpy as sp


# Mixins required: Administrable
class ContractMetadata:
    """(Mixin) Provide an interface to update tzip 16 metadata.

    Requires the `Administrable` mixin.
    """
    def __init__(self, metadata, meta_settings = False):
        self.update_initial_storage(
            metadata = sp.set_type_expr(metadata, sp.TBigMap(sp.TString, sp.TBytes))
        )

        if meta_settings:
            self.available_settings.append(
                ("metadata", sp.TBigMap(sp.TString, sp.TBytes), None)
            )
            setattr(self, "set_metadata", sp.entry_point(None, None))

    @sp.entry_point
    def set_metadata(self, metadata):
        """(Admin only) Set the contract metadata."""
        sp.set_type(metadata, sp.TBigMap(sp.TString, sp.TBytes))
        self.onlyAdministrator()
        self.data.metadata = metadata