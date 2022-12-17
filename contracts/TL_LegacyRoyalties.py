import smartpy as sp

from contracts import FA2
from tz1and_contracts_smartpy.mixins.Administrable import Administrable
from tz1and_contracts_smartpy.mixins.Upgradeable import Upgradeable
from tz1and_contracts_smartpy.mixins.ContractMetadata import ContractMetadata
from tz1and_contracts_smartpy.mixins.MetaSettings import MetaSettings
from contracts.mixins.BasicPermissions import BasicPermissions

from contracts.utils import EnvUtils, ErrorMessages
from tz1and_contracts_smartpy.utils import Utils


#
# Trusted Royalties - signed offchain.
#

t_public_key_item = sp.TRecord(
    owner = sp.TAddress,
    key = sp.TKey
).layout(("owner", "key"))

t_manage_registry = sp.TList(sp.TVariant(
    add_keys = sp.TMap(sp.TString, sp.TKey),
    remove_keys = sp.TSet(sp.TString),
    remove_royalties = sp.TMap(sp.TAddress, sp.TSet(sp.TOption(sp.TNat)))
).layout(("add_keys", ("remove_keys", "remove_royalties"))))

t_token_key_opt = sp.TRecord(
    fa2 = sp.TAddress,
    # Token ID is optional, for contracts with global royalties (PFPs, etc).
    id = sp.TOption(sp.TNat),
).layout(("fa2", "id"))

t_token_key = sp.TRecord(
    fa2 = sp.TAddress,
    id = sp.TNat,
).layout(("fa2", "id"))

# Offchain royalties type
t_royalties_offchain = sp.TRecord(
    token_key = t_token_key_opt,
    # NOTE: Royalties come from FA2, but maybe we
    # can define the types in their own header.
    token_royalties = FA2.t_royalties_interop
).layout(("token_key", "token_royalties"))

t_add_royalties_params = sp.TMap(
    sp.TString, # private key id
    sp.TList(sp.TRecord(
        signature = sp.TSignature,
        offchain_royalties = t_royalties_offchain
    ).layout(("signature", "offchain_royalties"))))


def signRoyalties(royalties, private_key) -> sp.Expr:
    signature = sp.make_signature(
        private_key,
        sp.pack(sp.set_type_expr(royalties, t_royalties_offchain)),
        message_format = 'Raw')

    return signature


@EnvUtils.view_helper
def getRoyalties(legacy_royalties, token_key) -> sp.Expr:
    return sp.view("get_royalties", sp.set_type_expr(legacy_royalties, sp.TAddress),
        sp.set_type_expr(token_key, t_token_key),
        t = FA2.t_royalties_interop)


#
# Token registry contract.
class TL_LegacyRoyalties(
    Administrable,
    ContractMetadata,
    BasicPermissions,
    #Pausable,
    MetaSettings,
    Upgradeable,
    sp.Contract):
    def __init__(self, administrator, metadata, exception_optimization_level="default-line"):
        sp.Contract.__init__(self)

        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")

        self.init_storage(
            public_keys = sp.big_map(tkey=sp.TString, tvalue=t_public_key_item),
            royalties = sp.big_map(tkey=t_token_key_opt, tvalue=FA2.t_royalties_interop)
        )

        Administrable.__init__(self, administrator = administrator, include_views = False)
        #Pausable.__init__(self, include_views = False)
        ContractMetadata.__init__(self, metadata = metadata)
        BasicPermissions.__init__(self)
        MetaSettings.__init__(self, lazy_ep = False)
        Upgradeable.__init__(self)

        self.generate_contract_metadata()


    def generate_contract_metadata(self):
        """Generate a metadata json file with all the contract's offchain views."""
        metadata_base = {
            "name": 'tz1and LegacyRoyalties',
            "description": 'tz1and legacy royalties',
            "version": "1.0.0",
            "interfaces": ["TZIP-016"],
            "authors": [
                "852Kerfunkle <https://github.com/852Kerfunkle>"
            ],
            "homepage": "https://www.tz1and.com",
            "source": {
                "tools": ["SmartPy"],
                "location": "https://github.com/tz1and",
            },
            "license": { "name": "UNLICENSED" }
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
    # Admin and permitted entry points
    #
    @sp.entry_point(lazify = False)
    def manage_registry(self, params):
        """Admin or permitted can add/remove public keys"""
        sp.set_type(params, t_manage_registry)

        #self.onlyUnpaused()
        self.onlyAdministratorOrPermitted()

        with sp.for_("upd", params) as upd:
            with upd.match_cases() as arg:
                with arg.match("add_keys") as add_keys:
                    with sp.for_("add_item", add_keys.items()) as add_item:
                        self.data.public_keys[add_item.key] = sp.record(owner=sp.sender, key=add_item.value)

                with arg.match("remove_keys") as remove_keys:
                    with sp.for_("id", remove_keys.elements()) as id:
                        # check owner or admin
                        with sp.if_(self.isAdministrator(sp.sender) | (self.data.public_keys.get(id, message="UNKNOWN_KEY").owner == sp.sender)):
                            del self.data.public_keys[id]
                        with sp.else_():
                            sp.failwith("NOT_KEY_OWNER_OR_ADMIN")

                with arg.match("remove_royalties") as remove_royalties:
                    with sp.for_("fa2_item", remove_royalties.items()) as fa2_item:
                        with sp.for_("token_id", fa2_item.value.elements()) as token_id:
                            del self.data.royalties[sp.record(fa2=fa2_item.key, id=token_id)]


    #
    # Public entry points
    #
    @sp.entry_point(lazify = False)
    def add_royalties(self, params):
        """User can add royalties if they are signed with a valid key."""
        sp.set_type(params, t_add_royalties_params)

        #self.onlyUnpaused()

        with sp.for_("key_item", params.items()) as key_item:
            public_key = sp.compute(self.data.public_keys.get(key_item.key, message="INVALID_KEY_ID").key)

            with sp.for_("royalties_item", key_item.value) as royalties_item:
                # Verify the signature matches.
                sp.verify(sp.check_signature(public_key, royalties_item.signature, sp.pack(royalties_item.offchain_royalties)), "INVALID_SIGNATURE")

                # If the signature is valid, add royalties to storage.
                self.data.royalties[royalties_item.offchain_royalties.token_key] = royalties_item.offchain_royalties.token_royalties


    #
    # Views
    #
    @sp.onchain_view(pure=True)
    def get_royalties(self, token_key):
        """Returns royalties, if known.

        First checks unique royalties, then global (id some or none).
        
        Fails if unknown."""
        sp.set_type(token_key, t_token_key)
        sp.result(Utils.openSomeOrDefault(
            self.data.royalties.get_opt(sp.record(fa2=token_key.fa2, id=sp.some(token_key.id))),
            self.data.royalties.get(sp.record(fa2=token_key.fa2, id=sp.none), message=ErrorMessages.unknown_royalties())))


    @sp.onchain_view(pure=True)
    def get_royalties_batch(self, token_keys):
        """Returns batch of royalties, if known.

        First checks unique royalties, then global (id some or none).
        
        Doesn't add royalties to result if unknown."""
        sp.set_type(token_keys, sp.TSet(t_token_key))

        result_map = sp.local("result_map", sp.map({}, tkey=t_token_key, tvalue=FA2.t_royalties_interop))
        with sp.for_("token_key", token_keys.elements()) as token_key:
            with self.data.royalties.get_opt(sp.record(fa2=token_key.fa2, id=sp.some(token_key.id))).match_cases() as arg:
                with arg.match("Some") as some_unique_royalties:
                    result_map.value[token_key] = some_unique_royalties
                with arg.match("None"):
                    with self.data.royalties.get_opt(sp.record(fa2=token_key.fa2, id=sp.none)).match("Some") as some_global_royalties:
                        result_map.value[token_key] = some_global_royalties
        sp.result(result_map.value)


    @sp.onchain_view(pure=True)
    def get_public_keys(self, key_ids):
        """Return one or more private keys.
        
        Doesn't add key to result if unknown."""
        sp.set_type(key_ids, sp.TSet(sp.TString))

        result_map = sp.local("result_map", sp.map({}, tkey=sp.TString, tvalue=sp.TKey))
        with sp.for_("key_id", key_ids.elements()) as key_id:
            with self.data.public_keys.get_opt(key_id).match("Some") as some_key_item:
                result_map.value[key_id] = some_key_item.key
        sp.result(result_map.value)