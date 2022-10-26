import { DeployMode, SmartpyNodeDevConfig, LedgerAccount, PrivateKeyAccount } from './config/config';
import { readFileSync } from 'fs';

const { testnetDeployerKey, deployerKey, nftStorageApiKey } = JSON.parse(
    readFileSync(new URL('../secrets.json', import.meta.url), { encoding: "utf-8" })
);

const config: SmartpyNodeDevConfig = {
    defaultNetwork: "sandbox",
    networks: {
        sandbox: {
            url: "http://localhost:20000",
            network: "sandboxnet",
            // Don't get all excited, this is the known key for Alice.
            accounts: { deployer: new PrivateKeyAccount("edsk3QoqBuvdamxouPhin7swCvkQNgq4jP5KZPbwWNnwdZpSpJiEbq") }
        },
        mainnet: {
            url: "https://mainnet.api.tez.ie",
            network: "mainnet",
            accounts: { deployer: new LedgerAccount() }
        },
        testnet: {
            url: "https://rpc.hangzhounet.teztnets.xyz",
            network: "hangzhounet",
            accounts: { deployer: new PrivateKeyAccount(testnetDeployerKey) }
        }
    },
    sandbox: {
        blockTime: 5, // In seconds.
        deployMode: DeployMode.DevWorld,
        bcdVersion: "latest",
        tzktVersion: "latest",
        flextesaVersion: "20220715",
        flextesaProtocol: "kathmandubox"
    },
    ipfs: {
        localNodeUrl: "http://localhost:5001",
        nftStorageApiKey: nftStorageApiKey
    },
    smartpy: {
        exclude_tests: new Set(["DistrictDAO", "FA2_proxy"])
    }
}
export default config;