import smartpy as sp

world_contract = sp.io.import_script_from_url("file:contracts/TL_World.py")


class TL_World_v1_1(world_contract.TL_World):
    def __init__(self, administrator, items_contract, places_contract, dao_contract, metadata,
        name="tz1and World (deprecated)", description="tz1and Virtual World", version="1.1.0"):

        world_contract.TL_World.__init__(self, administrator,
            items_contract, places_contract, dao_contract, metadata,
            name, description, version)

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

        sp.failwith("WHOOPS")

        # Get the place - must exist.
        """this_place = self.place_store_map.get(self.data.places, params.lot_id)

        # Caller must have ModifyAll or ModifyOwn permissions.
        permissions = self.getPermissionsInline(params.lot_id, params.owner, sp.sender)
        hasModifyAll = permissions & permissionModifyAll == permissionModifyAll

        # If ModifyAll permission is not given, make sure update map only contains sender items.
        with sp.if_(~hasModifyAll):
            with sp.for_("remove_key", params.update_map.keys()) as remove_key:
                sp.verify(remove_key == sp.sender, message = self.error_message.no_permission())

        # Update items.
        with sp.for_("issuer", params.update_map.keys()) as issuer:
            update_list = params.update_map[issuer]
            # Get item store - must exist.
            item_store = self.item_store_map.get(this_place.stored_items, issuer)
            
            with sp.for_("update", update_list) as update:
                self.validateItemData(update.item_data)

                with item_store[update.item_id].match_cases() as arg:
                    with arg.match("item") as immutable:
                        # sigh - variants are not mutable
                        item_var = sp.compute(immutable)
                        item_var.item_data = update.item_data
                        item_store[update.item_id] = sp.variant("item", item_var)
                    with arg.match("other") as immutable:
                        # sigh - variants are not mutable
                        other_var = sp.compute(immutable)
                        other_var.item_data = update.item_data
                        item_store[update.item_id] = sp.variant("other", other_var)
                    with arg.match("ext"):
                        item_store[update.item_id] = sp.variant("ext", update.item_data)

        # Increment interaction counter, next_id does not change.
        this_place.interaction_counter += 1"""

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