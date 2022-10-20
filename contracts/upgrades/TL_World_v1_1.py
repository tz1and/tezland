import smartpy as sp

world_contract = sp.io.import_script_from_url("file:contracts/TL_World.py")
worldv2_contract = sp.io.import_script_from_url("file:contracts/TL_World_v2.py")


class TL_World_v1_1(world_contract.TL_World):
    def __init__(self, administrator, items_contract, places_contract, dao_contract, metadata,
        name="tz1and World (deprecated)", description="tz1and Virtual World", version="1.1.0"):

        world_contract.TL_World.__init__(self, administrator,
            items_contract, places_contract, dao_contract, metadata,
            name, description, version)

    def send_migration(self, migration_to_contract, migration_map, place_props, lot_id):
        sp.set_type(migration_to_contract, sp.TAddress)
        sp.set_type(migration_map, worldv2_contract.migrationItemMapType)
        sp.set_type(place_props, worldv2_contract.placePropsType)
        sp.set_type(lot_id, sp.TNat)
        migration_handle = sp.contract(
            worldv2_contract.migrationType,
            migration_to_contract,
            entry_point='migration').open_some()
        sp.transfer(sp.record(
            place_key = sp.record(place_contract = self.data.places_contract, lot_id = lot_id),
            # For migration from v1 we basically need the same data as a chunk but with a list as the leaf.
            migrate_item_map = migration_map,
            migrate_place_props = place_props,
            extension = sp.none
        ), sp.mutez(0), migration_handle)

    @sp.entry_point(lazify = True)
    def set_item_data(self, params):
        """This upgraded entrypoint allows the admin to migrate
        all items in a place to the v2 world."""
        sp.set_type(params, sp.TRecord(
            lot_id = sp.TNat,
            owner = sp.TOption(sp.TAddress),
            update_map = sp.TMap(sp.TAddress, sp.TList(world_contract.updateItemListType)),
            extension = world_contract.extensionArgType
        ).layout(("lot_id", ("owner", ("update_map", "extension")))))

        self.onlyAdministrator()

        migration_map = sp.local("migration_map", {}, worldv2_contract.migrationItemMapType)

        this_place = self.place_store_map.get(self.data.places, params.lot_id)

        # TODO: do nothing or fail for empty places.
        # depends if I want to detect them advance or call any place anyway and waste a little gas...

        # Fill migration map with items from storage
        with sp.for_("issuer", this_place.stored_items.keys()) as issuer:
            # Get item store - must exist.
            item_store = self.item_store_map.get(this_place.stored_items, issuer)

            migration_map.value[issuer] = sp.map({})
            migration_map.value[issuer][self.data.items_contract] = sp.list([])
            current_list = migration_map.value[issuer][self.data.items_contract]

            with sp.for_("update", item_store.values()) as item_variant:
                with item_variant.match_cases() as arg:
                    with arg.match("item") as item:
                        # TODO: add adhoc operators
                        current_list.push(sp.variant("item", sp.record(
                            token_amount = item.item_amount,
                            token_id = item.token_id,
                            mutez_per_token = item.mutez_per_item,
                            item_data = item.item_data)))
                    with arg.match("other"):
                        sp.failwith("OTHER_TYPE_ITEMS_NOT_SUPPORTED")
                    with arg.match("ext") as ext:
                        current_list.push(sp.variant("ext", ext))

        # TODO: update adhoc operators.

        # Send migration to world v2.
        # TODO: somehow get the world v2 contract in here. maybe a constructor arg?
        # TODO: only send if there actually are items to transfer, I guess.
        self.send_migration(self.data.places_contract, migration_map.value, self.data.places[params.lot_id].place_props, params.lot_id)

        # Finally, delete the place from storage.
        del self.data.places[params.lot_id]

    @sp.entry_point(lazify = True)
    def get_item(self, params):
        """This upgraded entrypoint allows the admin to update
        the v1 world's metadata."""
        sp.set_type(params, sp.TRecord(
            lot_id = sp.TNat,
            item_id = sp.TNat,
            issuer = sp.TAddress,
            extension = world_contract.extensionArgType
        ).layout(("lot_id", ("item_id", ("issuer", "extension")))))

        self.onlyAdministrator()

        # Get ext map.
        ext_map = params.extension.open_some(message = "NO_EXT_PARAMS")

        # Make sure metadata_uri exists and update contract metadata.
        self.data.metadata[""] = ext_map.get("metadata_uri", message = "NO_METADATA_URI")