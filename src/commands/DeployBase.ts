import { TezosToolkit, ContractAbstraction, ContractProvider, WalletOperationBatch, OpKind } from "@taquito/taquito";
import { OperationContentsAndResult } from "@taquito/rpc";
import { InMemorySigner } from "@taquito/signer";
import { OperationContentsAndResultOrigination } from '@taquito/rpc';
import { performance } from 'perf_hooks';
import config from '../user.config';
import { NetworkConfig } from '../config/config';
import assert from 'assert';
import kleur from 'kleur';
import prompt from 'prompt';
import fs from 'fs';


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
        const existingDeployment = this.deploy.getDeployment(contract_name);
        this.contractList.push({name: contract_name, address: existingDeployment});
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

    private async get_originated_contracts_batch(results: OperationContentsAndResult[]): Promise<ContractAbstraction<ContractProvider>[]> {
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

            this.deploy.addDeployment(contract_name, contract_address);
        }

        console.log();

        const contracts = [];
        for (const c of this.contractList)
            contracts.push(await this.deploy.tezos.contract.at(c.address));

        return contracts;
    }
}


export default class DeployBase {

    private networkConfig: NetworkConfig;
    protected network: string;
    protected isSandboxNet: boolean;

    public tezos?: TezosToolkit;
    protected accountAddress?: string;

    private deploymentsDir: string;

    private deploymentsRegPath: string
    private deploymentsReg: any;

    constructor(options: any) {
        // set network to deploy to.
        if(!options.network) this.network = config.defaultNetwork;
        else this.network = options.network;

        this.isSandboxNet = this.network === "sandbox";

        // get and validate network config.
        this.networkConfig = config.networks[this.network];
        assert(this.networkConfig, `Network config not found for '${this.network}'`);
        assert(this.networkConfig.accounts.deployer, `deployer account not set for '${this.network}'`)

        this.deploymentsDir = `./deployments/${this.network}`;
        
        // if sandbox, delete deployments dir
        if(this.isSandboxNet) {
            if (fs.existsSync(this.deploymentsDir)) {
                fs.rmdirSync(this.deploymentsDir, { recursive: true });
                fs.mkdirSync(this.deploymentsDir, { recursive: true });
            }
        }
        else {
            if (!fs.existsSync(this.deploymentsDir)) fs.mkdirSync(this.deploymentsDir, { recursive: true });
        }

        this.deploymentsRegPath =`${this.deploymentsDir}/project.deployments.json`;
        if (fs.existsSync(this.deploymentsRegPath))
            this.deploymentsReg = JSON.parse(fs.readFileSync(this.deploymentsRegPath, { encoding: 'utf-8' }));
        else this.deploymentsReg = {};
    }

    private async initTezosToolkit() {
        const signer = await InMemorySigner.fromSecretKey(this.networkConfig.accounts.deployer);
        this.tezos = new TezosToolkit(this.networkConfig.url);
        this.tezos.setProvider({ signer: signer });

        this.accountAddress = await signer.publicKeyHash();
    }

    public getDeployment(contract_name: string): string {
        if(this.deploymentsReg[contract_name] && this.deploymentsReg[contract_name].contract) {
            return this.deploymentsReg[contract_name].contract;
        }
        return '';
    }

    public addDeployment(contract_name: string, address: string) {
        this.deploymentsReg[contract_name] = { contract: address };
    }

    public copyAndReadCode(contract_name: string) {
        const contractFile = `${contract_name}.json`;
        const storageFile = `${contract_name}_storage.json`;

        const codePath = `./build/${contractFile}`;
        const initPath = `./build/${storageFile}`;

        fs.copyFileSync(codePath, `${this.deploymentsDir}/${contractFile}`);
        fs.copyFileSync(initPath, `${this.deploymentsDir}/${storageFile}`);

        const codeJson = JSON.parse(fs.readFileSync(codePath, { encoding: 'utf-8' }));
        const initJson = JSON.parse(fs.readFileSync(initPath, { encoding: 'utf-8' }));

        return { codeJson, initJson };
    }

    protected async deploy_contract(contract_name: string): Promise<ContractAbstraction<ContractProvider>> {
        assert(this.tezos);

        // Check if deployment is in project.deployments.json
        // if yes, skip.
        const existingDeployment = this.getDeployment(contract_name);
        if(existingDeployment) {
            console.log(`>> Using existing deployment for '${contract_name}': ${existingDeployment}\n`);
            return this.tezos.contract.at(existingDeployment);
        }

        const { codeJson, initJson } = this.copyAndReadCode(contract_name);

        var orig_op = await this.tezos.contract.originate({
            code: codeJson,
            init: initJson,
        });

        var contract = await orig_op.contract();

        // Write deployment (name, address) to project.deployments.json
        this.addDeployment(contract_name, contract.address);

        console.log(`Successfully deployed contract ${contract_name}`);
        console.log(`>> Transaction hash: ${orig_op.hash}`);
        console.log(`>> Contract address: ${contract.address}\n`);

        return contract;
    };

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

    public async deploy(): Promise<void> {
        console.log(kleur.red(`Deploying to '${this.networkConfig.network}' on ${this.networkConfig.url} ...\n`));

        if(this.network !== config.defaultNetwork)
            await this.confirmDeploy();

        try {
            const start_time = performance.now();

            await this.initTezosToolkit();

            await this.deployDo();

            const end_time = performance.now();
            console.log(kleur.green(`Deploy ran in ${((end_time - start_time) / 1000).toFixed(1)}s`));
        } catch (error) {
            console.error(error);
        }

        // Write deployment file.
        fs.writeFileSync(this.deploymentsRegPath, JSON.stringify(this.deploymentsReg), { encoding: 'utf-8' })
    };

    protected async deployDo() {
        throw new Error("Not implemented");
    }
}