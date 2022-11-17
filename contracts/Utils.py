import smartpy as sp

FA2_legacy = sp.io.import_script_from_url("file:contracts/legacy/FA2_legacy.py")
FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")


#
# Generic (lazy) map for convenience.
class GenericMap:
    def __init__(self, key_type, value_type, default_value=None, get_error=None, big_map=True) -> None:
        self.key_type = key_type
        self.value_type = value_type
        self.default_value = default_value
        self.get_error = get_error
        self.big_map = big_map

    def make(self, defaults={}):
        if self.big_map:
            return sp.big_map(l=defaults, tkey=self.key_type, tvalue=self.value_type)
        else:
            return sp.map(l=defaults, tkey=self.key_type, tvalue=self.value_type)

    def add(self, map, key, value = None):
        if value is None:
            if self.default_value is not None:
                map[key] = self.default_value
            else:
                sp.failwith("NO_DEFAULT_VALUE")
        else:
            map[key] = value

    def remove(self, map, key):
        del map[key]

    def contains(self, map, key):
        return map.contains(key)

    def get(self, map, key):
        return map.get(key, message=self.get_error)


#
# Lazy set of addresses.
class AddressSet(GenericMap):
    def __init__(self):
        super().__init__(sp.TAddress, sp.TUnit, sp.unit)


#
# Utility functions
def isPowerOfTwoMinusOne(x):
    """Returns true if x is power of 2 - 1"""
    return ((x + 1) & x) == sp.nat(0)

def send_if_value(to, amount):
    """Transfer amount if greater 0"""
    with sp.if_(amount > sp.tez(0)):
        sp.send(to, amount)

@sp.inline_result
def openSomeOrDefault(e: sp.TOption, default):
    with e.match_cases() as arg:
        with arg.match("None"):
            sp.result(default)
        with arg.match("Some") as open:
            sp.result(open)


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
        fa2_map_opt = self.internal_map.value.get_opt(fa2)
        with fa2_map_opt.match_cases() as arg:
            with arg.match("Some") as fa2_map_some:
                fa2_map = sp.compute(fa2_map_some)
                new_entry = sp.compute(fa2_map.get(token_id, default_value=sp.record(amount=0, to_=to_, token_id=token_id)))
                new_entry.amount += token_amount
                fa2_map[token_id] = new_entry
                self.internal_map.value[fa2] = fa2_map

            with arg.match("None"):
                sp.failwith(sp.unit)

    def transfer_tokens(self, from_):
        sp.set_type(from_, sp.TAddress)

        with sp.for_("transfer_item", self.internal_map.value.items()) as transfer_item:
            with sp.if_(sp.len(transfer_item.value) > 0):
                fa2_transfer_multi(transfer_item.key, from_, transfer_item.value.values())

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
            fa2_transfer_multi(self.internal_fa2, from_, self.internal_map.value.values())

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
            send_if_value(send.key, send.value)

    def trace(self):
        sp.trace(self.internal_map.value)

#
# Validate IPFS Uri
def validate_ipfs_uri(metadata_uri):
    # Basic validation of the metadata, try to make sure it's a somewhat valid ipfs URI.
    # Ipfs cid v0 + proto is 53 chars.
    sp.verify((sp.slice(metadata_uri, 0, 7).open_some("INVALID_METADATA") == sp.utils.bytes_of_string("ipfs://"))
        & (sp.len(metadata_uri) >= sp.nat(53)), "INVALID_METADATA")

#
# FA2 views
def fa2_get_balance(fa2, token_id, owner):
    return sp.view("get_balance", fa2,
        sp.set_type_expr(
            sp.record(owner = owner, token_id = token_id),
            sp.TRecord(
                owner = sp.TAddress,
                token_id = sp.TNat
            ).layout(("owner", "token_id"))),
        t = sp.TNat).open_some()

def fa2_is_operator(fa2, token_id, owner, operator):
    return sp.view("is_operator", fa2,
        sp.set_type_expr(
            sp.record(token_id = token_id, owner = owner, operator = operator),
            FA2.t_operator_permission),
        t = sp.TBool).open_some()

#
# FA2 transfers
def fa2_transfer_multi(contract, from_, transfer_list):
    sp.set_type(transfer_list, sp.TList(FA2.t_transfer_tx))
    c = sp.contract(
        FA2.t_transfer_params,
        contract,
        entry_point='transfer').open_some()
    sp.transfer(sp.list([sp.record(from_=from_, txs=transfer_list)]), sp.mutez(0), c)

def fa2_transfer(contract, from_, to_, token_id, item_amount):
    fa2_transfer_multi(contract, from_, sp.list([sp.record(amount=item_amount, to_=to_, token_id=token_id)]))

#
# FA2 mint
def fa2_nft_mint(batch, contract):
    sp.set_type(batch, FA2.t_mint_nft_batch)
    sp.set_type(contract, sp.TAddress)
    c = sp.contract(
        FA2.t_mint_nft_batch,
        contract,
        entry_point='mint').open_some()
    sp.transfer(batch, sp.mutez(0), c)

def fa2_fungible_mint(batch, contract):
    sp.set_type(batch, FA2.t_mint_fungible_batch)
    sp.set_type(contract, sp.TAddress)
    c = sp.contract(
        FA2.t_mint_fungible_batch,
        contract,
        entry_point='mint').open_some()
    sp.transfer(batch, sp.mutez(0), c)

def fa2_single_asset_mint(batch, contract):
    fa2_fungible_mint(batch, contract)

#
# FA2/ContractMetadata set_metadata
def contract_set_metadata(contract, metadata_uri):
    sp.set_type(contract, sp.TAddress)
    sp.set_type(metadata_uri, sp.TBytes)
    set_metadata_handle = sp.contract(
        sp.TBigMap(sp.TString, sp.TBytes),
        contract,
        entry_point='set_metadata').open_some()
    sp.transfer(sp.big_map({"": metadata_uri}), sp.mutez(0), set_metadata_handle)