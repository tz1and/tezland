import smartpy as sp

FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")

#########
# Tests #
#########

if "templates" not in __name__:
    TESTS = sp.io.import_script_from_url("file:tests/lib/FA2_test_lib.py")

    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    tok0_md = TESTS.make_metadata(name="Token Zero", decimals=1, symbol="Tok0")
    tok1_md = TESTS.make_metadata(name="Token One", decimals=1, symbol="Tok1")
    tok2_md = TESTS.make_metadata(name="Token Two", decimals=1, symbol="Tok2")

    TOKEN_METADATA = [tok0_md, tok1_md, tok2_md]

    class NftTest(
        FA2.Admin,
        FA2.ChangeMetadata,
        FA2.WithdrawMutez,
        FA2.MintNft,
        FA2.BurnNft,
        FA2.OnchainviewBalanceOf,
        FA2.OffchainviewTokenMetadata,
        FA2.Fa2Nft,
    ):
        """NFT contract with all optional features."""

        def __init__(self, policy=None):
            FA2.Fa2Nft.__init__(
                self, sp.utils.metadata_of_url("ipfs://example"), policy=policy
            )
            FA2.Admin.__init__(self, admin.address)

    class FungibleTest(
        FA2.Admin,
        FA2.ChangeMetadata,
        FA2.WithdrawMutez,
        FA2.MintFungible,
        FA2.BurnFungible,
        FA2.OnchainviewBalanceOf,
        FA2.OffchainviewTokenMetadata,
        FA2.Fa2Fungible,
    ):
        """Fungible contract with all optional features."""

        def __init__(self, policy=None):
            FA2.Fa2Fungible.__init__(
                self, sp.utils.metadata_of_url("ipfs://example"), policy=policy
            )
            FA2.Admin.__init__(self, admin.address)

    # Fa2Nft

    def nft_test(policy=None):
        return FA2.Fa2Nft(
            metadata=sp.utils.metadata_of_url("ipfs://example"),
            token_metadata=TOKEN_METADATA,
            ledger={0: alice.address, 1: alice.address, 2: alice.address},
            policy=policy,
        )

    TESTS.test_core_interfaces("nft", nft_test())
    TESTS.test_transfers("nft", nft_test())
    TESTS.test_balance_of("nft", nft_test())
    TESTS.test_no_transfer("nft", nft_test(policy=FA2.NoTransfer()))
    TESTS.test_owner_transfer("nft", nft_test(policy=FA2.OwnerTransfer()))
    TESTS.test_owner_or_operator_transfer("nft", nft_test())

    # Fa2Fungible

    def fungible_test(policy=None):
        return FA2.Fa2Fungible(
            metadata=sp.utils.metadata_of_url("ipfs://example"),
            token_metadata=TOKEN_METADATA,
            ledger={
                (alice.address, 0): 42,
                (alice.address, 1): 42,
                (alice.address, 2): 42,
            },
            policy=policy,
        )

    TESTS.test_core_interfaces("fungible", fungible_test())
    TESTS.test_transfers("fungible", fungible_test())
    TESTS.test_balance_of("fungible", fungible_test())
    TESTS.test_no_transfer("fungible", fungible_test(policy=FA2.NoTransfer()))
    TESTS.test_owner_transfer("fungible", fungible_test(policy=FA2.OwnerTransfer()))
    TESTS.test_owner_or_operator_transfer("fungible", fungible_test())

    # Optional Features

    TESTS.test_optional_features(
        nft_contract=NftTest(), fungible_contract=FungibleTest()
    )
    TESTS.test_pause(NftTest(FA2.PauseTransfer()), FungibleTest(FA2.PauseTransfer()))
