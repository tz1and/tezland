import smartpy as sp

admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")
#pause_mixin = sp.io.import_script_from_url("file:contracts/Pausable.py")
upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
contract_metadata_mixin = sp.io.import_script_from_url("file:contracts/ContractMetadata.py")
basic_permissions_mixin = sp.io.import_script_from_url("file:contracts/BasicPermissions.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")


# TODO: t_royalties_signed: decide if data should be packed or not.
# TODO: should we use sets in eps supposed to be called from other contracts?

#
# Trusted Royalties - signed offchain.
#

t_public_key_item = sp.TRecord(
    owner = sp.TAddress,
    key = sp.TKey
).layout(("owner", "key"))

t_manage_public_keys = sp.TList(sp.TVariant(
    add = sp.TMap(sp.TString, sp.TKey),
    remove = sp.TSet(sp.TString)
).layout(("add", "remove")))

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
    # TODO: prob want to define royalties here directly.
    token_royalties = FA2.t_royalties_interop
).layout(("token_key", "token_royalties"))

t_remove_royalties_params = sp.TMap(sp.TAddress, sp.TSet(sp.TOption(sp.TNat)))

t_add_royalties_params = sp.TMap(
    sp.TString, # private key id
    sp.TList(sp.TRecord(
        signature = sp.TSignature,
        offchain_royalties = t_royalties_offchain
    ).layout(("signature", "offchain_royalties"))))


def sign_royalties(royalties, private_key):
    royalties = sp.set_type_expr(royalties, t_royalties_offchain)
    # Gives: Type format error atom secret_key
    #private_key = sp.set_type_expr(private_key, sp.TSecretKey)

    packed_royalties = sp.pack(royalties)

    signature = sp.make_signature(
        private_key,
        packed_royalties,
        message_format = 'Raw')

    return signature


#
# Token registry contract.
class TL_LegacyRoyalties(
    admin_mixin.Administrable,
    contract_metadata_mixin.ContractMetadata,
    basic_permissions_mixin.BasicPermissions,
    #pause_mixin.Pausable,
    upgradeable_mixin.Upgradeable,
    sp.Contract):
    def __init__(self, administrator, metadata, exception_optimization_level="default-line"):

        self.add_flag("exceptions", exception_optimization_level)
        #self.add_flag("erase-comments")

        self.init_storage(
            public_keys = sp.big_map(tkey=sp.TString, tvalue=t_public_key_item),
            royalties = sp.big_map(tkey=t_token_key_opt, tvalue=FA2.t_royalties_interop)
        )

        self.available_settings = []

        admin_mixin.Administrable.__init__(self, administrator = administrator, include_views = False)
        #pause_mixin.Pausable.__init__(self, meta_settings = True, include_views = False)
        contract_metadata_mixin.ContractMetadata.__init__(self, metadata = metadata, meta_settings = True)
        basic_permissions_mixin.BasicPermissions.__init__(self)
        upgradeable_mixin.Upgradeable.__init__(self)

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


    @sp.entry_point(lazify = False)
    def manage_public_keys(self, params):
        """Admin or permitted can add/remove public keys"""
        sp.set_type(params, t_manage_public_keys)

        #self.onlyUnpaused()
        self.onlyAdministratorOrPermitted()

        with sp.for_("upd", params) as upd:
            with upd.match_cases() as arg:
                with arg.match("add") as add:
                    with sp.for_("add_item", add.items()) as add_item:
                        self.data.public_keys[add_item.key] = sp.record(owner=sp.sender, key=add_item.value)

                with arg.match("remove") as remove:
                    with sp.for_("id", remove.elements()) as id:
                        # check owner or admin
                        with sp.if_(self.isAdministrator(sp.sender) | (self.data.public_keys.get(id, message="UNKNOWN_KEY").owner == sp.sender)):
                            del self.data.public_keys[id]
                        with sp.else_():
                            sp.failwith("NOT_KEY_OWNER_OR_ADMIN")


    @sp.entry_point(lazify = False)
    def remove_royalties(self, params):
        """Admin or permitted can remove royalties"""
        sp.set_type(params, t_remove_royalties_params)

        #self.onlyUnpaused()
        self.onlyAdministratorOrPermitted()

        with sp.for_("fa2_item", params.items()) as fa2_item:
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
    def get_token_royalties(self, token_key):
        """Returns royalties, if known.

        First checks unique royalties, then global (id some or none).
        
        Fails if unknown."""
        sp.set_type(token_key, t_token_key)
        sp.result(utils.openSomeOrDefault(
            self.data.royalties.get_opt(sp.record(fa2=token_key.fa2, id=sp.some(token_key.id))),
            self.data.royalties.get(sp.record(fa2=token_key.fa2, id=sp.none), message="UNKNOWN_ROYALTIES")))


    @sp.onchain_view(pure=True)
    def get_token_royalties_batch(self, token_keys):
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