import { DeployMode, SmartpyNodeDevConfig, LedgerAccount, PrivateKeyAccount } from './config/config';
import { readFileSync } from 'fs';

const { collectionsSignerKey, testnetDeployerKey, deployerKey, nftStorageApiKeys } = JSON.parse(
    readFileSync(new URL('../secrets.json', import.meta.url), { encoding: "utf-8" })
);

const config: SmartpyNodeDevConfig = {
    defaultNetwork: "sandbox",
    networks: {
        sandbox: {
            url: "http://localhost:20000",
            network: "sandboxnet",
            // Don't get all excited, this is the known key for Alice.
            accounts: {
                deployer: new PrivateKeyAccount("edsk3QoqBuvdamxouPhin7swCvkQNgq4jP5KZPbwWNnwdZpSpJiEbq"),
                collections_signer: new PrivateKeyAccount("edsk3QoqBuvdamxouPhin7swCvkQNgq4jP5KZPbwWNnwdZpSpJiEbq")
            }
        },
        mainnet: {
            url: "https://mainnet.api.tez.ie",
            network: "mainnet",
            accounts: {
                deployer: new LedgerAccount(),
                collections_signer: new PrivateKeyAccount(collectionsSignerKey)
            }
        },
        testnet: {
            url: "https://rpc.hangzhounet.teztnets.xyz",
            network: "hangzhounet",
            accounts: {
                deployer: new PrivateKeyAccount(testnetDeployerKey),
                collections_signer: new PrivateKeyAccount(collectionsSignerKey)
            }
        }
    },
    sandbox: {
        blockTime: 5, // In seconds.
        deployMode: DeployMode.DevWorld,
        bcdVersion: "master", // NOTE: lima support not in tagged release
        tzktVersion: "latest",
        flextesaVersion: "20221123",
        flextesaProtocol: "limabox"
    },
    ipfs: {
        localNodeUrl: "http://localhost:5001",
        nftStorageApiKeys: nftStorageApiKeys
    },
    smartpy: {
        exclude_tests: new Set(["DistrictDAO"]),
        test_dirs: new Set(['./tests/utils', './tests/legacy', './tests/legacy/mixins', './tests/mixins', './tests/upgrades', './tests'])
    }
}
export default config;