# The World contract.
#
# Each lot belongs to a Place (an FA2 token that is the "land").
# Items (another type of token) can be stored on your Place, either to swap
# or just to build something nice.

import smartpy as sp

world_types = sp.io.import_script_from_url("file:contracts/TL_World.py") 
pause_mixin = sp.io.import_script_from_url("file:contracts/Pausable.py")
fees_mixin = sp.io.import_script_from_url("file:contracts/Fees.py")
mod_mixin = sp.io.import_script_from_url("file:contracts/Moderation.py")
permitted_fa2 = sp.io.import_script_from_url("file:contracts/PermittedFA2.py")
upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
contract_metadata_mixin = sp.io.import_script_from_url("file:contracts/ContractMetadata.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")

class Error_message:
    def __init__(self):
        #self.prefix = "WORLD_"
        self.prefix = ""
    def make(self, s): return (self.prefix + s)
    def no_permission(self):        return self.make("NO_PERMISSION")
    def not_owner(self):            return self.make("NOT_OWNER")
    def fee_error(self):            return self.make("FEE_ERROR")
    def parameter_error(self):      return self.make("PARAM_ERROR")
    def data_length(self):          return self.make("DATA_LEN")
    def item_limit(self):           return self.make("ITEM_LIMIT")
    def not_for_sale(self):         return self.make("NOT_FOR_SALE")
    def wrong_amount(self):         return self.make("WRONG_AMOUNT")
    def wrong_item_type(self):      return self.make("WRONG_ITEM_TYPE")

#
# District storage
districtPropsType = sp.TMap(sp.TBytes, sp.TBytes)
# only set name by default.
def defaultDistrictProps(district_number): return sp.map({sp.bytes("0x00"): sp.utils.bytes_of_string(f'District #{district_number}')}, tkey=sp.TBytes, tvalue=sp.TBytes)


t_role = sp.TVariant(
    moderator = sp.TUnit,
    treasurer = sp.TUnit,
    builder = sp.TUnit,
    member = sp.TUnit,
    none = sp.TUnit,
)

t_elect_list = sp.TList(sp.TRecord(
    user = sp.TAddress,
    role = t_role # can be a promotion or a demotion
))

t_transfer_mutez = sp.TList(sp.TRecord(
    amount = sp.TMutez,
    to_ = sp.TAddress
))

t_transfer_tokens = sp.TMap(
    # token contract
    sp.TAddress,
    # map from destination address to amount and id
    # TODO: record that also holds token type: FA1/FA2?
    sp.TMap(
        # to
        sp.TAddress,
        # amount, id
        sp.TRecord(
            amount = sp.TNat,
            token_id = sp.TNat
        )
    )
)

t_burn_tokens = sp.TMap(
    # token contract
    sp.TAddress,
    # list of to amounts and ids
    # TODO: record that also holds token type: FA1/FA2?
    sp.TList(
        # amount, id
        sp.TRecord(
            amount = sp.TNat,
            token_id = sp.TNat
        )
    )
)

t_collect_items = sp.TList(sp.TRecord(
    lot_id = sp.TNat,
    item_id = sp.TNat,
    issuer = sp.TAddress,
    extension = world_types.extensionArgType,
    amount = sp.TMutez
).layout(("lot_id", ("item_id", ("issuer", ("extension", "amount"))))))

t_swap_items = sp.TRecord(
    lot_id = sp.TNat,
    owner = sp.TOption(sp.TAddress),
    item_list = sp.TList(world_types.placeItemListType),
    extension = world_types.extensionArgType
).layout(("lot_id", ("owner", ("item_list", "extension"))))

t_proposal_kind = sp.TVariant(
    member_election = t_elect_list,
    transfer_mutez = t_transfer_mutez,
    transfer_tokens = t_transfer_tokens,
    burn_tokens = t_burn_tokens,
    collect_items = t_collect_items,
    swap_items = t_swap_items,
)

t_proposal = sp.TRecord(
    # the type of proposal, also holds type specific parameters.
    kind = t_proposal_kind,
    # the address that created the proposal
    issuer = sp.TAddress,
    # the time it was created
    created = sp.TTimestamp,
    # the quorum required for this proposal, in permille.
    quorum = sp.TNat,
    # the number of positive votes: TODO: maybe just count them?
    positive_votes = sp.TNat
)

t_votes = sp.TMap(sp.TAddress, sp.TBool)

#
# The District mini-DAO contract.
# NOTE: should be pausable for code updates and because other item fa2 tokens are out of our control.
# guardian - can transfer places (as a kind of safety-net), can add/remove members and promote/demote any role
# moderators (multi-sig) - maybe not needed
# treasurers (multi-sig) - can vote to transfer community funds, collect items, place items for sale, transfer/burn tokens (except places)
# builders - can place/remove/edit items in public places, but only what's in the inventory of the community contract and no swaps
# members - ???
#
# make it bottom up, not top down:
# this could work if the required quorum goes up
# adding a new member you only need a few votes, say 20% 
# but to elect a builder you already need +30% percent 
# to elect a treasurer you need 50% 
# and voting someone out... maybe quorum of 30%? 
# everyone should get to vote on elections, not just certain roles
# you need to rise through the ranks 
# you can't just go from member to treasurer
# you have to become a builder first and remain there for a period of time 
# maybe even fixed election periods?
# and an emergency vote of confidence to remove/block someone from acting until resolved
class DistrictDAO(
    pause_mixin.Pausable,
    upgradeable_mixin.Upgradeable,
    contract_metadata_mixin.ContractMetadata,
    sp.Contract):
    def __init__(self, administrator, world_contract, items_contract, places_contract, dao_contract, district_number, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")
        
        self.error_message = Error_message()
        self.permission_param = world_types.Permission_param()
        self.init_storage(
            world_contract = world_contract,
            items_contract = items_contract,
            places_contract = places_contract,
            dao_contract = dao_contract,
            district_props = defaultDistrictProps(district_number),
            members = sp.big_map(tkey = sp.TAddress, tvalue = t_role),
            proposals = sp.big_map(tkey = sp.TNat, tvalue = t_proposal),
            votes = sp.big_map(tkey = sp.TNat, tvalue = t_votes),
            proposal_counter = 0
        )
        contract_metadata_mixin.ContractMetadata.__init__(self, administrator = administrator, metadata = metadata)
        pause_mixin.Pausable.__init__(self, administrator = administrator)
        upgradeable_mixin.Upgradeable.__init__(self, administrator = administrator)
        self.generate_contract_metadata(district_number)

    def generate_contract_metadata(self, district_number):
        """Generate a metadata json file with all the contract's offchain views
        and standard TZIP-12 and TZIP-016 key/values."""
        metadata_base = {
            "name": f'tz1and District #{district_number}',
            "description": 'tz1and District mini-DAO',
            "version": "1.0.0",
            "interfaces": ["TZIP-012", "TZIP-016"],
            "authors": [
                "852Kerfunkle <https://github.com/852Kerfunkle>"
            ],
            "homepage": "https://www.tz1and.com",
            "source": {
                "tools": ["SmartPy"],
                "location": "https://github.com/tz1and",
            },
            "license": { "name": "MIT" }
        }
        offchain_views = []
        for f in dir(self):
            attr = getattr(self, f)
            if isinstance(attr, sp.OnOffchainView):
                # Include onchain views as tip 16 offchain views
                offchain_views.append(attr)
        metadata_base["views"] = offchain_views
        self.init_metadata("metadata_base", metadata_base)

    #
    # Guardian entry points
    #
    # add/remove mod
    # transfer place tokens

    #
    # Moderator entry points
    #
    # proposals:
    # add/remove mod
    # add/remove treasurer
    # set_district_props
    # set_place_props

    @sp.entry_point(lazify = True)
    def set_place_props(self, params):
        t_set_place_props = sp.TRecord(
            lot_id =  sp.TNat,
            owner =  sp.TOption(sp.TAddress),
            props =  world_types.placePropsType,
            extension = world_types.extensionArgType
        ).layout(("lot_id", ("owner", ("props", "extension"))))
        sp.set_type(params, t_set_place_props)

        self.onlyUnpaused()

        c = sp.contract(
            t_set_place_props,
            self.data.world_contract,
            entry_point='set_place_props').open_some()
        sp.transfer(params, sp.mutez(0), c)

    #
    # Treasurer entry points
    #
    # proposals:
    # place items as swaps
    # remove swaps
    # collect items
    # transfer funds
    # transfer FA2 tokens (except places)

    @sp.entry_point(lazify = True)
    def get_item(self, params):
        t_get_item = sp.TRecord(
            lot_id = sp.TNat,
            item_id = sp.TNat,
            issuer = sp.TAddress,
            extension = world_types.extensionArgType
        ).layout(("lot_id", ("item_id", ("issuer", "extension"))))
        sp.set_type(params, t_get_item)

        self.onlyUnpaused()

        c = sp.contract(
            t_get_item,
            self.data.world_contract,
            entry_point='get_item').open_some()
        sp.transfer(params, sp.mutez(0), c)

    # treasurers can place items in the world for swaps (checked in user entry point)

    #
    # User entry points
    #
    # permissions are done based on user/moderator/tresurer roles
    #@sp.entry_point(lazify = True)
    #def set_permissions(self, params):
    #    t_set_permissions = sp.TList(sp.TVariant(
    #        add_permission = self.permission_param.get_add_type(),
    #        remove_permission = self.permission_param.get_remove_type()
    #    ).layout(("add_permission", "remove_permission")))
    #    sp.set_type(params, t_set_permissions)
    #
    #    self.onlyUnpaused()
    #
    #    c = sp.contract(
    #        t_set_permissions,
    #        self.data.world_contract,
    #        entry_point='set_permissions').open_some()
    #    sp.transfer(params, sp.mutez(0), c)


    # All builders can place items.
    # Treasurers can place swaps.
    @sp.entry_point(lazify = True)
    def place_items(self, params):
        t_place_items = sp.TRecord(
            lot_id = sp.TNat,
            owner = sp.TOption(sp.TAddress),
            item_list = sp.TList(world_types.placeItemListType),
            extension = world_types.extensionArgType
        ).layout(("lot_id", ("owner", ("item_list", "extension"))))
        sp.set_type(params, t_place_items)

        self.onlyUnpaused()

        c = sp.contract(
            t_place_items,
            self.data.world_contract,
            entry_point='place_items').open_some()
        sp.transfer(params, sp.mutez(0), c)


    # All builders can update items.
    # Treasurers can update swaps.
    @sp.entry_point(lazify = True)
    def set_item_data(self, params):
        t_set_item_data = sp.TRecord(
            lot_id = sp.TNat,
            owner = sp.TOption(sp.TAddress),
            update_map = sp.TMap(sp.TAddress, sp.TList(world_types.updateItemListType)),
            extension = world_types.extensionArgType
        ).layout(("lot_id", ("owner", ("update_map", "extension"))))
        sp.set_type(params, t_set_item_data)

        self.onlyUnpaused()

        c = sp.contract(
            t_set_item_data,
            self.data.world_contract,
            entry_point='set_item_data').open_some()
        sp.transfer(params, sp.mutez(0), c)


    # All builders can remove items.
    # Treasurers can remove swaps.
    @sp.entry_point(lazify = True)
    def remove_items(self, params):
        t_remove_items = sp.TRecord(
            lot_id = sp.TNat,
            owner = sp.TOption(sp.TAddress),
            remove_map = sp.TMap(sp.TAddress, sp.TList(sp.TNat)),
            extension = world_types.extensionArgType
        ).layout(("lot_id", ("owner", ("remove_map", "extension"))))
        sp.set_type(params, t_remove_items)

        self.onlyUnpaused()

        c = sp.contract(
            t_remove_items,
            self.data.world_contract,
            entry_point='remove_items').open_some()
        sp.transfer(params, sp.mutez(0), c)


    #
    # Member entry points
    #

    @sp.entry_point(lazify = True)
    def create_proposal(self, proposal):
        sp.set_type(proposal, t_proposal_kind)

        # TODO: check is member and can create this kind of proposal

        self.data.proposals[self.data.proposal_counter] = sp.record(
            kind = proposal,
            issuer = sp.sender,
            created = sp.now,
            quorum = 300, # TODO
            positive_votes = 0
        )

        self.data.proposal_counter += 1
    #
    # Views
    #
    # is_moderator, is_treasuerer, is_builder, is_member
