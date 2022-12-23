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
import path from "path";


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

    public async addToBatch(target_name: string, file_name: string, contract_name: string, target_args: string[], has_metadata: boolean = true) {
        assert(this.deploy.tezos);

        // Check if deployment is in project.deployments.json
        // if yes, skip.
        const existingDeployment = this.deploy.deploymentsReg.getContract(target_name);
        this.contractList.push({name: target_name, address: existingDeployment ? existingDeployment : ''});
        if(existingDeployment) {
            console.log(`>> Using existing deployment for '${target_name}': ${existingDeployment}\n`);
            return;
        }

        const [code, storage] = await this.deploy.compile_contract(target_name, file_name, contract_name, target_args, has_metadata);

        this.batch.withOrigination({
            code: code,
            init: storage,
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
        const contracts = this.get_originated_contracts_batch(results);
        console.log();

        return contracts;
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

    readonly deploymentsDir: string;

    readonly deploymentsReg: DeploymentsRegistry;

    public getNetwork(): string { return this.network; }
    public isSandboxNetwork(): boolean { return this.isSandboxNet; }

    constructor(options: any, is_upgrade: boolean = false) {
        // set network to deploy to.
        if(!options.network) this.network = config.defaultNetwork;
        else this.network = options.network;

        this.isSandboxNet = this.network === "sandbox";
        this.cleanDeploymentsInSandbox = !is_upgrade;

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

    private copyToDeploymentsAndReadCode(code_path: string, storage_path: string) {
        const code_file = path.basename(code_path);
        const storage_file = path.basename(storage_path);

        fs.copyFileSync(code_path, `${this.deploymentsDir}/${code_file}`);
        fs.copyFileSync(storage_path, `${this.deploymentsDir}/${storage_file}`);

        //const codeTz = fs.readFileSync(codePath, { encoding: 'utf-8' });
        const code_parsed = JSON.parse(fs.readFileSync(code_path, { encoding: 'utf-8' }));
        const storage_parsed = JSON.parse(fs.readFileSync(storage_path, { encoding: 'utf-8' }));

        return [code_parsed, storage_parsed];
    }

    // Compiles only metadata and uploads it.
    // Note: target_args needs to exclude metadata.
    // Returns metadata uri.
    public async compile_metadata(target_name: string, file_name: string, contract_name: string, target_args: string[]) {
        console.log(kleur.yellow(`Metadata target '${target_name}'`), `(${file_name}::${contract_name})`);

        // Build artifact directory.
        const target_out_dir = `./build/${target_name}`

        // Remove previous build output.
        if (fs.existsSync(target_out_dir)) fs.rmdirSync(target_out_dir, { recursive: true });

        // Make create the build output dir.
        fs.mkdirSync(target_out_dir, { recursive: true });

        // Compile metadata
        const metadata_path = smartpy.compile_metadata_substep(target_out_dir, target_name, file_name, contract_name, target_args.concat(['metadata = sp.utils.metadata_of_url("metadata_dummy")']));

        // Upload metadata
        const contract_metadata = JSON.parse(fs.readFileSync(metadata_path, { encoding: 'utf-8' }));
        const metadata_url = await ipfs.upload_metadata(contract_metadata, this.isSandboxNet);

        console.log()

        return metadata_url;
    }

    // Compiles metadata, uploads it and then compiles again with metadata set.
    // Note: target_args needs to exclude metadata.
    // Returns parsed code and storage.
    public async compile_contract(target_name: string, file_name: string, contract_name: string, target_args: string[], has_metadata: boolean = true) {
        console.log(kleur.yellow(`Compile target '${target_name}'`), `(${file_name}::${contract_name})`);

        // Build artifact directory.
        const target_out_dir = `./build/${target_name}`

        // Remove previous build output.
        if (fs.existsSync(target_out_dir)) fs.rmdirSync(target_out_dir, { recursive: true });

        // Make create the build output dir.
        fs.mkdirSync(target_out_dir, { recursive: true });

        let used_target_args = target_args;

        if (has_metadata) {
            // Compile metadata
            const metadata_path = smartpy.compile_metadata_substep(target_out_dir, target_name, file_name, contract_name, target_args.concat(['metadata = sp.utils.metadata_of_url("metadata_dummy")']));

            // Upload metadata
            const contract_metadata = JSON.parse(fs.readFileSync(metadata_path, { encoding: 'utf-8' }));
            const metadata_url = await ipfs.upload_metadata(contract_metadata, this.isSandboxNet);

            // Add metadata url to target args.
            used_target_args = target_args.concat([`metadata = sp.utils.metadata_of_url("${metadata_url}")`])
        }

        // Compile contract.
        const [code_path, storage_path] = smartpy.compile_code_substep(target_out_dir, target_name, file_name, contract_name, used_target_args);

        console.log()

        return this.copyToDeploymentsAndReadCode(code_path, storage_path);
    }

    // Compiles contract, extracts lazy entrypoint code and deploys the updates.
    // Note: target_args needs to exclude metadata.
    // Returns path of uploaded metadata.
    // TODO: copy compiled entrypoints output to deployments dir
    protected async upgrade_entrypoint(contract: ContractAbstraction<Wallet>, target_name: string, file_name: string, contract_name: string,
        target_args: string[], entrypoints: string[], has_metadata: boolean = true, upload_new_metadata: boolean = true): Promise<string | undefined>
    {
        console.log(kleur.yellow(`Upgrade target '${target_name}'`), `(${file_name}::${contract_name})`);

        // Build artifact directory.
        const target_out_dir = `./build/${target_name}`

        const used_target_args = has_metadata ? target_args.concat(['metadata = sp.utils.metadata_of_url("metadata_dummy")']) : target_args;

        // Compile contract with metadata set.
        const [code_map, metadata_path] = smartpy.compile_upgrade(target_out_dir, target_name, file_name, contract_name, used_target_args, entrypoints);

        await this.run_op_task(`Updating entrypoints [${kleur.yellow(entrypoints.join(', '))}]...`, async () => {
            let upgrade_batch = this.tezos!.wallet.batch();
            for (const ep_name of entrypoints) {
                upgrade_batch.with([
                    {
                        kind: OpKind.TRANSACTION,
                        ...contract.methodsObject.update_ep({
                            ep_name: {[ep_name]: null},
                            new_code: JSON.parse(fs.readFileSync(code_map.get(ep_name)!, "utf-8"))
                        }).toTransferParams()
                    }
                ]);
            }
            return upgrade_batch.send();
        });

        let metdata_url;
        if (has_metadata && upload_new_metadata) {
            const contract_metadata = JSON.parse(fs.readFileSync(metadata_path, { encoding: 'utf-8' }));
            metdata_url = await ipfs.upload_metadata(contract_metadata, this.isSandboxNet);
        }

        console.log();

        return metdata_url;
    }

    protected async deploy_contract(target_name: string, file_name: string, contract_name: string, target_args: string[], has_metadata: boolean = true): Promise<ContractAbstraction<Wallet>> {
        assert(this.tezos);

        // Check if deployment is in project.deployments.json
        // if yes, skip.
        const existingDeployment = this.deploymentsReg.getContract(target_name);
        if(existingDeployment) {
            console.log(`>> Using existing deployment for '${target_name}': ${existingDeployment}\n`);
            return this.tezos.wallet.at(existingDeployment);
        }

        const [code, storage] = await this.compile_contract(target_name, file_name, contract_name, target_args, has_metadata);

        const orig_op = await this.tezos.contract.originate({
            code: code,
            init: storage,
        });

        await orig_op.confirmation();
        const contract_address = orig_op.contractAddress;
        assert(contract_address);

        // Write deployment (name, address) to project.deployments.json
        this.deploymentsReg.addContract(target_name, contract_address);

        console.log(`Successfully deployed contract ${target_name}`);
        console.log(`>> Transaction hash: ${orig_op.hash}`);
        console.log(`>> Contract address: ${contract_address}\n`);

        return this.tezos.wallet.at(contract_address);
    };

    protected async feesToObject(op: TransactionWalletOperation|BatchWalletOperation): Promise<FeeResult> {
        const receipt = await op.receipt();
        // totalStorageBurn is paid storage diff + allocation burn + origination burn
        const paidStorage = receipt.totalStorageBurn.toNumber() / 1000000;
        const totalFee = receipt.totalFee.toNumber() / 1000000;
        return { storage: paidStorage.toFixed(6), fee: totalFee.toFixed(6) };
    }

    protected async feesToString(op: TransactionWalletOperation|BatchWalletOperation): Promise<string> {
        const res = await this.feesToObject(op);
        return `storage: ${res.storage}, gas: ${res.fee}`;
    }

    protected async run_flag_task(flag: string, task: () => Promise<void>) {
        if (!this.deploymentsReg.getFlag(flag)) {
            await task();
            this.deploymentsReg.addFlag(flag, true);
        }
        else console.log(`Task "${flag}" already done.\n`);
    }

    protected async run_op_task(
        task_name: string,
        task: () => Promise<TransactionWalletOperation | BatchWalletOperation>,
        print_fees: boolean = false): Promise<TransactionWalletOperation | BatchWalletOperation>
    {
        console.log(task_name);
        const operation = await task();
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