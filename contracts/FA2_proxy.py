from dataclasses import replace
import types
import smartpy as sp

from tezosbuilders_contracts_smartpy.mixins.Administrable import Administrable
from contracts import FA2


class ProxyBase(
    Administrable,
    FA2.ChangeMetadata,
    FA2.MintFungible,
    FA2.BurnFungible,
    FA2.Royalties,
    FA2.Fa2Fungible,
):
    """FA2 Proxy base contract"""

    def __init__(self, metadata, admin, parent):
        admin = sp.set_type_expr(admin, sp.TAddress)
        parent = sp.set_type_expr(parent, sp.TAddress)

        FA2.Fa2Fungible.__init__(
            self, metadata=metadata,
            name="tz1and Collection", description="tz1and Item Collection.",
            # TODO: figure out if we *need* FA2.PauseTransfer()
            # It might be good to have, simply for security reasons...
            # Then again, if the FA2 is borked, pausing is destructive to value as well.
            # But one could migrate to another FA2 before all value is lost. So maybe worth it...
            policy=FA2.PauseTransfer(FA2.OwnerOrOperatorAdhocTransfer()), has_royalties=True,
            allow_mint_existing=False
        )
        FA2.Royalties.__init__(self)
        Administrable.__init__(self, admin)

        self.update_initial_storage(parent = parent)

        # get lazy entry points
        self.proxied_entrypoints = []
        for f in dir(self):
            attr = getattr(self, f)
            if isinstance(attr, sp.Entrypoint) and attr.message.lazify != False:
                self.proxied_entrypoints.append((attr.message.fname, attr.message.parameter_type))

        print([ ep[0] for ep in self.proxied_entrypoints ])

    # TODO: can this be on the child only?
    @sp.entry_point(parameter_type=sp.TAddress)
    def set_parent(self, parent):
        sp.set_type(parent, sp.TAddress)
        self.data.parent = parent

    @sp.onchain_view(pure=True)
    def get_parent(self):
        sp.result(self.data.parent)

#class ProxyBase(sp.Contract):
#    def __init__(self, metadata, admin, parent):
#        admin = sp.set_type_expr(admin, sp.TAddress)
#        parent = sp.set_type_expr(parent, sp.TAddress)
#
#        sp.Contract.__init__(self)
#
#        self.init_storage(parent = parent)
#
#        # get lazy entry points
#        self.proxied_entrypoints = []
#        for f in dir(self):
#            attr = getattr(self, f)
#            if isinstance(attr, sp.Entrypoint) and attr.message.lazify != False:
#                self.proxied_entrypoints.append((attr.message.fname, attr.message.parameter_type))
#
#        print([ ep[0] for ep in self.proxied_entrypoints ])
#
#    # TODO: can this be on the child only?
#    @sp.entry_point(parameter_type=sp.TRecord(fa2=sp.TAddress, id=sp.TNat))
#    def get_token(self, params):
#        #sp.set_type(parent, sp.TAddress)
#        sp.trace(params)
#
#    # TODO: can this be on the child only?
#    @sp.entry_point(parameter_type=sp.TAddress)
#    def set_parent(self, parent):
#        #sp.set_type(parent, sp.TAddress)
#        self.data.parent = parent
#
#    @sp.onchain_view(pure=True)
#    def get_parent(self):
#        sp.result(self.data.parent)


class FA2ProxyParent(
    ProxyBase
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

        ProxyBase.__init__(self, metadata, admin, parent)

        def get_ep_lambda(self, ep_name):
            # Build a variant from proxied_entrypoints.
            sp.set_type(ep_name, sp.TVariant(
                **{entrypoint[0]: sp.TUnit for entrypoint in self.proxied_entrypoints}))

            # Build a matcher for proxied_entrypoints
            with ep_name.match_cases() as arg:
                for entrypoint in self.proxied_entrypoints:
                    print(f"matching {entrypoint[0]}")
                    with arg.match(entrypoint[0]):
                        sp.trace(sp.entrypoint_map())
                        sp.trace(sp.entrypoint_map()[sp.entrypoint_id(entrypoint[0])])
                        sp.result(sp.entrypoint_map()[sp.entrypoint_id(entrypoint[0])])

        self.get_ep_lambda = sp.onchain_view(pure=True)(get_ep_lambda)


class FA2ProxyChild(
    ProxyBase
):
    """FA2 Proxy child contract"""

    # NOTE: No entry points should be lazy.
    def __init__(self, metadata, admin, parent):
        admin = sp.set_type_expr(admin, sp.TAddress)
        parent = sp.set_type_expr(parent, sp.TAddress)

        ProxyBase.__init__(self, metadata, admin, parent)

        for f in dir(self):
            attr = getattr(self, f)
            if isinstance(attr, sp.Entrypoint):
                # if found in proxied entrypoints, remove it.
                for ep in self.proxied_entrypoints:
                    if attr.message.fname == ep[0]:
                        variant_name = attr.message.fname
                        print(f'removing ep {variant_name}')
                        setattr(self, f, sp.entry_point(None, None))
                        #setattr(self, f, None)

    @sp.private_lambda(with_storage="read-only")
    def getParentLambda(self, name):
        var_type = sp.TPair(sp.TVariant(**{entrypoint[0]: entrypoint[1] for entrypoint in self.proxied_entrypoints}), self.storage_type)
        lambda_type = sp.TLambda(var_type, sp.TPair(sp.TList(sp.TOperation), self.storage_type))
        sp.result(sp.view("get_ep_lambda", self.data.parent,
            sp.set_type_expr(name, sp.TVariant(
            **{entrypoint[0]: sp.TUnit for entrypoint in self.proxied_entrypoints})),
            t = lambda_type).open_some())
       

    # TODO: view per parent entrypoint.
    @sp.entry_point(lazify=False)
    def default(self, params):
        sp.set_type(params, sp.TVariant(
            **{entrypoint[0]: entrypoint[1] for entrypoint in self.proxied_entrypoints}))

        # Build a matcher for proxied_entrypoints
        with params.match_cases() as arg:
            for entrypoint in self.proxied_entrypoints:
                print(f"getting lambda for {entrypoint[0]}")
                with arg.match(entrypoint[0], f"{entrypoint[0]}_match"):
                    lambda_function = sp.compute(self.getParentLambda(sp.variant(entrypoint[0], sp.unit)))
                    ops, storage = sp.match_pair(lambda_function(sp.pair(params, self.data)))
                    sp.add_operations(ops)
                    self.data = storage
