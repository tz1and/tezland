import smartpy as sp

fa2_contract = sp.io.import_script_from_url("file:contracts/FA2.py")

fa2_contract.add_test(fa2_contract.environment_config())