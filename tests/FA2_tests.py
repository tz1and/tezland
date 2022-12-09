import smartpy as sp

from tezosbuilders_contracts_smartpy.mixins.Administrable import Administrable
from contracts import FA2


#########
# Tests #
#########

if "templates" not in __name__:
    from tests.lib import FA2_test_lib as TESTS

    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    tok0_md = TESTS.make_metadata(name="Token Zero", decimals=1, symbol="Tok0")
    tok1_md = TESTS.make_metadata(name="Token One", decimals=1, symbol="Tok1")
    tok2_md = TESTS.make_metadata(name="Token Two", decimals=1, symbol="Tok2")

    TOKEN_METADATA = [tok0_md, tok1_md, tok2_md]

    class NftTest(
        Administrable,
        FA2.ChangeMetadata,
        FA2.WithdrawMutez,
        FA2.MintNft,
        FA2.BurnNft,
        FA2.OffchainviewBalanceOf,
        FA2.OffchainviewTokenMetadata,
        FA2.OnchainviewCountTokens,
        FA2.Fa2Nft,
    ):
        """NFT contract with all optional features."""

        def __init__(self, policy=None):
            FA2.Fa2Nft.__init__(
                self, sp.utils.metadata_of_url("ipfs://example"), policy=policy
            )
            FA2.MintNft.__init__(self)
            Administrable.__init__(self, admin.address)

    class FungibleTest(
        Administrable,
        FA2.ChangeMetadata,
        FA2.WithdrawMutez,
        FA2.MintFungible,
        FA2.BurnFungible,
        FA2.OffchainviewBalanceOf,
        FA2.OffchainviewTokenMetadata,
        FA2.OnchainviewCountTokens,
        FA2.Fa2Fungible,
    ):
        """Fungible contract with all optional features."""

        def __init__(self, policy=None):
            FA2.Fa2Fungible.__init__(
                self, sp.utils.metadata_of_url("ipfs://example"), policy=policy
            )
            FA2.MintFungible.__init__(self)
            Administrable.__init__(self, admin.address)

    class SingleAssetTest(
        Administrable,
        FA2.ChangeMetadata,
        FA2.WithdrawMutez,
        FA2.MintSingleAsset,
        FA2.BurnSingleAsset,
        FA2.OffchainviewBalanceOf,
        FA2.OffchainviewTokenMetadata,
        FA2.OnchainviewCountTokens,
        FA2.Fa2SingleAsset,
    ):
        """Single asset contract with all optional features."""

        def __init__(self, policy=None):
            FA2.Fa2SingleAsset.__init__(
                self, sp.utils.metadata_of_url("ipfs://example"), policy=policy
            )
            Administrable.__init__(self, admin.address)

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

    # Fa2SingleAsset

    TOKEN_METADATA = [tok0_md]

    def single_asset_test(policy=None):
        return FA2.Fa2SingleAsset(
            metadata=sp.utils.metadata_of_url("ipfs://example"),
            token_metadata=TOKEN_METADATA,
            ledger={ alice.address: 42 },
            policy=policy,
        )

    TESTS.test_core_interfaces("single_asset", single_asset_test())
    TESTS.test_transfers("single_asset", single_asset_test())
    TESTS.test_balance_of("single_asset", single_asset_test())
    TESTS.test_no_transfer("single_asset", single_asset_test(policy=FA2.NoTransfer()))
    TESTS.test_owner_transfer("single_asset", single_asset_test(policy=FA2.OwnerTransfer()))
    TESTS.test_owner_or_operator_transfer("single_asset", single_asset_test())

    # Optional Features

    TESTS.test_optional_features(
        nft_contract=NftTest(), fungible_contract=FungibleTest(), single_asset_contract=SingleAssetTest()
    )
    TESTS.test_pause(NftTest(FA2.PauseTransfer()), FungibleTest(FA2.PauseTransfer()), SingleAssetTest(FA2.PauseTransfer()))
    TESTS.test_adhoc_operators(NftTest(FA2.OwnerOrOperatorAdhocTransfer()), FungibleTest(FA2.OwnerOrOperatorAdhocTransfer()), SingleAssetTest(FA2.OwnerOrOperatorAdhocTransfer()))

    # Royalties

    class NftRoyaltiesTest(
        Administrable,
        FA2.MintNft,
        FA2.Royalties,
        FA2.Fa2Nft,
    ):
        """NFT contract for testing royalties."""

        def __init__(self, policy=None):
            FA2.Fa2Nft.__init__(
                self, sp.utils.metadata_of_url("ipfs://example"), policy=policy, has_royalties=True
            )
            FA2.MintNft.__init__(self)
            FA2.Royalties.__init__(self)
            Administrable.__init__(self, admin.address)

    class FungibleRoyaltiesTest(
        Administrable,
        FA2.MintFungible,
        FA2.Royalties,
        FA2.Fa2Fungible,
    ):
        """Fungible contract with all optional features."""

        def __init__(self, policy=None):
            FA2.Fa2Fungible.__init__(
                self, sp.utils.metadata_of_url("ipfs://example"), policy=policy, has_royalties=True
            )
            FA2.MintFungible.__init__(self)
            FA2.Royalties.__init__(self)
            Administrable.__init__(self, admin.address)
    
    TESTS.test_royalties(NftRoyaltiesTest(), FungibleRoyaltiesTest()) # no royalties on single asset
