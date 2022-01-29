type PrivateKey = string;
type IpfsUrl = string;

type AccountsConfig = {
    [accountName: string]: string;
}

type NetworkConfig = {
    url: string;
    network: string;
    accounts: AccountsConfig;
}

type NetworksConfig = {
    sandbox: NetworkConfig;
    mainnet: NetworkConfig;

    [networkName: string]: NetworkConfig;
}

type IpfsConfig = {
    localNodeUrl: IpfsUrl;
    nftStorageApiKey: string;
    uploadToLocalIpfs: boolean;
}

type SmartpyNodeDevConfig = {
    defaultNetwork: string;
    networks: NetworksConfig;
    ipfs: IpfsConfig;
}