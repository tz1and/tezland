import smartpy as sp

contract_metadata_mixin = sp.io.import_script_from_url("file:contracts/ContractMetadata.py")

class ContractMetadataTest(contract_metadata_mixin.ContractMetadata, sp.Contract):
    def __init__(self, administrator, metadata):
        contract_metadata_mixin.ContractMetadata.__init__(self, administrator = administrator, metadata = metadata)


@sp.add_test(name = "ContractMetadata_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("ContractMetadata contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

    scenario.h2("Test ContractMetadata")

    scenario.h3("Contract origination")
    initial_metadata = sp.utils.metadata_of_url("https://new_meta.com")
    change_metadata = ContractMetadataTest(admin.address, initial_metadata)
    scenario += change_metadata

    #
    # update_fees
    #
    scenario.h3("set_metadata")

    new_metadata = sp.utils.metadata_of_url("https://new_meta.com")
    new_metadata2 = sp.utils.metadata_of_url("https://new_meta2.com")

    scenario.verify(change_metadata.data.metadata[""] == initial_metadata[""])
    change_metadata.set_metadata(new_metadata).run(sender = bob, valid = False, exception = "ONLY_ADMIN")
    change_metadata.set_metadata(new_metadata).run(sender = alice, valid = False, exception = "ONLY_ADMIN")
    change_metadata.set_metadata(new_metadata).run(sender = admin)
    scenario.verify(change_metadata.data.metadata[""] == new_metadata[""])
    change_metadata.set_metadata(new_metadata2).run(sender = admin)
    scenario.verify(change_metadata.data.metadata[""] == new_metadata2[""])
