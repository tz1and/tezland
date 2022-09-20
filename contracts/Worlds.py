import smartpy as sp

World = sp.io.import_script_from_url("file:contracts/TL_World_v2.py")

class tz1andWorld(
    World.TL_World
):
    """tz1and World"""

    def __init__(self, administrator, items_contract, places_contract, token_registry, metadata):
        World.TL_World.__init__(
            self, administrator=administrator, items_contract=items_contract,
            places_contract=places_contract, token_registry=token_registry, metadata=metadata,
            name="tz1and World", description="tz1and Virtual World v2"
        )
