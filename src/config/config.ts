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
}

export enum DeployMode {
    None,
    DevWorld,
    GasTest,
    StressTestSingle,
    StressTestMulti
};

export type SandboxConfig = {
    blockTime: number;
    deployMode: DeployMode;
}

export type SmartPyConfig = {
    exclude_tests: Set<string>;
}

export type SmartpyNodeDevConfig = {
    defaultNetwork: string;
    networks: NetworksConfig;
    sandbox: SandboxConfig;
    ipfs: IpfsConfig;
    smartpy: SmartPyConfig
}