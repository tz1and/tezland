import smartpy as sp


# Mixins required: Administrable
class FA2_Administration:
    def __init__(self):
        pass

    @sp.entry_point
    def transfer_fa2_administrator(self, transfer_list):
        """Proposes to transfer the FA2 token contracts administator to another
        minter contract.
        """
        sp.set_type(transfer_list, sp.TList(sp.TRecord(
            fa2 = sp.TAddress,
            proposed_fa2_administrator = sp.TAddress
        ).layout(("fa2", "proposed_fa2_administrator"))))
        self.onlyAdministrator()

        with sp.for_("transfer", transfer_list) as transfer:
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

    @sp.entry_point
    def accept_fa2_administrator(self, accept_list):
        """Accepts the FA2 contracts administrator responsabilities.
        """
        sp.set_type(accept_list, sp.TList(sp.TAddress))
        self.onlyAdministrator()

        with sp.for_("fa2", accept_list) as fa2:
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
