import { OpKind } from "@taquito/taquito";
import assert from "assert";
import kleur from "kleur";
import PostDeployBase, { GasResultsTable, PostDeployContracts } from "../commands/PostDeployBase";


export default class MarketplacePostDeploy extends PostDeployBase {
    // TODO: should really use the deployments registry!
    protected override printContracts(contracts: PostDeployContracts): void {
        console.log("VITE_MARKETPLACE_CONTRACT=" + contracts.get("Marketplace_contract")!.address);
        console.log()
        console.log(`contracts:
  tezlandMarketplace:
    address: ${contracts.get("Marketplace_contract")!.address}
    typename: tezlandMarketplace\n`);
    }

    protected override async gasTestSuite(contracts: PostDeployContracts) {
        const gas_results_tables: GasResultsTable[] = [];

        console.log(kleur.bgGreen("Running gas test suite"));

        const swapCollectCancel = async (row_name: string, token_id: number, swap_id: number) => {
            let gas_results = this.addGasResultsTable(gas_results_tables, { name: row_name, rows: {} });

            // place one item
            await this.runTaskAndAddGasResults(gas_results, "swap items", () => {
                assert(this.tezos)
                const batch = this.tezos.wallet.batch()

                batch.with([{
                        kind: OpKind.TRANSACTION,
                        ...contracts.get("items_v2_FA2_contract")!.methodsObject.update_adhoc_operators({ add_adhoc_operators: [{
                            operator: contracts.get("Marketplace_contract")!.address,
                            token_id: token_id
                        }] }).toTransferParams()
                    },
                    {
                        kind: OpKind.TRANSACTION,
                        ...contracts.get("Marketplace_contract")!.methodsObject.swap({
                            swap_key_partial: {
                                fa2: contracts.get("items_v2_FA2_contract")!.address,
                                token_id: token_id,
                                price: 12345678,
                                primary: false
                            },
                            token_amount: 2,
                        }).toTransferParams()
                    }
                ]);

                return batch.send();
            });

            // collect one item
            await this.runTaskAndAddGasResults(gas_results, "collect item", () => {
                return contracts.get("Marketplace_contract")!.methodsObject.collect({
                    swap_key: {
                        id: swap_id,
                        owner: this.accountAddress!,
                        partial: {
                            fa2: contracts.get("items_v2_FA2_contract")!.address,
                            token_id: token_id,
                            price: 12345678,
                            primary: false
                        }
                    }
                }).send({amount: 12345678, mutez: true});
            });

            // collect one item
            await this.runTaskAndAddGasResults(gas_results, "cancel swap", () => {
                return contracts.get("Marketplace_contract")!.methodsObject.cancel({
                    swap_key: {
                        id: swap_id,
                        owner: this.accountAddress!,
                        partial: {
                            fa2: contracts.get("items_v2_FA2_contract")!.address,
                            token_id: token_id,
                            price: 12345678,
                            primary: false
                        }
                    }
                }).send();
            });
        } 

        await swapCollectCancel("swap & collect once", 0, 0);

        await swapCollectCancel("swap & collect again", 0, 1);

        this.printGasResults(gas_results_tables);
    }
}