import smartpy as sp

fa2_contract = sp.io.import_script_from_url("file:contracts/FA2.py")

# test our specific config
fa2_contract.add_test(fa2_contract.items_config())
fa2_contract.add_test(fa2_contract.places_config())
fa2_contract.add_test(fa2_contract.dao_config())

# test all config
# TODO: fix tests for burn disabled
fa2_contract.add_test(fa2_contract.FA2_config(single_asset = True, allow_burn_tokens = True))
fa2_contract.add_test(fa2_contract.FA2_config(non_fungible = True, add_mutez_transfer = True, allow_burn_tokens = True))
fa2_contract.add_test(fa2_contract.FA2_config(store_total_supply = True, allow_burn_tokens = True))
fa2_contract.add_test(fa2_contract.FA2_config(add_mutez_transfer = True, allow_burn_tokens = True))
fa2_contract.add_test(fa2_contract.FA2_config(lazy_entry_points = True, allow_burn_tokens = True))

fa2_contract.add_test(fa2_contract.FA2_config(single_asset = True, allow_burn_tokens = True, operator_burn = True))
fa2_contract.add_test(fa2_contract.FA2_config(non_fungible = True, add_mutez_transfer = True, allow_burn_tokens = True, operator_burn = True))
fa2_contract.add_test(fa2_contract.FA2_config(store_total_supply = True, allow_burn_tokens = True, operator_burn = True))
fa2_contract.add_test(fa2_contract.FA2_config(add_mutez_transfer = True, allow_burn_tokens = True, operator_burn = True))
fa2_contract.add_test(fa2_contract.FA2_config(lazy_entry_points = True, allow_burn_tokens = True, operator_burn = True))