import kleur from "kleur";
import { ContractAbstraction, OpKind, Wallet } from "@taquito/taquito";
import { DeployMode } from "../config/config";
import DeployBase from "./DeployBase";


export type PostDeployContracts = Map<string, ContractAbstraction<Wallet>>;


export default class PostDeployBase extends DeployBase {
    public async runPostDeploy(deploy_mode: DeployMode, contracts: PostDeployContracts) {
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

    // Utils
    // TODO: should properly batch the operator adds per contact
    protected async fa2_add_operators(contracts: PostDeployContracts, operators: Map<string, Map<string, number[]>>) {
        return this.run_op_task("Adding operators", () => {
            let batch = this.tezos!.wallet.batch();

            for (const [token_contract, token_map] of operators) {
                let contract = contracts.get(token_contract)!;
                for (const [to_contract, token_ids] of token_map) {
                    for (const token_id of token_ids) {
                        batch.with([{
                            kind: OpKind.TRANSACTION,
                            ...contract.methods.update_operators([{
                                add_operator: {
                                    owner: this.accountAddress,
                                    operator: contracts.get(to_contract)!.address,
                                    token_id: token_id
                                }
                            }]).toTransferParams()
                        }])
                    }
                }
            }

            return batch.send()
        });
    }

    // TODO: should properly batch the operator removes per contact
    protected async fa2_remove_operators(contracts: PostDeployContracts, operators: Map<string, Map<string, number[]>>) {
        return this.run_op_task("Removing operators", () => {
            let batch = this.tezos!.wallet.batch();

            for (const [token_contract, token_map] of operators) {
                let contract = contracts.get(token_contract)!;
                for (const [to_contract, token_ids] of token_map) {
                    for (const token_id of token_ids) {
                        batch.with([{
                            kind: OpKind.TRANSACTION,
                            ...contract.methods.update_operators([{
                                remove_operator: {
                                    owner: this.accountAddress,
                                    operator: contracts.get(to_contract)!.address,
                                    token_id: token_id
                                }
                            }]).toTransferParams()
                        }])
                    }
                }
            }

            return batch.send()
        });
    }
}