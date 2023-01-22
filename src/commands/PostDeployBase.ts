import kleur from "kleur";
import { ContractAbstraction, OpKind, TransactionWalletOperation, Wallet } from "@taquito/taquito";
import { DeployMode } from "../config/config";
import DeployBase from "./DeployBase";
import { BatchWalletOperation } from "@taquito/taquito/dist/types/wallet/batch-operation";


export type PostDeployContracts = Map<string, ContractAbstraction<Wallet>>;

/**
 * Some types and functions for gas tests and resutls
 */
type GasResultRow = {
    storage: string;
    fee: string;
}

type GasResultsRows = {
    [id: string]: GasResultRow | undefined;
}

export type GasResultsTable = {
    name: string;
    rows: GasResultsRows;
}


export default abstract class PostDeployBase extends DeployBase {
    public async runPostDeploy(deploy_mode: DeployMode, contracts: PostDeployContracts) {
        console.log(kleur.magenta("Running post deploy tasks...\n"));

        try {
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
        }
        catch(e: any) {
            console.log(`PostDeply failed for mode '${deploy_mode}':`, e.message);
        }
    
        if (deploy_mode === DeployMode.None || deploy_mode === DeployMode.DevWorld) {
            console.log()
            this.printContracts(contracts);
        }
    }
    
    protected abstract printContracts(contracts: PostDeployContracts): void;

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

    // Gas results
    protected addGasResultsTable(gas_results_tables: GasResultsTable[], table: GasResultsTable): GasResultsTable {
        gas_results_tables.push(table);
        return table;
    }
    
    protected async runTaskAndAddGasResults(
        gas_results: GasResultsTable,
        task_name: string,
        f: () => Promise<TransactionWalletOperation | BatchWalletOperation>) {
        try {
            const op = await this.run_op_task(task_name, f);
            gas_results.rows[task_name] = await this.feesToObject(op);
        } catch(error) {
            console.log(kleur.red(">> Failed:\n"));
            console.dir(error, {depth: null});
            console.log();
            gas_results.rows[task_name] = undefined;
        }
    }

    protected printGasResults(gas_results_tables: GasResultsTable[]) {
        for (const table of gas_results_tables) {
            console.log();
            console.log(kleur.blue(table.name));
            for (const row_key of Object.keys(table.rows)) {
                const row = table.rows[row_key];
                if(row)
                    console.log(`${(row_key + ":").padEnd(32)}storage: ${row.storage}, gas: ${row.fee}`);
                else
                    console.log(`${(row_key + ":").padEnd(32)}` + kleur.red("failed!"));
            }
            //console.table(table.rows);
        }
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

    protected override async deployDo(): Promise<void> {
        // Nothing to do, is PostDeployBase
    }
}