import smartpy as sp

FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")

#
# Lazy set of permitted FA2 tokens for 'other' type.
class Address_set:
    def make(self, fa2_map={}):
        return sp.big_map(l=fa2_map, tkey=sp.TAddress, tvalue=sp.TUnit)
    def add(self, set, fa2):
        set[fa2] = sp.unit
    def remove(self, set, fa2):
        del set[fa2]
    def contains(self, set, fa2):
        return set.contains(fa2)

def isPowerOfTwoMinusOne(x):
    """Returns true if x is power of 2 - 1"""
    return ((x + 1) & x) == sp.nat(0)

def send_if_value(to, amount):
    """Transfer amount if greater 0"""
    with sp.if_(amount > sp.tez(0)):
        sp.send(to, amount)


#
# Metaclass for token transfers.
class TokenTransferMap:
    def init(self):
        return sp.local("transferMap", sp.map(tkey = sp.TNat, tvalue = FA2.t_transfer_tx))

    def add_token(self, transferMap, to_, token_id, token_amount):
        sp.set_type(to_, sp.TAddress)
        sp.set_type(token_id, sp.TNat)
        sp.set_type(token_amount, sp.TNat)

        with sp.if_(transferMap.value.contains(token_id)):
            transferMap.value[token_id].amount += token_amount
        with sp.else_():
            transferMap.value[token_id] = sp.record(amount=token_amount, to_=to_, token_id=token_id)

    def transfer_tokens(self, transferMap, fa2, from_):
        sp.set_type(fa2, sp.TAddress)
        sp.set_type(from_, sp.TAddress)

        with sp.if_(sp.len(transferMap.value) > 0):
            fa2_transfer_multi(fa2, from_, transferMap.value.values())


#
# Validate IPFS Uri
def validate_ipfs_uri(metadata_uri):
    # Basic validation of the metadata, try to make sure it's a somewhat valid ipfs URI.
    # Ipfs cid v0 + proto is 53 chars.
    sp.verify((sp.slice(metadata_uri, 0, 7).open_some("INVALID_METADATA") == sp.utils.bytes_of_string("ipfs://"))
        & (sp.len(metadata_uri) >= sp.nat(53)), "INVALID_METADATA")

#
# tz1and fa2 extension royalties
def tz1and_items_get_royalties(fa2, token_id):
    return sp.view("get_token_royalties", fa2,
        sp.set_type_expr(token_id, sp.TNat),
        t = FA2.t_royalties).open_some()

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

# Not used, World now has it's own operators set.
#def fa2_is_operator(self, fa2, token_id, owner, operator):
#    return sp.view("is_operator", fa2,
#        sp.set_type_expr(
#            sp.record(token_id = token_id, owner = owner, operator = operator),
#            sp.TRecord(
#                token_id = sp.TNat,
#                owner = sp.TAddress,
#                operator = sp.TAddress
#            ).layout(("owner", ("operator", "token_id")))),
#        t = sp.TBool).open_some()

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

def fa2_nft_royalties_mint(batch, contract):
    sp.set_type(batch, FA2.t_mint_nft_royalties_batch)
    sp.set_type(contract, sp.TAddress)
    c = sp.contract(
        FA2.t_mint_nft_royalties_batch,
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

def fa2_fungible_royalties_mint(batch, contract):
    sp.set_type(batch, FA2.t_mint_fungible_royalties_batch)
    sp.set_type(contract, sp.TAddress)
    c = sp.contract(
        FA2.t_mint_fungible_royalties_batch,
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