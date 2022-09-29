import smartpy as sp

contract_metadata_mixin = sp.io.import_script_from_url("file:contracts/ContractMetadata.py")
#basic_permissions_mixin = sp.io.import_script_from_url("file:contracts/BasicPermissions.py")
#upgradeable_mixin = sp.io.import_script_from_url("file:contracts/Upgradeable.py")
utils = sp.io.import_script_from_url("file:contracts/Utils.py")


# TODO: store information about a contracts royalties?
# TODO: convert tz1and royalties to the more common decimals and shares format? (see fa2 metadata)
# TODO: add support for merkle tree to check for supported tokens? object.com, etc...
# TODO: can drastically optimise the size by not having the admin/contract metadata mixins. Maybe useful to optimise.


#
# TokenRegistry contract.
# NOTE: should be pausable for code updates.
class TL_TokenRegistry(
    contract_metadata_mixin.ContractMetadata,
    #basic_permissions_mixin.BasicPermissions,
    #upgradeable_mixin.Upgradeable,
    sp.Contract):
    def __init__(self, administrator, minter, metadata, exception_optimization_level="default-line"):
        self.add_flag("exceptions", exception_optimization_level)
        self.add_flag("erase-comments")

        administrator = sp.set_type_expr(administrator, sp.TAddress)
        
        #self.address_set = utils.Address_set()
        self.init_storage(
            minter = minter,
            #registered = self.address_set.make() # registered fa2s
        )
        contract_metadata_mixin.ContractMetadata.__init__(self, administrator = administrator, metadata = metadata)
        #basic_permissions_mixin.BasicPermissions.__init__(self, administrator = administrator)
        #upgradeable_mixin.Upgradeable.__init__(self, administrator = administrator)
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

    #
    # Inline helpers
    #
    def isTokenTz1andCollection(self, fa2):
        return sp.view("is_collection", self.data.minter,
            sp.set_type_expr(fa2, sp.TAddress),
            t = sp.TBool).open_some()

    #
    # Admin-only entry points
    #
    """@sp.entry_point(lazify = True)
    def unregister_fa2(self, params):
        ""Allow administrator to unregister FA2s""
        sp.set_type(params, sp.TList(sp.TAddress))

        self.onlyAdministrator()

        with sp.for_("contract", params) as contract:
            self.address_set.remove(self.data.registered, contract)

    #
    # Admin and permitted entry points
    #
    @sp.entry_point(lazify = True)
    def register_fa2(self, params):
        ""Allow permitted accounts to register FA2s""
        sp.set_type(params, sp.TList(sp.TAddress))

        # administrator OR permitted
        self.onlyAdministratorOrPermitted()

        with sp.for_("contract", params) as contract:
            self.address_set.add(self.data.registered, contract)"""

    #
    # Views
    #
    @sp.onchain_view(pure=True)
    def is_registered(self, contract):
        # TODO: should we store royalty-type information with registered tokens?
        """Returns true if contract is registered, false otherwise."""
        sp.set_type(contract, sp.TAddress)
        with sp.set_result_type(sp.TBool):
            sp.result(self.isTokenTz1andCollection(contract))
