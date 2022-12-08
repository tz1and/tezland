import smartpy as sp

from tezosbuilders_contracts_smartpy.mixins.Administrable import Administrable


# TODO: add tests!


t_manage_blacklist = sp.TList(sp.TVariant(
    add = sp.TSet(sp.TAddress),
    remove = sp.TSet(sp.TAddress)
).layout(("add", "remove")))

t_blacklist_param = sp.TSet(sp.TAddress)

t_blacklist_result = sp.TSet(sp.TAddress)


#
# Blacklist contract.
class TL_Blacklist(
    Administrable,
    sp.Contract):
    def __init__(self, administrator, metadata, exception_optimization_level="default-line"):
        sp.Contract.__init__(self)

        self.add_flag("exceptions", exception_optimization_level)
        #self.add_flag("erase-comments")

        self.init_storage(
            blacklist = sp.big_map(tkey=sp.TAddress, tvalue=sp.TUnit)
        )

        self.available_settings = []

        Administrable.__init__(self, administrator = administrator, include_views = False)

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
    # Admin only entry points
    #
    @sp.entry_point(lazify = False)
    def manage_blacklist(self, params):
        """Admin can add/remove addresses."""
        sp.set_type(params, t_manage_blacklist)

        #self.onlyUnpaused()
        self.onlyAdministrator()

        with sp.for_("task", params) as task:
            with task.match_cases() as arg:
                with arg.match("add") as add:
                    with sp.for_("add_element", add.elements()) as add_element:
                        self.data.blacklist[add_element] = sp.unit

                with arg.match("remove") as remove:
                    with sp.for_("remove_element", remove.elements()) as remove_element:
                        del self.data.blacklist[remove_element]


#    #
#    # Views
#    #
#    @sp.onchain_view(pure=True)
#    def is_not_blacklisted(self, address_set):
#        """Returns set of addresses that are NOT blacklisted.
#        
#        Existance in set = not blacklisted."""
#        sp.set_type(address_set, t_blacklist_param)
#
#        with sp.set_result_type(t_blacklist_result):
#            result_set = sp.local("result_set", sp.set([]), t_blacklist_result)
#            with sp.for_("address", address_set.elements()) as address:
#                with sp.if_(~self.data.blacklist.contains(address)):
#                    result_set.value.add(address)
#            sp.result(result_set.value)


    @sp.onchain_view(pure=True)
    def check_blacklisted(self, address_set):
        """Fails with ADDRESS_BLACKLISTED if any of the contracts aren't.
        Otherwise just returns unit."""
        sp.set_type(address_set, t_blacklist_param)

        with sp.for_("address", address_set.elements()) as address:
            with sp.if_(self.data.blacklist.contains(address)):
                sp.failwith("ADDRESS_BLACKLISTED")
        sp.result(sp.unit)