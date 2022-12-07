import smartpy as sp

from contracts import FA2
from tezosbuilders_contracts_smartpy.utils import Utils
from contracts.utils import FA2Utils


#
# Class for multi fa2 token transfers.
class FA2TokenTransferMap:
    def __init__(self):
        self.internal_map = sp.local("transferMap", sp.map(tkey = sp.TAddress, tvalue = sp.TMap(sp.TNat, FA2.t_transfer_tx)))

    def add_fa2(self, fa2):
        sp.set_type(fa2, sp.TAddress)

        with sp.if_(~self.internal_map.value.contains(fa2)):
            self.internal_map.value[fa2] = {}

    def add_token(self, fa2, to_, token_id, token_amount):
        sp.set_type(fa2, sp.TAddress)
        sp.set_type(to_, sp.TAddress)
        sp.set_type(token_id, sp.TNat)
        sp.set_type(token_amount, sp.TNat)

        # NOTE: yes it seems silly to do it this way, but it generates much nicer code.
        fa2_map = sp.compute(self.internal_map.value.get(fa2, message=sp.unit))
        entry = sp.compute(fa2_map.get(token_id, default_value=sp.record(amount=0, to_=to_, token_id=token_id)))
        entry.amount += token_amount
        fa2_map[token_id] = entry
        self.internal_map.value[fa2] = fa2_map

    def transfer_tokens(self, from_):
        sp.set_type(from_, sp.TAddress)

        with sp.for_("transfer_item", self.internal_map.value.items()) as transfer_item:
            with sp.if_(sp.len(transfer_item.value) > 0):
                # NOTE: use rev_values to avoid reversing list.
                FA2Utils.fa2_transfer_multi(transfer_item.key, from_, transfer_item.value.rev_values())

    def trace(self):
        sp.trace(self.internal_map.value)


#
# Class for single fa2 token transfers.
class FA2TokenTransferMapSingle:
    def __init__(self, fa2):
        self.internal_map = sp.local("transferMap", sp.map(tkey = sp.TNat, tvalue = FA2.t_transfer_tx))
        self.internal_fa2 = sp.set_type_expr(fa2, sp.TAddress)

    def add_token(self, to_, token_id, token_amount):
        sp.set_type(to_, sp.TAddress)
        sp.set_type(token_id, sp.TNat)
        sp.set_type(token_amount, sp.TNat)

        # NOTE: yes it seems silly to do it this way, but it generates much nicer code.
        new_entry = sp.compute(self.internal_map.value.get(token_id, default_value=sp.record(amount=0, to_=to_, token_id=token_id)))
        new_entry.amount += token_amount
        self.internal_map.value[token_id] = new_entry

    def transfer_tokens(self, from_):
        sp.set_type(from_, sp.TAddress)

        with sp.if_(sp.len(self.internal_map.value) > 0):
            # NOTE: use rev_values to avoid reversing list.
            FA2Utils.fa2_transfer_multi(self.internal_fa2, from_, self.internal_map.value.rev_values())

    def trace(self):
        sp.trace(self.internal_map.value)
        sp.trace(self.internal_fa2)


#
# Class for native token transfers.
class TokenSendMap:
    def __init__(self):
        self.internal_map = sp.local("send_map", sp.map(tkey=sp.TAddress, tvalue=sp.TMutez))

    def add(self, address, amount):
        sp.set_type(address, sp.TAddress)
        sp.set_type(amount, sp.TMutez)
        self.internal_map.value[address] = self.internal_map.value.get(address, sp.mutez(0)) + amount

    def transfer(self):
        with sp.for_("send", self.internal_map.value.items()) as send:
            Utils.sendIfValue(send.key, send.value)

    def trace(self):
        sp.trace(self.internal_map.value)