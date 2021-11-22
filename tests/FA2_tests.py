import smartpy as sp

fa2_contract = sp.io.import_script_from_url("file:contracts/FA2.py")

fa2_contract.add_test(fa2_contract.items_config())
fa2_contract.add_test(fa2_contract.places_config())
#if not fa2_contract.global_parameter("only_environment_test", False):
#    fa2_contract.add_test(fa2_contract.FA2_config(debug_mode = True), is_default = not sp.in_browser)
#    fa2_contract.add_test(fa2_contract.FA2_config(single_asset = True), is_default = not sp.in_browser)
#    fa2_contract.add_test(fa2_contract.FA2_config(non_fungible = True, add_mutez_transfer = True),
#             is_default = not sp.in_browser)
#    fa2_contract.add_test(fa2_contract.FA2_config(readable = False), is_default = not sp.in_browser)
#    fa2_contract.add_test(fa2_contract.FA2_config(force_layouts = False),
#             is_default = not sp.in_browser)
#    fa2_contract.add_test(fa2_contract.FA2_config(debug_mode = True, support_operator = False),
#             is_default = not sp.in_browser)
#    fa2_contract.add_test(fa2_contract.FA2_config(assume_consecutive_token_ids = False)
#             , is_default = not sp.in_browser)
#    fa2_contract.add_test(fa2_contract.FA2_config(store_total_supply = True)
#             , is_default = not sp.in_browser)
#    fa2_contract.add_test(fa2_contract.FA2_config(add_mutez_transfer = True)
#             , is_default = not sp.in_browser)
#    fa2_contract.add_test(fa2_contract.FA2_config(lazy_entry_points = True)
#             , is_default = not sp.in_browser)