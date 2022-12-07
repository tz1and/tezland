import { TezosToolkit, ContractAbstraction, WalletOperationBatch, OpKind, Wallet, TransactionWalletOperation } from "@taquito/taquito";
import { BatchWalletOperation } from "@taquito/taquito/dist/types/wallet/batch-operation";
import { OperationContentsAndResult } from "@taquito/rpc";
import { InMemorySigner } from "@taquito/signer";
import { OperationContentsAndResultOrigination } from '@taquito/rpc';
import { LedgerSigner } from '@taquito/ledger-signer';
import TransportNodeHid from '@ledgerhq/hw-transport-node-hid';
import { performance } from 'perf_hooks';
import config from '../user.config';
import { PrivateKeyAccount, LedgerAccount, NetworkConfig } from '../config/config';
import DeploymentsRegistry from "./DeploymentsRegistry";
import assert from 'assert';
import kleur from 'kleur';
import prompt from 'prompt';
import fs from 'fs';
import util, { promisify } from 'util';
import * as smartpy from './smartpy';
import * as ipfs from '../ipfs'


type FeeResult = {
    storage: string;
    fee: string;
}

export const sleep = promisify(setTimeout);

// NOTE: only works with single origination per op
export class DeployContractBatch {
    private batch: WalletOperationBatch;
    private deploy: DeployBase;

    private contractList: { name: string, address: string}[] = [];

    constructor(deploy: DeployBase) {
        assert(deploy.tezos);
        this.batch = deploy.tezos.wallet.batch();
        this.deploy = deploy;
    }

    public addToBatch(contract_name: string) {
        assert(this.deploy.tezos);

        // Check if deployment is in project.deployments.json
        // if yes, skip.
        const existingDeployment = this.deploy.deploymentsReg.getContract(contract_name);
        this.contractList.push({name: contract_name, address: existingDeployment ? existingDeployment : ''});
        if(existingDeployment) {
            console.log(`>> Using existing deployment for '${contract_name}': ${existingDeployment}\n`);
            return;
        }

        const { codeJson, initJson } = this.deploy.copyAndReadCode(contract_name);

        this.batch.withOrigination({
            code: codeJson,
            init: initJson,
        });

        // Write deployment (name, address) to project.deployments.json
        //this.addDeployment(contract_name, contract.address);
    }

    public async deployBatch() {
        if (this.contractList.filter(item => !item.address).length === 0)
            return this.get_originated_contracts_batch([]);

        const batch_op = await this.batch.send();
        await batch_op.confirmation();

        console.log(`Successfully deployed contracts in batch`);
        console.log(`>> Transaction hash: ${batch_op.opHash}`);

        const results = await batch_op.operationResults();
        return this.get_originated_contracts_batch(results);
    }

    private async get_originated_contracts_batch(results: OperationContentsAndResult[]): Promise<ContractAbstraction<Wallet>[]> {
        assert(this.deploy.tezos);

        const filtered_contracts = this.contractList.filter(item => !item.address);
        assert(results.length === filtered_contracts.length);

        for (let i = 0; i < results.length; ++i) {
            const res = results[i];
            assert(res.kind === OpKind.ORIGINATION);
            const orig_res = res as OperationContentsAndResultOrigination;
            const contract_name = filtered_contracts[i].name;
            const contract_address = orig_res.metadata.operation_result!.originated_contracts![0];

            console.log(`>> ${contract_name} address: ${contract_address}`);

            // let's hope it's a ref
            filtered_contracts[i].address = contract_address;

            this.deploy.deploymentsReg.addContract(contract_name, contract_address);
        }

        console.log();

        const contracts = [];
        for (const c of this.contractList)
            contracts.push(await this.deploy.tezos.wallet.at(c.address));

        return contracts;
    }
}


export default class DeployBase {

    private networkConfig: NetworkConfig;
    protected network: string;
    protected isSandboxNet: boolean;
    protected cleanDeploymentsInSandbox: boolean;

    public tezos?: TezosToolkit;
    protected accountAddress?: string;

    private deploymentsDir: string;

    readonly deploymentsReg: DeploymentsRegistry;

    public getNetwork(): string { return this.network; }
    public isSandboxNetwork(): boolean { return this.isSandboxNet; }

    constructor(options: any) {
        // set network to deploy to.
        if(!options.network) this.network = config.defaultNetwork;
        else this.network = options.network;

        this.isSandboxNet = this.network === "sandbox";
        this.cleanDeploymentsInSandbox = true;

        // get and validate network config.
        this.networkConfig = config.networks[this.network];
        assert(this.networkConfig, `Network config not found for '${this.network}'`);
        assert(this.networkConfig.accounts.deployer, `deployer account not set for '${this.network}'`)

        this.deploymentsDir = `./deployments/${this.network}`;
        this.deploymentsReg = new DeploymentsRegistry(`${this.deploymentsDir}/project.deployments.json`)
    }

    private async initTezosToolkit() {
        let signer;
        if (this.networkConfig.accounts.deployer instanceof LedgerAccount) {
            console.log("Connecting to ledger...");
            const transport = await TransportNodeHid.create();
            signer = new LedgerSigner(transport);
        }
        else if (this.networkConfig.accounts.deployer instanceof PrivateKeyAccount) {
            signer = await InMemorySigner.fromSecretKey(this.networkConfig.accounts.deployer.private_key);
        }
        else throw new Error("Unhandled account type");

        this.tezos = new TezosToolkit(this.networkConfig.url);
        this.tezos.setProvider({ signer: signer });

        this.accountAddress = await signer.publicKeyHash();
    }

    public async getAccountPubkey(account_name: string): Promise<string> {
        const account = this.networkConfig.accounts[account_name];
        if (account instanceof PrivateKeyAccount) {
            const signer = await InMemorySigner.fromSecretKey(account.private_key);
            return signer.publicKey();
        }

        throw new Error(`Account ${account_name} not defined`);
    }

    /**
     * TODO: add operations done to deployments file, like "added allowed places"?
     */
    /*public addDeployOperation*/

    public copyAndReadCode(contract_name: string) {
        const contractFile = `${contract_name}.json`;
        const storageFile = `${contract_name}_storage.json`;

        const codePath = `./build/${contractFile}`;
        const initPath = `./build/${storageFile}`;

        fs.copyFileSync(codePath, `${this.deploymentsDir}/${contractFile}`);
        fs.copyFileSync(initPath, `${this.deploymentsDir}/${storageFile}`);

        //const codeTz = fs.readFileSync(codePath, { encoding: 'utf-8' });
        const codeJson = JSON.parse(fs.readFileSync(codePath, { encoding: 'utf-8' }));
        const initJson = JSON.parse(fs.readFileSync(initPath, { encoding: 'utf-8' }));

        return { codeJson, initJson };
    }

    // Compiles metadata, uploads it and then compiles again with metadata set.
    // Note: target_args needs to exclude metadata.
    protected async compile_contract(target_name: string, file_name: string, contract_name: string, target_args: string[], metadata?: ipfs.ContractMetadata) {
        var metadata_url;
        if (metadata === undefined) {
            // Compile metadata
            smartpy.compile_metadata(target_name, file_name, contract_name, target_args.concat(['metadata = sp.utils.metadata_of_url("metadata_dummy")']));

            const metadtaFile = `${target_name}_metadata.json`;
            const metadtaPath = `./build/${metadtaFile}`;
            const contract_metadata = JSON.parse(fs.readFileSync(metadtaPath, { encoding: 'utf-8' }));

            metadata_url = await ipfs.upload_metadata(contract_metadata, this.isSandboxNet);
        }
        else {
            metadata_url = await ipfs.upload_contract_metadata(metadata, this.isSandboxNet);
        }

        // Compile contract with metadata set.
        smartpy.compile_newtarget(target_name, file_name, contract_name, target_args.concat([`metadata = sp.utils.metadata_of_url("${metadata_url}")`]));
    }

    protected async deploy_contract(contract_name: string): Promise<ContractAbstraction<Wallet>> {
        assert(this.tezos);

        // Check if deployment is in project.deployments.json
        // if yes, skip.
        const existingDeployment = this.deploymentsReg.getContract(contract_name);
        if(existingDeployment) {
            console.log(`>> Using existing deployment for '${contract_name}': ${existingDeployment}\n`);
            return this.tezos.wallet.at(existingDeployment);
        }

        const { codeJson, initJson } = this.copyAndReadCode(contract_name);

        const orig_op = await this.tezos.contract.originate({
            code: codeJson,
            init: initJson,
        });

        await orig_op.confirmation();
        const contract_address = orig_op.contractAddress;
        assert(contract_address);

        // Write deployment (name, address) to project.deployments.json
        this.deploymentsReg.addContract(contract_name, contract_address);

        console.log(`Successfully deployed contract ${contract_name}`);
        console.log(`>> Transaction hash: ${orig_op.hash}`);
        console.log(`>> Contract address: ${contract_address}\n`);

        return this.tezos.wallet.at(contract_address);
    };

    protected async feesToObject(op: TransactionWalletOperation|BatchWalletOperation): Promise<FeeResult> {
        const receipt = await op.receipt();
        //console.log("totalFee", receipt.totalFee.toNumber());
        //console.log("totalGas", receipt.totalGas.toNumber());
        //console.log("totalStorage", receipt.totalStorage.toNumber());
        //console.log("totalAllocationBurn", receipt.totalAllocationBurn.toNumber());
        //console.log("totalOriginationBurn", receipt.totalOriginationBurn.toNumber());
        //console.log("totalPaidStorageDiff", receipt.totalPaidStorageDiff.toNumber());
        //console.log("totalStorageBurn", receipt.totalStorageBurn.toNumber());
        // TODO: figure out how to actually calculate burn.
        const paidStorage = receipt.totalPaidStorageDiff.toNumber() * 250 / 1000000;
        const totalFee = receipt.totalFee.toNumber() / 1000000;
        //const totalGas = receipt.totalGas.toNumber() / 1000000;
        //return `${(totalFee + paidStorage).toFixed(6)} (storage: ${paidStorage.toFixed(6)}, gas: ${totalFee.toFixed(6)})`;
        return { storage: paidStorage.toFixed(6), fee: totalFee.toFixed(6) };
    }

    protected async feesToString(op: TransactionWalletOperation|BatchWalletOperation): Promise<string> {
        const res = await this.feesToObject(op);
        return `storage: ${res.storage}, gas: ${res.fee}`;
    }

    protected async run_op_task(
        task_name: string,
        f: () => Promise<TransactionWalletOperation | BatchWalletOperation>,
        print_fees: boolean = false): Promise<TransactionWalletOperation | BatchWalletOperation>
    {
        console.log(task_name);
        const operation = await f();
        await operation.confirmation();
        console.log(kleur.green(">> Done."), `Transaction hash: ${operation.opHash}\n`);
        if (print_fees) console.log(`${task_name}: ${this.feesToString(operation)}`);
        return operation;
    }

    private async confirmDeploy() {
        const properties = [
            {
                name: 'yesno',
                message: 'Are you sure? (yes/no)',
                validator: /^(?:yes|no)$/,
                warning: 'Must respond yes or no',
                default: 'no'
            }
        ];

        prompt.start();

        console.log(kleur.yellow("This will deploy new  contracts to " + this.network));
        const { yesno } = await prompt.get(properties);

        if (yesno === "no") throw new Error("Deploy cancelled");
    }

    private prepare() {
        // If sandbox, delete deployments dir
        if(this.isSandboxNet && this.cleanDeploymentsInSandbox) {
            console.log(kleur.yellow("Cleaning deployments dir."))
            if (fs.existsSync(this.deploymentsDir))
                fs.rmSync(this.deploymentsDir, { recursive: true });
        }
        
        if (!fs.existsSync(this.deploymentsDir)) fs.mkdirSync(this.deploymentsDir, { recursive: true });

        this.deploymentsReg.readFromDisk();
    }

    public async deploy(): Promise<void> {
        console.log(kleur.red(`Deploying to '${this.networkConfig.network}' on ${this.networkConfig.url} ...\n`));
        this.prepare();

        if(this.network !== config.defaultNetwork)
            await this.confirmDeploy();

        try {
            const start_time = performance.now();

            await this.initTezosToolkit();

            await this.deployDo();

            const end_time = performance.now();
            console.log(kleur.green(`Deploy ran in ${((end_time - start_time) / 1000).toFixed(1)}s`));
        } catch (error) {
            console.error(util.inspect(error, {showHidden: false, depth: null, colors: true}));
        }
    };

    protected async deployDo() {
        throw new Error("Not implemented");
    }
}