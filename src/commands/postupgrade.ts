import assert from "assert";
import PostDeployBase, { PostDeployContracts } from "./PostDeployBase";
import * as ipfs from '../ipfs'
import { ContractAbstraction, ContractMethodObject, MichelCodecPacker, MichelsonMap, OpKind, TransactionWalletOperation, Wallet, WalletOperationBatch } from "@taquito/taquito";
import { BatchWalletOperation } from "@taquito/taquito/dist/types/wallet/batch-operation";
import { OperationContentsAndResultTransaction, OperationResultOrigination, MichelsonV1Expression } from '@taquito/rpc';
import { Schema } from '@taquito/michelson-encoder';
import { char2Bytes } from '@taquito/utils'
import kleur from "kleur";
import config from "../user.config";
import { sleep } from "./DeployBase";
import { SHA3 } from 'sha3';
import WorldUtils from "./WorldUtils";


export default class PostUpgrade extends PostDeployBase {
    protected printContracts(contracts: PostDeployContracts) {
        console.log("REACT_APP_ITEM_CONTRACT=" + contracts.get("items_v2_FA2_contract")!.address);
        console.log("REACT_APP_PLACE_CONTRACT=" + contracts.get("places_v2_FA2_contract")!.address);
        console.log("REACT_APP_INTERIOR_CONTRACT=" + contracts.get("interiors_FA2_contract")!.address);
        console.log("REACT_APP_DAO_CONTRACT=" + contracts.get("dao_FA2_contract")!.address);
        console.log("REACT_APP_WORLD_CONTRACT=" + contracts.get("World_v2_contract")!.address);
        console.log("REACT_APP_MINTER_CONTRACT=" + contracts.get("Minter_v2_contract")!.address);
        console.log("REACT_APP_DUTCH_AUCTION_CONTRACT=" + contracts.get("Dutch_v2_contract")!.address);
        console.log("REACT_APP_FACTORY_CONTRACT=" + contracts.get("Factory_contract")!.address);
        console.log("REACT_APP_REGISTRY_CONTRACT=" + contracts.get("Registry_contract")!.address);
        console.log()
        console.log(`contracts:
  tezlandItems:
    address: ${contracts.get("items_FA2_contract")!.address}
    typename: tezlandFA2Fungible

  tezlandItemsV2:
    address: ${contracts.get("items_v2_FA2_contract")!.address}
    typename: tezlandFA2FungibleV2

  tezlandPlaces:
    address: ${contracts.get("places_FA2_contract")!.address}
    typename: tezlandFA2NFT

  tezlandPlacesV2:
    address: ${contracts.get("places_v2_FA2_contract")!.address}
    typename: tezlandFA2NFTV2

  tezlandInteriors:
    address: ${contracts.get("interiors_FA2_contract")!.address}
    typename: tezlandFA2NFTV2

  tezlandDAO:
    address: ${contracts.get("dao_FA2_contract")!.address}
    typename: tezlandDAO

  tezlandWorld:
    address: ${contracts.get("World_contract")!.address}
    typename: tezlandWorld

  tezlandWorldV2:
    address: ${contracts.get("World_v2_contract")!.address}
    typename: tezlandWorldV2
    
  tezlandMinter:
    address: ${contracts.get("Minter_contract")!.address}
    typename: tezlandMinter

  tezlandMinterV2:
    address: ${contracts.get("Minter_v2_contract")!.address}
    typename: tezlandMinterV2

  tezlandDutchAuctions:
    address: ${contracts.get("Dutch_contract")!.address}
    typename: tezlandDutchAuctions

  tezlandDutchAuctionsV2:
    address: ${contracts.get("Dutch_v2_contract")!.address}
    typename: tezlandDutchAuctionsV2
    
  tezlandFactory:
    address: ${contracts.get("Factory_contract")!.address}
    typename: tezlandFactory
    
  tezlandRegistry:
    address: ${contracts.get("Registry_contract")!.address}
    typename: tezlandRegistry\n`);
    }

    private async mintNewItem_legacy(model_path: string, polygonCount: number, amount: number, batch: WalletOperationBatch, Minter_contract: ContractAbstraction<Wallet>, collection_contract: ContractAbstraction<Wallet>) {
        assert(this.accountAddress);

        // Create item metadata and upload it
        const item_metadata_url = await ipfs.upload_item_metadata(Minter_contract.address, model_path, polygonCount, this.isSandboxNet);
        console.log(`item token metadata: ${item_metadata_url}`);

        const contributors = [
            { address: this.accountAddress, relative_royalties: 1000, role: {minter: null} }
        ];

        batch.with([{
            kind: OpKind.TRANSACTION,
            ...collection_contract.methodsObject.mint([{
                to_: this.accountAddress,
                amount: amount,
                token: {
                    new: {
                        metadata: { "": char2Bytes(item_metadata_url) },
                        royalties: {
                            royalties: 250,
                            contributors: contributors
                        }
                    }
                },
            }]).toTransferParams()
        }]);
    }

    private async mintNewItem_public(model_path: string, polygonCount: number, amount: number, batch: WalletOperationBatch, Minter_contract: ContractAbstraction<Wallet>, collection_contract: ContractAbstraction<Wallet>) {
        assert(this.accountAddress);

        // Create item metadata and upload it
        const item_metadata_url = await ipfs.upload_item_metadata(Minter_contract.address, model_path, polygonCount, this.isSandboxNet);
        console.log(`item token metadata: ${item_metadata_url}`);

        const shares = { [this.accountAddress]: 250 }

        batch.with([{
            kind: OpKind.TRANSACTION,
            ...Minter_contract.methodsObject.mint_public({
                collection: collection_contract.address,
                to_: this.accountAddress,
                amount: amount,
                royalties: shares,
                metadata: Buffer.from(item_metadata_url, 'utf8').toString('hex')
            }).toTransferParams()
        }]);
    }

    private async mintNewItem_private(model_path: string, polygonCount: number, amount: number, batch: WalletOperationBatch, Minter_contract: ContractAbstraction<Wallet>, collection_contract: ContractAbstraction<Wallet>) {
        assert(this.accountAddress);

        // Create item metadata and upload it
        const item_metadata_url = await ipfs.upload_item_metadata(Minter_contract.address, model_path, polygonCount, this.isSandboxNet);
        console.log(`item token metadata: ${item_metadata_url}`);

        const shares = { [this.accountAddress]: 250 }

        batch.with([{
            kind: OpKind.TRANSACTION,
            ...Minter_contract.methodsObject.mint_private({
                collection: collection_contract.address,
                to_: this.accountAddress,
                amount: amount,
                royalties: shares,
                metadata: Buffer.from(item_metadata_url, 'utf8').toString('hex')
            }).toTransferParams()
        }]);
    }

    // Create place metadata and upload it
    private mintNewPlaces(mint_args: any[], batch: WalletOperationBatch, places_FA2_contract: ContractAbstraction<Wallet>) {
        batch.with([{
            kind: OpKind.TRANSACTION,
            ...places_FA2_contract.methodsObject.mint(
                mint_args
            ).toTransferParams()
        }]);
    }

    private mintNewInteriorPlaces(mint_args: any[], batch: WalletOperationBatch, interiors_FA2_contract: ContractAbstraction<Wallet>) {
        batch.with([{
            kind: OpKind.TRANSACTION,
            ...interiors_FA2_contract.methodsObject.mint(
                mint_args
            ).toTransferParams()
        }]);
    }

    private async getHashedPlaceSeq(contracts: PostDeployContracts, place_key: any) {
        // Place seq type type:
        // (pair (bytes %place_seq) (map %chunk_seqs nat bytes))

        // Type as michelson expression
        const placeSeqStorageType: MichelsonV1Expression = {
            prim: 'pair',
            args: [
                { prim: 'bytes', annots: [ '%place_seq' ] },
                { prim: 'map', args: [ { prim: 'nat' }, { prim: 'bytes' } ], annots: [ '%chunk_seqs' ] }
            ]
        };

        // Get place seq.
        const place_seq = await contracts.get("World_v2_contract")!.contractViews.get_place_seqnum(
            place_key
        ).executeView({viewCaller: this.accountAddress!});

        // Encode result as a michelson expression.
        const storageSchema = new Schema(placeSeqStorageType);
        const placeSeqDataMichelson = storageSchema.Encode(place_seq);

        // Pack encoded michelson data.
        const packer = new MichelCodecPacker();
        const packedPlaceSeq = await packer.packData({ data: placeSeqDataMichelson, type: placeSeqStorageType });

        // Return hash.
        return new SHA3(256).update(packedPlaceSeq.packed, 'hex').digest('hex');
    }

    protected async deployDevWorld(contracts: PostDeployContracts) {
        console.log(kleur.bgGreen("Deploying dev world"));

        await this.run_op_task("Mint Interiors", async () => {
            const mint_batch = this.tezos!.wallet.batch();

            const places = [];
            places.push(await WorldUtils.prepareNewInteriorPlace(0, [0, 0, 0], [[20, 0, 20], [20, 0, -20], [-20, 0, -20], [-20, 0, 20]], this.accountAddress!, this.isSandboxNet, 20));
            places.push(await WorldUtils.prepareNewInteriorPlace(1, [0, 0, 0], [[40, 0, 40], [40, 0, -40], [-40, 0, -40], [-40, 0, 40]], this.accountAddress!, this.isSandboxNet, 40));
            places.push(await WorldUtils.prepareNewInteriorPlace(2, [0, 0, 0], [[80, 0, 80], [80, 0, -80], [-80, 0, -80], [-80, 0, 80]], this.accountAddress!, this.isSandboxNet, 80));
            places.push(await WorldUtils.prepareNewInteriorPlace(3, [0, 0, 0], [[160, 0, 160], [160, 0, -160], [-160, 0, -160], [-160, 0, 160]], this.accountAddress!, this.isSandboxNet, 160));
            this.mintNewInteriorPlaces(places, mint_batch, contracts.get("interiors_FA2_contract")!);

            return mint_batch.send();
        });

        // set operators
        await this.fa2_set_operators(contracts, new Map(Object.entries({
            items_FA2_contract: new Map(Object.entries({
                World_v2_contract: [0, 1, 2, 3]
            })),
            places_v2_FA2_contract: new Map(Object.entries({
                Dutch_v2_contract: [0, 1, 2, 3]
            }))
        })));

        await this.run_op_task("Place 10 items in Place #1", () => {
            const map_ten_items = new MichelsonMap<number, MichelsonMap<any, unknown>>()
            const map_ten_items_issuer = new MichelsonMap<boolean, MichelsonMap<any, unknown>>()
            map_ten_items_issuer.set(false, MichelsonMap.fromLiteral({
                [contracts.get("items_FA2_contract")!.address]: [
                    { item: { token_id: 1, amount: 1, rate: 1000000, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 2, amount: 1, rate: 1000000, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: 1000000, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 2, amount: 1, rate: 1000000, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 3, amount: 10, rate: 1000000, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: 1000000, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 1, amount: 1, rate: 0, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: 1000000, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 3, amount: 1, rate: 1000000, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 1, amount: 1, rate: 1000000, data: "01800040520000baa6c9c2460a4000", primary: false } }
                ]
            }));
            map_ten_items.set(0, map_ten_items_issuer)
            return contracts.get("World_v2_contract")!.methodsObject.place_items({
                place_key: { fa2: contracts.get("places_v2_FA2_contract")!.address, id: 1 }, place_item_map: map_ten_items
            }).send();
        });

        await this.run_op_task("Place 5 items in Place #3", () => {
            const map_five_items = new MichelsonMap<number, MichelsonMap<any, unknown>>()
            const map_five_items_issuer = new MichelsonMap<boolean, MichelsonMap<any, unknown>>()
            map_five_items_issuer.set(false, MichelsonMap.fromLiteral({
                [contracts.get("items_FA2_contract")!.address]: [
                    { item: { token_id: 0, amount: 10, rate: 1000000, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 1, amount: 1, rate: 1000000, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 2, amount: 1, rate: 0, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 3, amount: 1, rate: 1000000, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: 1000000, data: "01800040520000baa6c9c2460a4000", primary: false } }
                ]
            }));
            map_five_items.set(0, map_five_items_issuer)
            return contracts.get("World_v2_contract")!.methodsObject.place_items({
                place_key: { fa2: contracts.get("places_v2_FA2_contract")!.address, id: 3 }, place_item_map: map_five_items
            }).send();
        });

        await this.run_op_task("Update 3 items in Place #2", () => {
            const update_three_items = new MichelsonMap<number, MichelsonMap<any, unknown>>()
            const update_three_items_issuer = MichelsonMap.fromLiteral({
                [this.accountAddress!]: {
                    [contracts.get("items_FA2_contract")!.address]: [
                        { item_id: 0, data: "01800041b1be48a779c9c244023dd5"},
                        { item_id: 1, data: "01800041b1be48a779c9c244023dd5"},
                        { item_id: 3, data: "01800041b1be48a779c9c244023dd5"}
                    ]
                }
            })
            update_three_items.set(0, update_three_items_issuer)
            return contracts.get("World_v2_contract")!.methodsObject.set_item_data({
                place_key: { fa2: contracts.get("places_v2_FA2_contract")!.address, id: 2 }, update_map: update_three_items
            }).send();
        });

        await this.run_op_task("Update 5 items in Place #0", () => {
            const update_five_items = new MichelsonMap<number, MichelsonMap<any, unknown>>()
            const update_five_items_issuer = MichelsonMap.fromLiteral({
                [this.accountAddress!]: {
                    [contracts.get("items_FA2_contract")!.address]: [
                        { item_id: 2, data: "01800041b1be48a779c9c244023dd5"},
                        { item_id: 3, data: "01800041b1be48a779c9c244023dd5"},
                        { item_id: 5, data: "01800041b1be48a779c9c244023dd5"},
                        { item_id: 7, data: "01800041b1be48a779c9c244023dd5"},
                        { item_id: 8, data: "01800041b1be48a779c9c244023dd5"}
                    ]
                }
            })
            update_five_items.set(0, update_five_items_issuer)
            return contracts.get("World_v2_contract")!.methodsObject.set_item_data({
                place_key: { fa2: contracts.get("places_v2_FA2_contract")!.address, id: 0 }, update_map: update_five_items
            }).send();
        });

        await this.run_op_task("Remove 2 items in Place #1", () => {
            const remove_two_items = new MichelsonMap<number, MichelsonMap<any, unknown>>()
            const remove_two_items_issuer = MichelsonMap.fromLiteral({
                [this.accountAddress!]: {
                    [contracts.get("items_FA2_contract")!.address]: [ 2, 3 ]
                }
            })
            remove_two_items.set(0, remove_two_items_issuer)
            return contracts.get("World_v2_contract")!.methodsObject.remove_items({
                place_key: { fa2: contracts.get("places_v2_FA2_contract")!.address, id: 0 }, remove_map: remove_two_items
            }).send();
        });

        await this.run_op_task("Create auction Place #0", () => {
            let current_time = Math.floor(Date.now() / 1000) + config.sandbox.blockTime;
            return contracts.get("Dutch_v2_contract")!.methodsObject.create({
                auction_key: {
                    fa2: contracts.get("places_v2_FA2_contract")!.address,
                    token_id: 0,
                    owner: this.accountAddress
                },
                auction: {
                    start_price: 200000,
                    end_price: 100000,
                    start_time: current_time.toString(),
                    end_time: (current_time + 2000).toString()
                }
            }).send();
        });

        await this.run_op_task("Create auction Place #2", () => {
            let current_time = Math.floor(Date.now() / 1000) + config.sandbox.blockTime;
            return contracts.get("Dutch_v2_contract")!.methodsObject.create({
                auction_key: {
                    fa2: contracts.get("places_v2_FA2_contract")!.address,
                    token_id: 2,
                    owner: this.accountAddress
                },
                auction: {
                    start_price: 200000,
                    end_price: 100000,
                    start_time: current_time.toString(),
                    end_time: (current_time + 2000).toString()
                }
            }).send();
        });

        await this.run_op_task("Bid on auction Place #0", async () => {
            const chunkSeqHash = await this.getHashedPlaceSeq(contracts, {
                fa2: contracts.get("places_v2_FA2_contract")!.address, id: 0
            });

            return contracts.get("Dutch_v2_contract")!.methodsObject.bid({
                auction_key: {
                    fa2: contracts.get("places_v2_FA2_contract")!.address,
                    token_id: 0,
                    owner: this.accountAddress
                },
                seq_hash: chunkSeqHash
            }).send({amount: 200000, mutez: true});
        });

        await this.run_op_task("Cancel auction Place #2", () => {
            return contracts.get("Dutch_v2_contract")!.methodsObject.cancel({
                auction_key: {
                    fa2: contracts.get("places_v2_FA2_contract")!.address,
                    token_id: 2,
                    owner: this.accountAddress
                }
            }).send();
        });
    }

    protected async gasTestSuite(contracts: PostDeployContracts) {
        assert(this.tezos);
        //assert(this.accountAddress);

        // TODO: PostDeployContracts should be a class with a get that can throw.

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

        type GasResultsTable = {
            name: string;
            rows: GasResultsRows;
        }

        const gas_results_tables: GasResultsTable[] = [];

        const addGasResultsTable = (table: GasResultsTable): GasResultsTable => {
            gas_results_tables.push(table);
            return table;
        }

        const runTaskAndAddGasResults = async (
            gas_results: GasResultsTable,
            task_name: string,
            f: () => Promise<TransactionWalletOperation | BatchWalletOperation>) => {
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

        console.log(kleur.bgGreen("Running gas test suite"));

        {
            const mint_batch = this.tezos.wallet.batch();
            await this.mintNewItem_legacy('assets/Duck.glb', 4212, 10000, mint_batch, contracts.get("Minter_v2_contract")!, contracts.get("items_FA2_contract")!);
            await this.mintNewItem_public('assets/Duck.glb', 4212, 10000, mint_batch, contracts.get("Minter_v2_contract")!, contracts.get("items_v2_FA2_contract")!);
            // Mint some places in new place contract
            this.mintNewPlaces([await WorldUtils.prepareNewPlace(0, [0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]], this.accountAddress!, this.isSandboxNet)], mint_batch, contracts.get("places_v2_FA2_contract")!);
            this.mintNewPlaces([await WorldUtils.prepareNewPlace(1, [0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]], this.accountAddress!, this.isSandboxNet)], mint_batch, contracts.get("places_v2_FA2_contract")!);
            this.mintNewPlaces([await WorldUtils.prepareNewPlace(2, [0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]], this.accountAddress!, this.isSandboxNet)], mint_batch, contracts.get("places_v2_FA2_contract")!);
            // TODO: TEMP: FIXME: Mint some places in old place contract
            this.mintNewPlaces([await WorldUtils.prepareNewPlace(0, [0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]], this.accountAddress!, this.isSandboxNet)], mint_batch, contracts.get("places_FA2_contract")!);
            this.mintNewPlaces([await WorldUtils.prepareNewPlace(1, [0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]], this.accountAddress!, this.isSandboxNet)], mint_batch, contracts.get("places_FA2_contract")!);
            this.mintNewPlaces([await WorldUtils.prepareNewPlace(2, [0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]], this.accountAddress!, this.isSandboxNet)], mint_batch, contracts.get("places_FA2_contract")!);
            const mint_batch_op = await mint_batch.send();
            await mint_batch_op.confirmation();
        }

        let gas_results = addGasResultsTable({ name: "FA2", rows: {} });

        // set operator (v1)
        await runTaskAndAddGasResults(gas_results, "update_operators (v1)", () => {
            return contracts.get("items_FA2_contract")!.methods.update_operators([{
                add_operator: {
                    owner: this.accountAddress,
                    operator: contracts.get("World_v2_contract")!.address,
                    token_id: 0
                }
            }]).send()
        });

        // set operator (v2)
        await runTaskAndAddGasResults(gas_results, "update_operators (v2)", () => {
            return contracts.get("items_v2_FA2_contract")!.methods.update_operators([{
                add_operator: {
                    owner: this.accountAddress,
                    operator: contracts.get("World_v2_contract")!.address,
                    token_id: 0
                }
            }]).send()
        });

        const placeKey0 = { fa2: contracts.get("places_v2_FA2_contract")!.address, id: 0 };
        //const placeKey0Chunk0 = { place_key: placeKey0, chunk_id: 0 };
        const placeKey1 = { fa2: contracts.get("places_v2_FA2_contract")!.address, id: 1 };
        //const placeKey1Chunk0 = { place_key: placeKey1, chunk_id: 0 };
        const placeKey2 = { fa2: contracts.get("places_v2_FA2_contract")!.address, id: 2 };
        //const placeKey2Chunk0 = { place_key: placeKey1, chunk_id: 0 };

        const defaultRate = 1000000;

        gas_results = addGasResultsTable({ name: "World", rows: {} });

        /**
         * World
         */
        // place one item to make sure storage is set.
        let map_place_one_item: MichelsonMap<number, MichelsonMap<any, unknown>>;
        await runTaskAndAddGasResults(gas_results, "create place 0 (item)", () => {
            map_place_one_item = new MichelsonMap<number, MichelsonMap<any, unknown>>()
            const map_one_item_issuer = new MichelsonMap<boolean, MichelsonMap<any, unknown>>()
            map_one_item_issuer.set(false, MichelsonMap.fromLiteral({
                [contracts.get("items_FA2_contract")!.address]: [
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } }
                ]
            }));
            map_place_one_item.set(0, map_one_item_issuer);
            return contracts.get("World_v2_contract")!.methodsObject.place_items({
                place_key: placeKey0, place_item_map: map_place_one_item
            }).send();
        });

        // NOTE: for some reason the first created place is more expensive? some weird storage diff somewhere...
        await runTaskAndAddGasResults(gas_results, "create place 1 (item)", () => {
            return contracts.get("World_v2_contract")!.methodsObject.place_items({
                place_key: placeKey1, place_item_map: map_place_one_item
            }).send();
        });

        await runTaskAndAddGasResults(gas_results, "create place 2 (item v2)", () => {
            const map_place_one_item_v2 = new MichelsonMap<number, MichelsonMap<any, unknown>>()
            const map_one_item_issuer = new MichelsonMap<boolean, MichelsonMap<any, unknown>>()
            map_one_item_issuer.set(false, MichelsonMap.fromLiteral({
                [contracts.get("items_v2_FA2_contract")!.address]: [
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } }
                ]
            }));
            map_place_one_item_v2.set(0, map_one_item_issuer);
            return contracts.get("World_v2_contract")!.methodsObject.place_items({
                place_key: placeKey2, place_item_map: map_place_one_item_v2
            }).send();
        });

        /*{
            const transfer_op = await items_FA2_contract.methodsObject.transfer([{
                from_: this.accountAddress,
                txs: [
                    {
                        to_: World_contract.address,
                        token_id: 0,
                        amount: 1,
                    }
                ]
            }]).send();
            await transfer_op.confirmation();
        }

        // create place
        {
            const creat_op = await World_contract.methodsObject.update_place_props({ place_key: placeKey0, updates: "ffffff" }).send();
            await creat_op.confirmation();
            console.log("create place (props):\t" + await feesToString(creat_op));
        }*/

        // place props
        await runTaskAndAddGasResults(gas_results, "update_place", () => {
            const props_map = new MichelsonMap<string, string>();
            props_map.set('00', '000000');
            return contracts.get("World_v2_contract")!.methodsObject.update_place({ place_key: placeKey0, update: { props: [{add_props: props_map}] } }).send();
        });

        gas_results = addGasResultsTable({ name: "World place_items", rows: {} });

        // place one item
        await runTaskAndAddGasResults(gas_results, "place_items (1)", () => {
            return contracts.get("World_v2_contract")!.methodsObject.place_items({
                place_key: placeKey0, place_item_map: map_place_one_item
            }).send();
        });

        // place ten items
        await runTaskAndAddGasResults(gas_results, "place_items (10)", () => {
            const map_ten_items = new MichelsonMap<number, MichelsonMap<any, unknown>>()
            const map_ten_items_issuer = new MichelsonMap<boolean, MichelsonMap<any, unknown>>()
            map_ten_items_issuer.set(false, MichelsonMap.fromLiteral({
                [contracts.get("items_FA2_contract")!.address]: [
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } }
                ]
            }));
            map_ten_items.set(0, map_ten_items_issuer);
            return contracts.get("World_v2_contract")!.methodsObject.place_items({
                place_key: placeKey0, place_item_map: map_ten_items
            }).send();
        });

        // place one item in multiple chunks
        await runTaskAndAddGasResults(gas_results, "place_items chunks (2x1)", () => {
            const map_one_item_multiple_chunks = new MichelsonMap<number, MichelsonMap<any, unknown>>()
            const map_one_item_issuer = new MichelsonMap<boolean, MichelsonMap<any, unknown>>()
            map_one_item_issuer.set(false, MichelsonMap.fromLiteral({
                [contracts.get("items_FA2_contract")!.address]: [
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } }
                ]
            }));
            map_one_item_multiple_chunks.set(0, map_one_item_issuer);
            map_one_item_multiple_chunks.set(1, map_one_item_issuer);
            return contracts.get("World_v2_contract")!.methodsObject.place_items({
                place_key: placeKey0, place_item_map: map_one_item_multiple_chunks
            }).send();
        });

        // place ten items in multiple chunks
        await runTaskAndAddGasResults(gas_results, "place_items chunks (2x10)", () => {
            const map_ten_items = new MichelsonMap<number, MichelsonMap<any, unknown>>()
            const map_ten_items_issuer = new MichelsonMap<boolean, MichelsonMap<any, unknown>>()
            map_ten_items_issuer.set(false, MichelsonMap.fromLiteral({
                [contracts.get("items_FA2_contract")!.address]: [
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } },
                    { item: { token_id: 0, amount: 1, rate: defaultRate, data: "01800040520000baa6c9c2460a4000", primary: false } }
                ]
            }));
            map_ten_items.set(0, map_ten_items_issuer);
            map_ten_items.set(1, map_ten_items_issuer);
            return contracts.get("World_v2_contract")!.methodsObject.place_items({
                place_key: placeKey0, place_item_map: map_ten_items
            }).send();
        });

        gas_results = addGasResultsTable({ name: "World set_item_data", rows: {} });

        // set one items data
        await runTaskAndAddGasResults(gas_results, "set_item_data (1)", () => {
            const map_update_one_item = new MichelsonMap<number, unknown>()
            const map_update_one_item_issuer = MichelsonMap.fromLiteral({
                [this.accountAddress!]: {
                    [contracts.get("items_FA2_contract")!.address]: [
                        { item_id: 0, data: "01800041b1be48a779c9c244023dd5" }
                    ]
                }
            });
            map_update_one_item.set(0, map_update_one_item_issuer)
            return contracts.get("World_v2_contract")!.methodsObject.set_item_data({
                place_key: placeKey0, update_map: map_update_one_item
            }).send();
        });

        // set ten items data
        await runTaskAndAddGasResults(gas_results, "set_item_data (10)", () => {
            const map_update_ten_items = new MichelsonMap<number, unknown>()
            const map_update_ten_items_issuer = MichelsonMap.fromLiteral({
                [this.accountAddress!]: {
                    [contracts.get("items_FA2_contract")!.address]: [
                        { item_id: 1, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 2, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 3, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 4, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 5, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 6, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 7, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 8, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 9, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 10, data: "01800041b1be48a779c9c244023dd5" }
                    ]
                }
            });
            map_update_ten_items.set(0, map_update_ten_items_issuer)
            return contracts.get("World_v2_contract")!.methodsObject.set_item_data({
                place_key: placeKey0, update_map: map_update_ten_items
            }).send();
        });

        // set one items data multiple chunks
        await runTaskAndAddGasResults(gas_results, "set_item_data chunks (2x1)", () => {
            const map_update_one_item = new MichelsonMap<number, unknown>()
            const map_update_one_item_issuer = MichelsonMap.fromLiteral({
                [this.accountAddress!]: {
                    [contracts.get("items_FA2_contract")!.address]: [
                        { item_id: 0, data: "01800041b1be48a779c9c244023dd5" }
                    ]
                }
            });
            map_update_one_item.set(0, map_update_one_item_issuer)
            map_update_one_item.set(1, map_update_one_item_issuer)
            return contracts.get("World_v2_contract")!.methodsObject.set_item_data({
                place_key: placeKey0, update_map: map_update_one_item
            }).send();
        });

        // set ten items data multiple chunks
        await runTaskAndAddGasResults(gas_results, "set_item_data chunks (2x10)", () => {
            const map_update_ten_items = new MichelsonMap<number, unknown>()
            const map_update_ten_items_issuer = MichelsonMap.fromLiteral({
                [this.accountAddress!]: {
                    [contracts.get("items_FA2_contract")!.address]: [
                        { item_id: 1, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 2, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 3, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 4, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 5, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 6, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 7, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 8, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 9, data: "01800041b1be48a779c9c244023dd5" },
                        { item_id: 10, data: "01800041b1be48a779c9c244023dd5" }
                    ]
                }
            });
            map_update_ten_items.set(0, map_update_ten_items_issuer)
            map_update_ten_items.set(1, map_update_ten_items_issuer)
            return contracts.get("World_v2_contract")!.methodsObject.set_item_data({
                place_key: placeKey0, update_map: map_update_ten_items
            }).send();
        });

        gas_results = addGasResultsTable({ name: "World remove_items", rows: {} });

        // remove one item
        await runTaskAndAddGasResults(gas_results, "remove_items (1)", () => {
            const map_remove_one_item = new MichelsonMap<number, unknown>()
            const map_remove_one_item_issuer = MichelsonMap.fromLiteral({
                [this.accountAddress!]: {
                    [contracts.get("items_FA2_contract")!.address]: [0]
                }
            });
            map_remove_one_item.set(0, map_remove_one_item_issuer)
            return contracts.get("World_v2_contract")!.methodsObject.remove_items({
                place_key: placeKey0, remove_map: map_remove_one_item
            }).send();
        });

        // remove ten items
        await runTaskAndAddGasResults(gas_results, "remove_items (10)", () => {
            const map_remove_ten_items = new MichelsonMap<number, unknown>()
            const map_remove_ten_items_issuer = MichelsonMap.fromLiteral({
                [this.accountAddress!]: {
                    [contracts.get("items_FA2_contract")!.address]: [1,2,3,4,5,6,7,8,9,10]
                }
            });
            map_remove_ten_items.set(0, map_remove_ten_items_issuer)
            return contracts.get("World_v2_contract")!.methodsObject.remove_items({
                place_key: placeKey0, remove_map: map_remove_ten_items
            }).send();
        });

        // remove one item multiple chunks
        await runTaskAndAddGasResults(gas_results, "remove_items chunks (2x1)", () => {
            const map_remove_one_item = new MichelsonMap<number, unknown>()
            const map_remove_one_item_issuer = MichelsonMap.fromLiteral({
                [this.accountAddress!]: {
                    [contracts.get("items_FA2_contract")!.address]: [11]
                }
            });
            const map_remove_one_item_issuer_1 = MichelsonMap.fromLiteral({
                [this.accountAddress!]: {
                    [contracts.get("items_FA2_contract")!.address]: [0]
                }
            });
            map_remove_one_item.set(0, map_remove_one_item_issuer)
            map_remove_one_item.set(1, map_remove_one_item_issuer_1)
            return contracts.get("World_v2_contract")!.methodsObject.remove_items({
                place_key: placeKey0, remove_map: map_remove_one_item
            }).send();
        });

        // remove ten items multiple chunks
        await runTaskAndAddGasResults(gas_results, "remove_items chunks (2x10)", () => {
            const map_remove_ten_items = new MichelsonMap<number, unknown>()
            const map_remove_ten_items_issuer = MichelsonMap.fromLiteral({
                [this.accountAddress!]: {
                    [contracts.get("items_FA2_contract")!.address]: [12,13,14,15,16,17,18,19,20,21]
                }
            });
            const map_remove_ten_items_issuer_1 = MichelsonMap.fromLiteral({
                [this.accountAddress!]: {
                    [contracts.get("items_FA2_contract")!.address]: [1,2,3,4,5,6,7,8,9,10]
                }
            });
            map_remove_ten_items.set(0, map_remove_ten_items_issuer)
            map_remove_ten_items.set(1, map_remove_ten_items_issuer_1)
            return contracts.get("World_v2_contract")!.methodsObject.remove_items({
                place_key: placeKey0, remove_map: map_remove_ten_items
            }).send();
        });

        gas_results = addGasResultsTable({ name: "World set_permissions", rows: {} });

        // set_permissions
        await runTaskAndAddGasResults(gas_results, "set_permissions", () => {
            return contracts.get("World_v2_contract")!.methods.set_permissions([{
                add: {
                    place_key: placeKey0,
                    owner: this.accountAddress,
                    permittee: contracts.get("Dutch_v2_contract")!.address,
                    perm: 7
                }
            }]).send();
        });

        // get item (v1)
        await runTaskAndAddGasResults(gas_results, "get_item (v1)", () => {
            return contracts.get("World_v2_contract")!.methodsObject.get_item({
                place_key: placeKey0, chunk_id: 0, issuer: this.accountAddress, fa2: contracts.get("items_FA2_contract")!.address, item_id: 22
            }).send({ mutez: true, amount: 1000000 });
        });

        // get item (v2)
        await runTaskAndAddGasResults(gas_results, "get_item (v2)", () => {
            return contracts.get("World_v2_contract")!.methodsObject.get_item({
                place_key: placeKey2, chunk_id: 0, issuer: this.accountAddress, fa2: contracts.get("items_v2_FA2_contract")!.address, item_id: 0
            }).send({ mutez: true, amount: 1000000 });
        });

        gas_results = addGasResultsTable({ name: "Auctions", rows: {} });

        /**
         * Auctions
         */
        // set operator
        await runTaskAndAddGasResults(gas_results, "create_auction", () => {
            const current_time = Math.floor(Date.now() / 1000) + config.sandbox.blockTime;
            return this.tezos!.wallet.batch().with([
                // add operator
                {
                    kind: OpKind.TRANSACTION,
                    ...contracts.get("places_v2_FA2_contract")!.methods.update_operators([{
                        add_operator: {
                            owner: this.accountAddress,
                            operator: contracts.get("Dutch_v2_contract")!.address,
                            token_id: 0
                        }
                    }]).toTransferParams()
                },
                // create auction
                {
                    kind: OpKind.TRANSACTION,
                    ...contracts.get("Dutch_v2_contract")!.methodsObject.create({
                        auction_key: {
                            fa2: contracts.get("places_v2_FA2_contract")!.address,
                            token_id: 0,
                            owner: this.accountAddress
                        },
                        auction: {
                            start_price: 200000,
                            end_price: 100000,
                            start_time: current_time.toString(),
                            end_time: (current_time + 2000).toString()
                        }
                    }).toTransferParams()
                }
            ]).send();
        });

        await sleep(config.sandbox.blockTime * 1000);

        await runTaskAndAddGasResults(gas_results, "bid", async () => {
            const chunkSeqHash = await this.getHashedPlaceSeq(contracts, {
                fa2: contracts.get("places_v2_FA2_contract")!.address, id: 0
            });

            return contracts.get("Dutch_v2_contract")!.methodsObject.bid({
                auction_key: {
                    fa2: contracts.get("places_v2_FA2_contract")!.address,
                    token_id: 0,
                    owner: this.accountAddress
                },
                seq_hash: chunkSeqHash
            }).send({amount: 200000, mutez: true});
        });

        await runTaskAndAddGasResults(gas_results, "create_auction", () => {
            const current_time = Math.floor(Date.now() / 1000) + config.sandbox.blockTime;
            return this.tezos!.wallet.batch().with([
                // add operator
                {
                    kind: OpKind.TRANSACTION,
                    ...contracts.get("places_v2_FA2_contract")!.methods.update_operators([{
                        add_operator: {
                            owner: this.accountAddress,
                            operator: contracts.get("Dutch_v2_contract")!.address,
                            token_id: 0
                        }
                    }]).toTransferParams()
                },
                // create auction
                {
                    kind: OpKind.TRANSACTION,
                    ...contracts.get("Dutch_v2_contract")!.methodsObject.create({
                        auction_key: {
                            fa2: contracts.get("places_v2_FA2_contract")!.address,
                            token_id: 0,
                            owner: this.accountAddress
                        },
                        auction: {
                            start_price: 200000,
                            end_price: 100000,
                            start_time: current_time.toString(),
                            end_time: (current_time + 2000).toString()
                        }
                    }).toTransferParams()
                }
            ]).send();
        });

        await sleep(config.sandbox.blockTime * 1000);

        await runTaskAndAddGasResults(gas_results, "cancel", () => {
            return contracts.get("Dutch_v2_contract")!.methodsObject.cancel({
                auction_key: {
                    fa2: contracts.get("places_v2_FA2_contract")!.address,
                    token_id: 0,
                    owner: this.accountAddress
                }
            }).send();
        });

        gas_results = addGasResultsTable({ name: "Adhoc Operators", rows: {} });

        /**
         * Test adhoc operator storage effects on gas consumption.
         */
        // set 100 regular operators
        await runTaskAndAddGasResults(gas_results, "update_operators (100)", () => {
            const op_alot = [];
            for (const n of [...Array(100).keys()])
                op_alot.push({
                    add_operator: {
                        owner: this.accountAddress,
                        operator: contracts.get("Minter_v2_contract")!.address,
                        token_id: n
                    }
                });
            return contracts.get("items_FA2_contract")!.methods.update_operators(
                op_alot
            ).send();
        });

        // token transfer
        await runTaskAndAddGasResults(gas_results, "transfer", () => {
            return contracts.get("items_FA2_contract")!.methodsObject.transfer([{
                from_: this.accountAddress,
                txs: [{
                    to_: contracts.get("Minter_v2_contract")!.address,
                    amount: 1,
                    token_id: 0
                }]
            }]).send();
        });

        // set adhoc operators
        await runTaskAndAddGasResults(gas_results, "update_adhoc_operators", () => {
            return contracts.get("items_FA2_contract")!.methodsObject.update_adhoc_operators({
                add_adhoc_operators: [{
                    operator: contracts.get("Minter_v2_contract")!.address,
                    token_id: 0
                }]
            }).send();
        });

        // set max adhoc operators
        let item_adhoc_max_op: ContractMethodObject<Wallet>;
        await runTaskAndAddGasResults(gas_results, "update_adhoc_operators (100)", () => {
            const adhoc_ops = [];
            for (const n of [...Array(100).keys()])
                adhoc_ops.push({
                    operator: contracts.get("Minter_v2_contract")!.address,
                    token_id: n
                });
            item_adhoc_max_op = contracts.get("items_FA2_contract")!.methodsObject.update_adhoc_operators({
                add_adhoc_operators: adhoc_ops
            });
            return item_adhoc_max_op.send();
        });

        await runTaskAndAddGasResults(gas_results, "update_adhoc_operators (100)", () => {
            // Do that again to see storage diff
            return item_adhoc_max_op.send();
        });

        // tokens transfer
        await runTaskAndAddGasResults(gas_results, "transfer (100 adhoc)", () => {
            return contracts.get("items_FA2_contract")!.methodsObject.transfer([{
                from_: this.accountAddress,
                txs: [{
                    to_: contracts.get("Minter_v2_contract")!.address,
                    amount: 1,
                    token_id: 0
                }]
            }]).send();
        });

        // set adhoc operators
        await runTaskAndAddGasResults(gas_results, "update_adhoc_operators (reset)", async () => {
            return contracts.get("items_FA2_contract")!.methodsObject.update_adhoc_operators({
                add_adhoc_operators: [{
                    operator: contracts.get("Minter_v2_contract")!.address,
                    token_id: 0
                }]
            }).send();
        });

        // final transfer after adhoc reset
        await runTaskAndAddGasResults(gas_results, "transfer (reset)", () => {
            return contracts.get("items_FA2_contract")!.methodsObject.transfer([{
                from_: this.accountAddress,
                txs: [{
                    to_: contracts.get("Minter_v2_contract")!.address,
                    amount: 1,
                    token_id: 0
                }]
            }]).send();
        });

        gas_results = addGasResultsTable({ name: "Mint", rows: {} });

        // mint again
        await runTaskAndAddGasResults(gas_results, "mint some (2)", async () => {
            const mint_batch2 = this.tezos!.wallet.batch();
            await this.mintNewItem_public('assets/Duck.glb', 4212, 10000, mint_batch2, contracts.get("Minter_v2_contract")!, contracts.get("items_v2_FA2_contract")!);
            await this.mintNewItem_public('assets/Duck.glb', 4212, 10000, mint_batch2, contracts.get("Minter_v2_contract")!, contracts.get("items_v2_FA2_contract")!);
            return mint_batch2.send();
        });

        // Do that again to see storage diff
        await runTaskAndAddGasResults(gas_results, "update_adhoc_operators (100)", async () => {
            return item_adhoc_max_op.send()
        });

        gas_results = addGasResultsTable({ name: "Factory", rows: {} });

        /**
         * Factory
         */
        var originatedTokenContractAddress: string | undefined;
        await runTaskAndAddGasResults(gas_results, "create_token", async () => {
            const token_metadata_url = await ipfs.upload_metadata({name: "bla", whatever: "yes"}, this.isSandboxNet);
            const op = await contracts.get("Factory_contract")!.methods.create_token(
                char2Bytes(token_metadata_url)
            ).send();

            await op.confirmation();

            const result = await op.operationResults();
            // looking for originated_contracts
            for (const res of result) {
                if (res.kind === OpKind.TRANSACTION) {
                    const tx: OperationContentsAndResultTransaction = res;
                    for (const internal_res of tx.metadata.internal_operation_results!) {
                        const orig = internal_res.result as OperationResultOrigination;
                        if (orig.originated_contracts) {
                            originatedTokenContractAddress = orig.originated_contracts[0]
                            console.log(`Found originated token contract: ${originatedTokenContractAddress}`)
                        }
                    }
                }
            }

            return op;
        });

        const originatedTokenContract = await this.tezos!.wallet.at(originatedTokenContractAddress!);

        // mint with created token.
        await runTaskAndAddGasResults(gas_results, "mint_private (2)", async () => {
            const mint_batch2 = this.tezos!.wallet.batch();
            await this.mintNewItem_private('assets/Duck.glb', 4212, 10000, mint_batch2, contracts.get("Minter_v2_contract")!, originatedTokenContract);
            await this.mintNewItem_private('assets/Duck.glb', 4212, 10000, mint_batch2, contracts.get("Minter_v2_contract")!, originatedTokenContract);
            return mint_batch2.send();
        });

        // transfer with created token
        await runTaskAndAddGasResults(gas_results, "transfer", () => {
            return originatedTokenContract.methodsObject.transfer([{
                from_: this.accountAddress,
                txs: [{
                    to_: contracts.get("Minter_v2_contract")!.address,
                    amount: 1,
                    token_id: 0
                }]
            }]).send();
        });
        

        /**
         * Print results to console.
         */
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

    private async mintAndPlace(contracts: PostDeployContracts, per_batch: number = 100, batches: number = 30, token_id: number = 0) {
        assert(this.tezos);

        console.log(kleur.bgGreen("Single Place stress test: " + token_id));

        const mint_batch = this.tezos.wallet.batch();
        await this.mintNewItem_public('assets/Duck.glb', 4212, 10000, mint_batch, contracts.get("Minter_v2_contract")!, contracts.get("items_v2_FA2_contract")!);
        this.mintNewPlaces([await WorldUtils.prepareNewPlace(token_id, [0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]], this.accountAddress!, this.isSandboxNet)], mint_batch, contracts.get("places_v2_FA2_contract")!);
        const mint_batch_op = await mint_batch.send();
        await mint_batch_op.confirmation();

        // set operator
        const op_op = await contracts.get("items_FA2_contract")!.methods.update_operators([{
            add_operator: {
                owner: this.accountAddress,
                operator: contracts.get("World_v2_contract")!.address,
                token_id: token_id
            }
        }]).send()
        await op_op.confirmation();

        const item_list = [];
        for (let i = 0; i < per_batch; ++i)
            item_list.push({ item: { token_id: token_id, amount: 1, rate: 1000000, data: "01800040520000baa6c9c2460a4000", primary: false } });


        const item_map = new MichelsonMap<number, MichelsonMap<any, unknown>>()
        const item_map_issuer = new MichelsonMap<boolean, MichelsonMap<any, unknown>>()
        item_map_issuer.set(false, MichelsonMap.fromLiteral({ [contracts.get("items_FA2_contract")!.address]: item_list } ));
        item_map.set(0, item_map_issuer);

        for (let i = 0; i < batches; ++i) {
            console.log("Placing batch: ", i + 1);
            const place_ten_items_op = await contracts.get("World_v2_contract")!.methodsObject.place_items({
                place_key: {fa2: contracts.get("places_v2_FA2_contract")!.address, id: token_id }, place_item_map: item_map
            }).send();
            await place_ten_items_op.confirmation();
            console.log("place_items:\t" + await this.feesToString(place_ten_items_op));
        }

        /*const place_items_op = await contracts.get("World_v2_contract")!.methodsObject.place_items({
            lot_id: token_id, place_item_map: michelsonmap... [{ item: { token_id: token_id, amount: 1, rate: 1000000, data: "01800040520000baa6c9c2460a4000" } }]
        }).send();
        await place_items_op.confirmation();

        const map_update_one_item: MichelsonMap<string, object[]> = new MichelsonMap();
        map_update_one_item.set(this.accountAddress!, [{ item_id: 0, data: "000000000000000000000000000000" }]);
        const set_item_data_op = await contracts.get("World_v2_contract")!.methodsObject.set_item_data({
            lot_id: token_id, update_map: map_update_one_item
        }).send();
        await set_item_data_op.confirmation();
        console.log("set_item_data:\t" + await this.feesToString(set_item_data_op));*/
    }

    protected async stressTestSingle(contracts: PostDeployContracts, per_batch: number = 100, batches: number = 30, token_id: number = 0) {
        const set_item_limit_op = await contracts.get("World_v2_contract")!.methodsObject.update_item_limit(10000).send();
        await set_item_limit_op.confirmation();

        this.mintAndPlace(contracts);
    }

    protected async stressTestMulti(contracts: PostDeployContracts) {
        const set_item_limit_op = await contracts.get("World_v2_contract")!.methodsObject.update_item_limit(10000).send();
        await set_item_limit_op.confirmation();

        for (let i = 0; i < 1000; ++i) {
            try {
                await this.mintAndPlace(contracts, 100, 10, i);
            } catch {
                console.log(kleur.red("stressTestSingle failed: " + i));
            }
        }
    }
}