import smartpy as sp

admin_mixin = sp.io.import_script_from_url("file:contracts/Administrable.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")


# TODO: store information about a contracts royalties?
# TODO: convert tz1and royalties to the more common decimals and shares format? (see fa2 metadata)
# TODO: add support for merkle tree to check for supported tokens? object.com, etc...
# TODO: figure out if entrypoints should be lazy!!!!


#
# TokenRegistry contract.
# NOTE: should be pausable for code updates.
class TL_TokenRegistry(
    admin_mixin.Administrable,
    sp.Contract):
    def __init__(self, administrator, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")

        administrator = sp.set_type_expr(administrator, sp.TAddress)
        
        self.address_set = utils.Address_set()
        self.init_storage(
            metadata = metadata,
            registered = self.address_set.make(), # registered fa2s
            permitted = self.address_set.make(), # accounts permitted to add to registry
            )
        admin_mixin.Administrable.__init__(self, administrator = administrator)
        self.generate_contract_metadata()

    def generate_contract_metadata(self):
        """Generate a metadata json file with all the contract's offchain views
        and standard TZIP-12 and TZIP-016 key/values."""
        metadata_base = {
            "name": 'tz1and TokenRegistry',
            "description": 'tz1and token registry',
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

    def onlyAdministratorOrPermitted(self):
        sp.verify(self.isAdministrator(sp.sender) | self.data.permitted.contains(sp.sender), 'NOT_PERMITTED')

    #
    # Admin-only entry points
    #
    @sp.entry_point(lazify = True)
    def manage_permissions(self, params):
        """Allows the administrator to add accounts permitted
        to register FA2s"""
        sp.set_type(params, sp.TList(sp.TVariant(
            add_permission = sp.TAddress,
            remove_permission = sp.TAddress
        )))

        self.onlyAdministrator()

        with sp.for_("update", params) as update:
            with update.match_cases() as arg:
                with arg.match("add_permission") as address:
                    self.address_set.add(self.data.permitted, address)

                with arg.match("remove_permission") as address:
                    self.address_set.remove(self.data.permitted, address)

    @sp.entry_point(lazify = True)
    def unregister_fa2(self, params):
        """Allow administrator to unregister FA2s"""
        sp.set_type(params, sp.TList(sp.TAddress))

        self.onlyAdministrator()

        with sp.for_("contract", params) as contract:
            self.address_set.remove(self.data.registered, contract)

    #
    # Admin and permitted entry points
    #
    @sp.entry_point(lazify = True)
    def register_fa2(self, params):
        """Allow permitted accounts to register FA2s"""
        sp.set_type(params, sp.TList(sp.TAddress))

        # administrator OR permitted
        self.onlyAdministratorOrPermitted()

        with sp.for_("contract", params) as contract:
            self.address_set.add(self.data.registered, contract)

    #
    # Views
    #
    @sp.onchain_view(pure=True)
    def is_registered(self, contract):
        # TODO: figure out if this should throw or return false...
        """Returns true if contract is registered,
        fails with TOKEN_NOT_REGISTERED otherwise"""
        sp.set_type(contract, sp.TAddress)
        with sp.set_result_type(sp.TBool):
            with sp.if_(self.address_set.contains(self.data.registered, contract)):
                sp.result(True)
            with sp.else_():
                sp.failwith("TOKEN_NOT_REGISTERED")
