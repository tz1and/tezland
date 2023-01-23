import { OpKind } from "@taquito/taquito";
import assert from "assert";
import kleur from "kleur";
import PostDeployBase, { GasResultsTable, PostDeployContracts } from "../commands/PostDeployBase";
import BigNumber from 'bignumber.js';


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

        const Marketplace_contract = contracts.get("Marketplace_contract")!;

        const marketplace_storage = await Marketplace_contract.storage() as any;
        let next_swap_id: BigNumber = marketplace_storage.next_swap_id;

        const swapCollect = async (row_name: string, token_id: number, swap_id: BigNumber) => {
            let gas_results = this.addGasResultsTable(gas_results_tables, { name: row_name, rows: {} });

            // place one item
            await this.runTaskAndAddGasResults(gas_results, "swap items", () => {
                assert(this.tezos)
                const batch = this.tezos.wallet.batch()

                batch.with([{
                        kind: OpKind.TRANSACTION,
                        ...contracts.get("items_v2_FA2_contract")!.methodsObject.update_adhoc_operators({ add_adhoc_operators: [{
                            operator: Marketplace_contract.address,
                            token_id: token_id
                        }] }).toTransferParams()
                    },
                    {
                        kind: OpKind.TRANSACTION,
                        ...Marketplace_contract.methodsObject.swap({
                            swap_key_partial: {
                                fa2: contracts.get("items_v2_FA2_contract")!.address,
                                token_id: token_id,
                                rate: 12345678,
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
                return Marketplace_contract.methodsObject.collect({
                    swap_key: {
                        id: swap_id,
                        owner: this.accountAddress!,
                        partial: {
                            fa2: contracts.get("items_v2_FA2_contract")!.address,
                            token_id: token_id,
                            rate: 12345678,
                            primary: false
                        }
                    }
                }).send({amount: 12345678, mutez: true});
            });

            return gas_results;
        }

        const swapCollectCancel = async (row_name: string, token_id: number, swap_id: BigNumber) => {
            const gas_results = await swapCollect(row_name, token_id, swap_id);

            // collect one item
            await this.runTaskAndAddGasResults(gas_results, "cancel swap", () => {
                return Marketplace_contract.methodsObject.cancel({
                    swap_key: {
                        id: swap_id,
                        owner: this.accountAddress!,
                        partial: {
                            fa2: contracts.get("items_v2_FA2_contract")!.address,
                            token_id: token_id,
                            rate: 12345678,
                            primary: false
                        }
                    }
                }).send();
            });
        }

        await swapCollectCancel("swap, collect & cancel once", 0, next_swap_id);

        next_swap_id = next_swap_id.plus(1)
        await swapCollectCancel("swap, collect & cancel again", 0, next_swap_id);

        next_swap_id = next_swap_id.plus(1)
        await swapCollect("swap & collect once", 0, next_swap_id);

        next_swap_id = next_swap_id.plus(1)
        await swapCollect("swap & collect again", 0, next_swap_id);

        next_swap_id = next_swap_id.plus(1)
        await swapCollect("swap & collect again", 1, next_swap_id);

        this.printGasResults(gas_results_tables);
    }
}