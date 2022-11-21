import smartpy as sp

world_contract = sp.io.import_script_from_url("file:contracts/TL_World.py")
worldv2_contract = sp.io.import_script_from_url("file:contracts/TL_World_v2.py")
FA2_legacy = sp.io.import_script_from_url("file:contracts/legacy/FA2_legacy.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")


class TL_World_v1_1(world_contract.TL_World):
    def __init__(self, administrator, items_contract, places_contract, dao_contract, world_v2_contract, world_v2_place_contract,
        metadata, name="tz1and World (deprecated)", description="tz1and Virtual World", version="1.1.0"):

        self.migrate_to_contract = sp.set_type_expr(world_v2_contract, sp.TAddress)
        self.new_place_tokens_contract = sp.set_type_expr(world_v2_place_contract, sp.TAddress)

        world_contract.TL_World.__init__(self, administrator,
            items_contract, places_contract, dao_contract, metadata,
            name, description, version)

    def send_migration(self, migration_to_contract, migration_map, place_props, lot_id):
        sp.set_type(migration_to_contract, sp.TAddress)
        sp.set_type(migration_map, worldv2_contract.migrationItemMapType)
        sp.set_type(place_props, worldv2_contract.placePropsType)
        sp.set_type(lot_id, sp.TNat)

        # Call v2 migration ep.
        migration_handle = sp.contract(
            worldv2_contract.migrationType,
            migration_to_contract,
            entry_point='migration').open_some()
        sp.transfer(sp.record(
            place_key = sp.record(fa2 = self.new_place_tokens_contract, id = lot_id),
            item_map = migration_map,
            props = place_props,
            ext = sp.none
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

        this_place_opt = self.data.places.get_opt(params.lot_id)

        # Do nothing for empty places.
        with this_place_opt.match("Some") as this_place:
            # Only migrate place has items or the props have been changed.
            with sp.if_((sp.len(this_place.stored_items) > 0) | ~sp.poly_equal_expr(this_place.place_props, worldv2_contract.defaultPlaceProps)):
                # The record of items to migrate to v2.
                migration_map = sp.local("migration_map", {}, worldv2_contract.migrationItemMapType)

                # Our token transfer map.
                # Since it's all the same token, we can have a single map.
                transferMap = utils.FA2TokenTransferMapSingle(self.data.items_contract)

                # Fill migration map with items from storage
                with sp.for_("issuer_item", this_place.stored_items.items()) as issuer_item:
                    # Get item store - must exist.
                    item_store = issuer_item.value

                    migration_map.value[issuer_item.key] = sp.map({self.data.items_contract: sp.list([])})
                    current_list = migration_map.value[issuer_item.key][self.data.items_contract]

                    with sp.for_("item_variant", item_store.values()) as item_variant:
                        with item_variant.match_cases() as arg:
                            with arg.match("item") as item:
                                # Add to transfer map.
                                transferMap.add_token(self.migrate_to_contract, item.token_id, item.item_amount)

                                # Add item to migration list.
                                current_list.push(sp.variant("item", sp.record(
                                    token_id = item.token_id,
                                    amount = item.item_amount,
                                    rate = item.mutez_per_item,
                                    data = item.item_data,
                                    primary = False)))
                            with arg.match("other"):
                                sp.failwith("OTHER_TYPE_ITEMS_NOT_SUPPORTED")
                            with arg.match("ext") as ext:
                                current_list.push(sp.variant("ext", ext))

                # Transfer FA2 tokens
                transferMap.transfer_tokens(sp.self_address)

                # Send migration to world v2.
                # NOTE: still have to send migration even if map is empty, for the props.
                self.send_migration(self.migrate_to_contract, migration_map.value, self.data.places[params.lot_id].place_props, params.lot_id)

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