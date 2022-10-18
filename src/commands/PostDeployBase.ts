import kleur from "kleur";
import { ContractAbstraction, Wallet } from "@taquito/taquito";
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
}