export type PrivateKey = string;
export type IpfsUrl = string;

export type AccountsConfig = {
    [accountName: string]: string;
}

export type NetworkConfig = {
    url: string;
    network: string;
    accounts: AccountsConfig;
}

export type NetworksConfig = {
    sandbox: NetworkConfig;
    mainnet: NetworkConfig;

    [networkName: string]: NetworkConfig;
}

export type IpfsConfig = {
    localNodeUrl: IpfsUrl;
    nftStorageApiKey: string;
    uploadToLocalIpfs: boolean;
}

export type SmartpyNodeDevConfig = {
    defaultNetwork: string;
    networks: NetworksConfig;
    ipfs: IpfsConfig;
}