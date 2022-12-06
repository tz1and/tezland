from dataclasses import replace
import types
import smartpy as sp

from contracts.mixins.Administrable import Administrable
from contracts import FA2


class FA2ProxyBase(
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
                self.proxied_entrypoints.append(attr.message.fname)

        print(self.proxied_entrypoints)

    # TODO: can this be on the child only?
    @sp.entry_point(lazify=False)
    def set_parent(self, parent):
        sp.set_type(parent, sp.TAddress)
        self.data.parent = parent


class FA2ProxyParent(
    FA2ProxyBase
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

        FA2ProxyBase.__init__(self, metadata, admin, parent)

        def get_ep_lambda(self, ep_name):
            # Build a variant from proxied_entrypoints.
            sp.set_type(ep_name, sp.TVariant(
                **{entrypoint: sp.TUnit for entrypoint in self.proxied_entrypoints}))

            # Build a matcher for proxied_entrypoints
            with ep_name.match_cases() as arg:
                for entrypoint in self.proxied_entrypoints:
                    with arg.match(entrypoint):
                        sp.result(sp.entrypoint_map()[sp.entrypoint_id(entrypoint)])

        self.get_ep_lambda = sp.onchain_view(pure=True)(get_ep_lambda)

        self.transfer = types.MethodType(self.transfer.f, self)

        def get_private_lambda(self):
            sp.result(self.data.test_private_lambda)

        self.get_private_lambda = sp.onchain_view(pure=True)(get_private_lambda)

        self.update_initial_storage(
            test_private_lambda = sp.build_lambda(self.transfer, with_storage=None, with_operations=True)#, contract_self=self)
        )


class FA2ProxyChild(
    FA2ProxyBase
):
    """FA2 Proxy child contract"""

    # NOTE: No entry points should be lazy.
    def __init__(self, metadata, admin, parent):
        admin = sp.set_type_expr(admin, sp.TAddress)
        parent = sp.set_type_expr(parent, sp.TAddress)

        FA2ProxyBase.__init__(self, metadata, admin, parent)

        # *sigh* I don't know why I have to do this.
        def update_adhoc_operators(self, batch):
            sp.set_type(batch, FA2.t_adhoc_operator_params)
            pass
            #lambda_function = self.getParentLambda(sp.variant("update_adhoc_operators", sp.unit))
            #operations = lambda_function(sp.variant("update_adhoc_operators", batch))
            #sp.add_operations(operations)

        self.update_adhoc_operators = sp.entry_point(update_adhoc_operators)

        #for f in dir(self):
        #    attr = getattr(self, f)
        #    if isinstance(attr, sp.Entrypoint) and attr.message.fname in self.proxied_entrypoints:
        #        variant_name = attr.message.fname
        #        print(f'gotta proxy {variant_name} here')
        #        def our_replacement(self, params):
        #            nonlocal variant_name
        #            lambda_type = sp.TUnit
        #            lambda_function = self.getParentLambda(sp.variant(variant_name, sp.unit), lambda_type)
        #            lambda_function(params)
        #        setattr(self, f, sp.entry_point(our_replacement, name=attr.message.fname))

    def getParentLambda(self, name):
        return sp.view("get_ep_lambda", self.data.parent,
            sp.set_type_expr(name, sp.TVariant(
            **{entrypoint: sp.TUnit for entrypoint in self.proxied_entrypoints})),
            t = sp.TUnit).open_some()

    #@sp.entry_point
    #def accept_administrator(self):
    #    lambda_function = self.getParentLambda(sp.variant("accept_administrator", sp.unit), sp.TUnit)
    #    sp.add_operations(lambda_function(sp.unit))

    @sp.entry_point
    def mint(self, batch):
        sp.set_type(batch, FA2.t_mint_fungible_royalties_batch)
        pass
        #lambda_function = self.getParentLambda(sp.variant("mint", sp.unit))
        #operations = lambda_function(sp.variant("mint", batch))
        #sp.add_operations(operations)

    #@sp.entry_point
    #def burn(self, batch):
    #    sp.set_type(batch, FA2.t_burn_batch)
    #    lambda_function = self.getParentLambda(sp.variant("burn", sp.unit))
    #    operations = lambda_function(sp.variant("burn", batch))
    #    sp.add_operations(operations)
#
    #@sp.entry_point
    #def balance_of(self, batch):
    #    sp.set_type(batch, FA2.t_balance_of_params)
    #    lambda_function = self.getParentLambda(sp.variant("balance_of", sp.unit))
    #    operations = lambda_function(sp.variant("balance_of", batch))
    #    sp.add_operations(operations)
#
    #@sp.entry_point
    #def transfer(self, batch):
    #    sp.set_type(batch, FA2.t_transfer_params)
    #    lambda_function = self.getParentLambda(sp.variant("transfer", sp.unit))
    #    operations = lambda_function(sp.variant("transfer", batch))
    #    sp.add_operations(operations)
#
    #@sp.entry_point
    #def update_operators(self, batch):
    #    sp.set_type(batch, FA2.t_update_operators_params)
    #    lambda_function = self.getParentLambda(sp.variant("update_operators", sp.unit))
    #    operations = lambda_function(sp.variant("update_operators", batch))
    #    sp.add_operations(operations)
#
