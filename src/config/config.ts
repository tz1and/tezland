export type PrivateKey = string;
export type IpfsUrl = string;

export interface AccountType {}
export class LedgerAccount implements AccountType {}
export class PrivateKeyAccount implements AccountType {
    private_key: string;

    constructor(key: string) {
        this.private_key = key;
    }
}

export type AccountsConfig = {
    [accountName: string]: AccountType;
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
    nftStorageApiKeys: string[];
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
    bcdVersion: string;
    tzktVersion: string;
    flextesaVersion: string;
    flextesaProtocol: string;
}

export type SmartPyConfig = {
    exclude_tests: Set<string>;
    test_dirs: Set<string>;
}

export type SmartpyNodeDevConfig = {
    defaultNetwork: string;
    networks: NetworksConfig;
    sandbox: SandboxConfig;
    ipfs: IpfsConfig;
    smartpy: SmartPyConfig
}