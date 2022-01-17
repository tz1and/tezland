import smartpy as sp

fa2_contract = sp.io.import_script_from_url("file:contracts/FA2.py")

# test our specific config
fa2_contract.add_test(fa2_contract.items_config())
fa2_contract.add_test(fa2_contract.places_config())

# test all config
fa2_contract.add_test(fa2_contract.FA2_config(debug_mode = True))
fa2_contract.add_test(fa2_contract.FA2_config(single_asset = True))
fa2_contract.add_test(fa2_contract.FA2_config(non_fungible = True, add_mutez_transfer = True))
fa2_contract.add_test(fa2_contract.FA2_config(readable = False))
fa2_contract.add_test(fa2_contract.FA2_config(force_layouts = False))
fa2_contract.add_test(fa2_contract.FA2_config(debug_mode = True, support_operator = False))
fa2_contract.add_test(fa2_contract.FA2_config(assume_consecutive_token_ids = False))
fa2_contract.add_test(fa2_contract.FA2_config(store_total_supply = True))
fa2_contract.add_test(fa2_contract.FA2_config(add_mutez_transfer = True))
fa2_contract.add_test(fa2_contract.FA2_config(lazy_entry_points = True))