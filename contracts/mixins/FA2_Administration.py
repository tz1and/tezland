import smartpy as sp


t_transfer_fa2_administrator_params = sp.TList(sp.TRecord(
    fa2 = sp.TAddress,
    proposed_fa2_administrator = sp.TAddress
).layout(("fa2", "proposed_fa2_administrator")))

t_accept_fa2_administrator_params = sp.TList(sp.TAddress)


# Mixins required: Administrable
class FA2_Administration:
    def __init__(self):
        pass

    @sp.entry_point(parameter_type=t_transfer_fa2_administrator_params)
    def transfer_fa2_administrator(self, params):
        """Proposes to transfer the FA2 token contracts administator to another
        minter contract.
        """
        self.onlyAdministrator()

        with sp.for_("transfer", params) as transfer:
            # Get a handle on the FA2 contract transfer_administator entry point
            fa2_transfer_administrator_handle = sp.contract(
                t=sp.TAddress,
                address=transfer.fa2,
                entry_point="transfer_administrator").open_some()

            # Propose to transfer the FA2 token contract administrator
            sp.transfer(
                arg=transfer.proposed_fa2_administrator,
                amount=sp.mutez(0),
                destination=fa2_transfer_administrator_handle)

    @sp.entry_point(parameter_type=t_accept_fa2_administrator_params)
    def accept_fa2_administrator(self, params):
        """Accepts the FA2 contracts administrator responsabilities.
        """
        self.onlyAdministrator()

        with sp.for_("fa2", params) as fa2:
            # Get a handle on the FA2 contract accept_administrator entry point
            fa2_accept_administrator_handle = sp.contract(
                t=sp.TUnit,
                address=fa2,
                entry_point="accept_administrator").open_some()

            # Accept the FA2 token contract administrator responsabilities
            sp.transfer(
                arg=sp.unit,
                amount=sp.mutez(0),
                destination=fa2_accept_administrator_handle)
