import pprint
import smartpy as sp

from tezosbuilders_contracts_smartpy.mixins.Administrable import Administrable
from tezosbuilders_contracts_smartpy.mixins.Upgradeable import Upgradeable
from contracts import FA2


# NOTE: all proxied entrypoints must have parameter_type set!

VERBOSE = False


class testFA2(
    Administrable,
    FA2.ChangeMetadata,
    FA2.MintFungible,
    FA2.BurnFungible,
    FA2.Royalties,
    FA2.Fa2Fungible,
):
    """tz1and Items"""

    def __init__(self, metadata, admin, include_views=True):
        FA2.Fa2Fungible.__init__(
            self, metadata=metadata,
            name="tz1and Items", description="tz1and Item FA2 Tokens.",
            #policy=FA2.BlacklistTransfer(admin, FA2.PauseTransfer(FA2.OwnerOrOperatorAdhocTransfer()), True),
            policy=FA2.PauseTransfer(FA2.OwnerOrOperatorAdhocTransfer()),
            has_royalties=True,
            allow_mint_existing=False,
            include_views=include_views
        )
        FA2.MintFungible.__init__(self)
        FA2.Royalties.__init__(self, include_views = include_views)
        Administrable.__init__(self, admin, include_views = False)


class FA2ProxyBase(testFA2):
    """FA2 Proxy base contract"""

    def __init__(self, metadata, admin, parent, include_views=True):
        admin = sp.set_type_expr(admin, sp.TAddress)
        parent = sp.set_type_expr(parent, sp.TAddress)

        testFA2.__init__(self, metadata, admin, include_views=include_views)

        if VERBOSE: print("\nProxyBase")
        self.update_initial_storage(parent = parent)

        # get lazy entry points
        self.proxied_entrypoints = []
        for f in dir(self):
            attr = getattr(self, f)
            if isinstance(attr, sp.Entrypoint) and attr.message.lazify != False:
                self.proxied_entrypoints.append((attr.message.fname, attr.message.parameter_type))

        # Sort proxied (lazy) entrypoints (default comb?) to be able to find ep index.
        self.proxied_entrypoints.sort(key=lambda x: x[0])
        if VERBOSE: print(f"proxied_entrypoints: {[ ep[0] for ep in self.proxied_entrypoints ]}")

        self.ep_variant_type = sp.TVariant(**{entrypoint[0]: entrypoint[1] for entrypoint in self.proxied_entrypoints})


class FA2ProxyParent(
    FA2ProxyBase,
    Upgradeable
):
    """FA2 Proxy parent contract"""

    #def transfer_lambda(self, contract_self, params):
    #    sp.set_type(params, FA2.t_transfer_params)
    #    self.transfer.f(self, params)

    def __init__(self, metadata, admin, parent):
        # All entry points should be lazy, exceptions marked not lazy.
        self.add_flag("lazy-entry-points")

        admin = sp.set_type_expr(admin, sp.TAddress)
        parent = sp.set_type_expr(parent, sp.TAddress)

        FA2ProxyBase.__init__(self, metadata, admin, parent, include_views=False)

        if VERBOSE: print("\nProxyParent")
        # remove unneeded entrypoints
        keep_entrypoints = ["accept_administrator", "transfer_administrator", "update_ep"]
        deleted_entrypoints = []
        for f in dir(self):
            attr = getattr(self, f)
            if isinstance(attr, sp.Entrypoint) and attr.message.lazify == False and attr.message.fname not in keep_entrypoints:
                deleted_entrypoints.append(attr.message.fname)
                setattr(self, f, None)

        if VERBOSE: print(f"deleted_entrypoints: {deleted_entrypoints}")

        def get_ep_lambda(self, id):
            # Build a variant from proxied_entrypoints.
            sp.set_type(id, sp.TNat)
            sp.result(sp.entrypoint_map().get(id, message=sp.unit))

        self.get_ep_lambda = sp.onchain_view(pure=True)(get_ep_lambda)

        #for entrypoint in self.proxied_entrypoints:
        #    print(f"id {entrypoint[0]}:{sp.entrypoint_id(entrypoint[0])}")

        Upgradeable.__init__(self)


class FA2ProxyChild(
    FA2ProxyBase
):
    """FA2 Proxy child contract"""

    # NOTE: No entry points should be lazy.
    def __init__(self, metadata, admin, parent):
        admin = sp.set_type_expr(admin, sp.TAddress)
        parent = sp.set_type_expr(parent, sp.TAddress)

        FA2ProxyBase.__init__(self, metadata, admin, parent)

        if VERBOSE: print("\nProxyChild")
        for f in dir(self):
            attr = getattr(self, f)
            if isinstance(attr, sp.Entrypoint):
                # if found in proxied entrypoints, remove it.
                for ep in self.proxied_entrypoints:
                    if attr.message.fname == ep[0]:
                        variant_name = attr.message.fname
                        if VERBOSE: print(f'removing ep {variant_name}')
                        #setattr(self, f, sp.entry_point(None, None))
                        setattr(self, f, None)
                        #delattr(self, f)


    @sp.private_lambda(with_storage="read-write", with_operations=True)
    def executeParentLambda(self, params):
        sp.set_type(params, sp.TRecord(
            id = sp.TNat,
            args = self.ep_variant_type
        ))
        lambda_type = sp.TLambda(sp.TPair(self.ep_variant_type, self.storage_type), sp.TPair(sp.TList(sp.TOperation), self.storage_type))
        lambda_function = sp.compute(sp.view("get_ep_lambda", self.data.parent,
            sp.set_type_expr(params.id, sp.TNat),
            t = lambda_type).open_some())
        ops, storage = sp.match_pair(lambda_function(sp.pair(params.args, self.data)))
        self.data = storage
        sp.add_operations(ops)


    @sp.entry_point(lazify=False)
    def default(self, params):
        sp.set_type(params, self.ep_variant_type)

        # Build a matcher for proxied_entrypoints
        with params.match_cases() as arg:
            for index, entrypoint in enumerate(self.proxied_entrypoints):
                if VERBOSE: print(f"getting lambda for {entrypoint[0]}")
                with arg.match(entrypoint[0], f"{entrypoint[0]}_match"):
                    sp.compute(self.executeParentLambda(sp.record(id=sp.nat(index), args=params)))


    # NOTE: This can be on the child only. Base and Parent don't need it.
    @sp.entry_point(lazify=False, parameter_type=sp.TAddress)
    def set_parent(self, parent):
        self.onlyAdministrator()
        self.data.parent = parent