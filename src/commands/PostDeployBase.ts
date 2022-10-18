import kleur from "kleur";
import { ContractAbstraction, TransactionWalletOperation, Wallet } from "@taquito/taquito";
import { BatchWalletOperation } from "@taquito/taquito/dist/types/wallet/batch-operation";
import { DeployMode } from "../config/config";
import DeployBase from "./DeployBase";
import config from "../user.config";


export type PostDeployContracts = Map<string, ContractAbstraction<Wallet>>;


export default class PostDeployBase extends DeployBase {
    public async runPostDeploy(contracts: PostDeployContracts) {
        // If this is a sandbox deploy, run the post deploy tasks.
        const deploy_mode = this.isSandboxNet ? config.sandbox.deployMode : DeployMode.None;

        console.log(kleur.magenta("Running post deploy tasks...\n"));
        switch (deploy_mode) {
            case DeployMode.DevWorld:
                await this.deployDevWorld(contracts);
                break;
            case DeployMode.GasTest:
                await this.gasTestSuite(contracts);
                break;
            case DeployMode.StressTestSingle:
                await this.stressTestSingle(contracts);
                break;
            case DeployMode.StressTestMulti:
                await this.stressTestMulti(contracts);
                break;
        }
    
        if (deploy_mode === DeployMode.None || deploy_mode === DeployMode.DevWorld) {
            this.printContracts(contracts);
        }
    }
    
    protected printContracts(contracts: PostDeployContracts) {
        throw new Error("Method not implemented.");
    }

    protected async deployDevWorld(contracts: PostDeployContracts) {
        throw new Error("Method not implemented.");
    }

    protected async gasTestSuite(contracts: PostDeployContracts) {
        throw new Error("Method not implemented.");
    }

    protected async stressTestSingle(contracts: PostDeployContracts) {
        throw new Error("Method not implemented.");
    }

    protected async stressTestMulti(contracts: PostDeployContracts) {
        throw new Error("Method not implemented.");
    }

    protected async feesToString(op: TransactionWalletOperation|BatchWalletOperation): Promise<string> {
        const receipt = await op.receipt();
        //console.log("totalFee", receipt.totalFee.toNumber());
        //console.log("totalGas", receipt.totalGas.toNumber());
        //console.log("totalStorage", receipt.totalStorage.toNumber());
        //console.log("totalAllocationBurn", receipt.totalAllocationBurn.toNumber());
        //console.log("totalOriginationBurn", receipt.totalOriginationBurn.toNumber());
        //console.log("totalPaidStorageDiff", receipt.totalPaidStorageDiff.toNumber());
        //console.log("totalStorageBurn", receipt.totalStorageBurn.toNumber());
        // TODO: figure out how to actually calculate burn.
        const paidStorage = receipt.totalPaidStorageDiff.toNumber() * 100 / 1000000;
        const totalFee = receipt.totalFee.toNumber() / 1000000;
        //const totalGas = receipt.totalGas.toNumber() / 1000000;
        //return `${(totalFee + paidStorage).toFixed(6)} (storage: ${paidStorage.toFixed(6)}, gas: ${totalFee.toFixed(6)})`;
        return `storage: ${paidStorage.toFixed(6)}, gas: ${totalFee.toFixed(6)}`;
    }
}