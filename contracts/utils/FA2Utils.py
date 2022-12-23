import smartpy as sp

from contracts import FA2


#
# FA2 views
#

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
# FA2 calls
#

def fa2_transfer_multi(contract, from_, transfer_list, nonstandard_transfer=False):
    sp.set_type(transfer_list, sp.TList(FA2.t_transfer_tx))
    c = sp.contract(
        FA2.t_transfer_params,
        contract,
        entry_point=("transfer_tokens" if nonstandard_transfer else "transfer")).open_some()
    sp.transfer(sp.list([sp.record(from_=from_, txs=transfer_list)]), sp.mutez(0), c)

def fa2_transfer(contract, from_, to_, token_id, item_amount, nonstandard_transfer=False):
    fa2_transfer_multi(contract, from_, sp.list([sp.record(amount=item_amount, to_=to_, token_id=token_id)]), nonstandard_transfer)