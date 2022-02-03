import { SmartpyNodeDevConfig } from './config/config';
const { testnetDeployerKey, deployerKey, nftStorageApiKey } = require('../secrets.json');

const config: SmartpyNodeDevConfig = {
    defaultNetwork: "sandbox",
    networks: {
        sandbox: {
            url: "http://localhost:20000",
            network: "sandboxnet",
            // Don't get all excited, this is the known key for Alice.
            accounts: { deployer: "edsk3QoqBuvdamxouPhin7swCvkQNgq4jP5KZPbwWNnwdZpSpJiEbq" }
        },
        mainnet: {
            url: "https://mainnet.api.tez.ie",
            network: "mainnet",
            accounts: { deployer: deployerKey }
        },
        testnet: {
            url: "https://rpc.hangzhounet.teztnets.xyz",
            network: "hangzhounet",
            accounts: { deployer: testnetDeployerKey }
        }
    },
    ipfs: {
        localNodeUrl: "http://localhost:5001",
        nftStorageApiKey: nftStorageApiKey,
        uploadToLocalIpfs: true
    }
}
export default config;