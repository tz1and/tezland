import assert from "assert";
import PostDeployBase, { PostDeployContracts } from "./PostDeployBase";
import * as ipfs from '../ipfs'
import { ContractAbstraction, MichelsonMap, OpKind, Wallet, WalletOperationBatch } from "@taquito/taquito";
import kleur from "kleur";
import config from "../user.config";
import { sleep } from "./DeployBase";


export default class PostDeploy extends PostDeployBase {
    protected printContracts(contracts: PostDeployContracts) {
        console.log("REACT_APP_ITEM_CONTRACT=" + contracts.get("items_FA2_contract")!.address);
        console.log("REACT_APP_PLACE_CONTRACT=" + contracts.get("places_FA2_contract")!.address);
        console.log("REACT_APP_DAO_CONTRACT=" + contracts.get("dao_FA2_contract")!.address);
        console.log("REACT_APP_WORLD_CONTRACT=" + contracts.get("World_contract")!.address);
        console.log("REACT_APP_MINTER_CONTRACT=" + contracts.get("Minter_contract")!.address);
        console.log("REACT_APP_DUTCH_AUCTION_CONTRACT=" + contracts.get("Dutch_contract")!.address);
        console.log()
        console.log(`contracts:
  tezlandItems:
    address: ${contracts.get("items_FA2_contract")!.address}
    typename: tezlandItems

  tezlandPlaces:
    address: ${contracts.get("places_FA2_contract")!.address}
    typename: tezlandPlaces

  tezlandDAO:
    address: ${contracts.get("dao_FA2_contract")!.address}
    typename: tezlandDAO

  tezlandWorld:
    address: ${contracts.get("World_contract")!.address}
    typename: tezlandWorld

  tezlandMinter:
    address: ${contracts.get("Minter_contract")!.address}
    typename: tezlandMinter

  tezlandDutchAuctions:
    address: ${contracts.get("Dutch_contract")!.address}
    typename: tezlandDutchAuctions\n`);
    }

    private async mintNewItem(model_path: string, polygonCount: number, amount: number, batch: WalletOperationBatch, Minter_contract: ContractAbstraction<Wallet>) {
        assert(this.accountAddress);

        // Create item metadata and upload it
        const item_metadata_url = await ipfs.upload_item_metadata(Minter_contract.address, model_path, polygonCount, this.isSandboxNet);
        console.log(`item token metadata: ${item_metadata_url}`);

        const contributors = [
            { address: this.accountAddress, relative_royalties: 1000, role: {minter: null} }
        ];

        batch.with([{
            kind: OpKind.TRANSACTION,
            ...Minter_contract.methodsObject.mint_Item({
                to_: this.accountAddress,
                amount: amount,
                royalties: 250,
                contributors: contributors,
                metadata: Buffer.from(item_metadata_url, 'utf8').toString('hex')
            }).toTransferParams()
        }]);
    }

    // Create place metadata and upload it
    private mintNewPlaces(mint_args: any[], batch: WalletOperationBatch, Minter_contract: ContractAbstraction<Wallet>) {
        batch.with([{
            kind: OpKind.TRANSACTION,
            ...Minter_contract.methodsObject.mint_Place(
                mint_args
            ).toTransferParams()
        }]);
    }

    private async prepareNewPlace(center: number[], border: number[][], buildHeight: number = 10): Promise<any> {
        const place_metadata_url = await ipfs.upload_place_metadata({
            name: "Some Place",
            description: "A nice place",
            minter: this.accountAddress!,
            centerCoordinates: center,
            borderCoordinates: border,
            buildHeight: buildHeight,
            placeType: "exterior"
        }, this.isSandboxNet);
        console.log(`place token metadata: ${place_metadata_url}`);

        const metadata_map = new MichelsonMap<string,string>({ prim: "map", args: [{prim: "string"}, {prim: "bytes"}]});
        metadata_map.set('', Buffer.from(place_metadata_url, 'utf8').toString('hex'));
        return {
            to_: this.accountAddress,
            metadata: metadata_map
        }
    }

    protected async deployDevWorld(contracts: PostDeployContracts) {
        console.log(kleur.bgGreen("Deploying dev world"));

        // prepare batch
        await this.run_op_task("Mint items", async () => {
            const mint_batch = this.tezos!.wallet.batch();

            await this.mintNewItem('assets/Lantern.glb', 5394, 100, mint_batch, contracts.get("Minter_contract")!);
            await this.mintNewItem('assets/Fox.glb', 576, 25, mint_batch, contracts.get("Minter_contract")!);
            await this.mintNewItem('assets/Duck.glb', 4212, 75, mint_batch, contracts.get("Minter_contract")!);
            await this.mintNewItem('assets/DragonAttenuation.glb', 134995, 66, mint_batch, contracts.get("Minter_contract")!);

            const places = [];
            places.push(await this.prepareNewPlace([0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]]));
            places.push(await this.prepareNewPlace([22, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]]));
            places.push(await this.prepareNewPlace([22, 0, -22], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]]));
            places.push(await this.prepareNewPlace([0, 0, -25], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10], [0, 0, 14]]));
            this.mintNewPlaces(places, mint_batch, contracts.get("Minter_contract")!);

            return mint_batch.send();
        });

        // set operators
        await this.fa2_set_operators(contracts, new Map(Object.entries({
            items_FA2_contract: new Map(Object.entries({
                World_contract: [0, 1, 2, 3]
            })),
            places_FA2_contract: new Map(Object.entries({
                Dutch_contract: [1, 3]
            }))
        })));

        await this.run_op_task("Place 10 items in Place #0", () => {
            const list_ten_items = [
                { item: { token_id: 1, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
                { item: { token_id: 2, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
                { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
                { item: { token_id: 2, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
                { item: { token_id: 3, token_amount: 10, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
                { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
                { item: { token_id: 1, token_amount: 1, mutez_per_token: 0, item_data: "01800040520000baa6c9c2460a4000" } },
                { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
                { item: { token_id: 3, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
                { item: { token_id: 1, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } }
            ];
            return contracts.get("World_contract")!.methodsObject.place_items({
                lot_id: 0, item_list: list_ten_items
            }).send();
        });

        await this.run_op_task("Place 5 items in Place #2", () => {
            const list_five_items = [
                { item: { token_id: 0, token_amount: 10, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
                { item: { token_id: 1, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
                { item: { token_id: 2, token_amount: 1, mutez_per_token: 0, item_data: "01800040520000baa6c9c2460a4000" } },
                { item: { token_id: 3, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
                { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } }
            ];
            return contracts.get("World_contract")!.methodsObject.place_items({
                lot_id: 2, item_list: list_five_items
            }).send();
        });

        await this.run_op_task("Create auction Place #1", () => {
            let current_time = Math.floor(Date.now() / 1000) + config.sandbox.blockTime;
            return contracts.get("Dutch_contract")!.methodsObject.create({
                token_id: 1,
                start_price: 200000,
                end_price: 100000,
                start_time: current_time.toString(),
                end_time: (current_time + 2000).toString(),
                fa2: contracts.get("places_FA2_contract")!.address
            }).send();
        });

        await this.run_op_task("Create auction Place #3", () => {
            let current_time = Math.floor(Date.now() / 1000) + config.sandbox.blockTime;
            return contracts.get("Dutch_contract")!.methodsObject.create({
                token_id: 3,
                start_price: 200000,
                end_price: 100000,
                start_time: current_time.toString(),
                end_time: (current_time + 2000).toString(),
                fa2: contracts.get("places_FA2_contract")!.address
            }).send();
        });
    }

    protected async gasTestSuite(contracts: PostDeployContracts) {
        assert(this.tezos);
        //assert(this.accountAddress);

        console.log(kleur.bgGreen("Running gas test suite"));

        const mint_batch = this.tezos.wallet.batch();
        await this.mintNewItem('assets/Duck.glb', 4212, 10000, mint_batch, contracts.get("Minter_contract")!);
        this.mintNewPlaces([await this.prepareNewPlace([0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]])], mint_batch, contracts.get("Minter_contract")!);
        this.mintNewPlaces([await this.prepareNewPlace([0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]])], mint_batch, contracts.get("Minter_contract")!);
        const mint_batch_op = await mint_batch.send();
        await mint_batch_op.confirmation();
        console.log();

        // set operator
        const op_op = await contracts.get("items_FA2_contract")!.methods.update_operators([{
            add_operator: {
                owner: this.accountAddress,
                operator: contracts.get("World_contract")!.address,
                token_id: 0
            }
        }]).send()
        await op_op.confirmation();
        console.log("update_operators:\t" + await this.feesToString(op_op));

        /**
         * World
         */
        // place one item to make sure storage is set.
        const list_one_item = [{ item: { token_id: 0, token_amount: 1, mutez_per_token: 1, item_data: "01800040520000baa6c9c2460a4000" } }];
        const setup_storage = await contracts.get("World_contract")!.methodsObject.place_items({
            lot_id: 0, item_list: list_one_item
        }).send();
        await setup_storage.confirmation();
        console.log("create place 0 (item):\t" + await this.feesToString(setup_storage));

        // NOTE: for some reason the first created place is more expensive? some weird storage diff somewhere...
        const setup_storage1 = await contracts.get("World_contract")!.methodsObject.place_items({
            lot_id: 1, item_list: list_one_item
        }).send();
        await setup_storage1.confirmation();
        console.log("create place 1 (item):\t" + await this.feesToString(setup_storage1));
        /*const transfer_op = await items_FA2_contract.methodsObject.transfer([{
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

        // create place
        const creat_op = await World_contract.methodsObject.set_place_props({ lot_id: 0, props: "ffffff" }).send();
        await creat_op.confirmation();
        console.log("create place (props):\t" + await feesToString(creat_op));*/

        // place props
        const props_map = new MichelsonMap<string, string>();
        props_map.set('00', '000000');
        const place_props_op = await contracts.get("World_contract")!.methodsObject.set_place_props({ lot_id: 0, props: props_map }).send();
        await place_props_op.confirmation();
        console.log("set_place_props:\t" + await this.feesToString(place_props_op));
        console.log();

        // place one item
        const place_one_item_op = await contracts.get("World_contract")!.methodsObject.place_items({
            lot_id: 0, item_list: list_one_item
        }).send();
        await place_one_item_op.confirmation();
        console.log("place_items (1):\t" + await this.feesToString(place_one_item_op));

        // place ten items
        const list_ten_items = [
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } }
        ];
        const place_ten_items_op = await contracts.get("World_contract")!.methodsObject.place_items({
            lot_id: 0, item_list: list_ten_items
        }).send();
        await place_ten_items_op.confirmation();
        console.log("place_items (10):\t" + await this.feesToString(place_ten_items_op));
        console.log();

        // set one items data
        const map_update_one_item: MichelsonMap<string, object[]> = new MichelsonMap();
        map_update_one_item.set(this.accountAddress!, [{ item_id: 0, item_data: "01800041b1be48a779c9c244023dd5" }]);
        const set_item_data_op = await contracts.get("World_contract")!.methodsObject.set_item_data({
            lot_id: 0, update_map: map_update_one_item
        }).send();
        await set_item_data_op.confirmation();
        console.log("set_item_data (1):\t" + await this.feesToString(set_item_data_op));

            // set ten items data
        const map_update_ten_items: MichelsonMap<string, object[]> = new MichelsonMap();
        map_update_ten_items.set(this.accountAddress!, [
            { item_id: 1, item_data: "01800041b1be48a779c9c244023dd5" },
            { item_id: 2, item_data: "01800041b1be48a779c9c244023dd5" },
            { item_id: 3, item_data: "01800041b1be48a779c9c244023dd5" },
            { item_id: 4, item_data: "01800041b1be48a779c9c244023dd5" },
            { item_id: 5, item_data: "01800041b1be48a779c9c244023dd5" },
            { item_id: 6, item_data: "01800041b1be48a779c9c244023dd5" },
            { item_id: 7, item_data: "01800041b1be48a779c9c244023dd5" },
            { item_id: 8, item_data: "01800041b1be48a779c9c244023dd5" },
            { item_id: 9, item_data: "01800041b1be48a779c9c244023dd5" },
            { item_id: 10, item_data: "01800041b1be48a779c9c244023dd5" }
        ]);
        const set_ten_items_data_op = await contracts.get("World_contract")!.methodsObject.set_item_data({
            lot_id: 0, update_map: map_update_ten_items
        }).send();
        await set_ten_items_data_op.confirmation();
        console.log("set_item_data (10):\t" + await this.feesToString(set_ten_items_data_op));
        console.log();

        // remove one item
        const map_remove_one_item: MichelsonMap<string, number[]> = new MichelsonMap();
        map_remove_one_item.set(this.accountAddress!, [0]);
        const remove_one_item_op = await contracts.get("World_contract")!.methodsObject.remove_items({
            lot_id: 0, remove_map: map_remove_one_item
        }).send();
        await remove_one_item_op.confirmation();
        console.log("remove_items (1):\t" + await this.feesToString(remove_one_item_op));

        // remove ten items
        const map_remove_ten_items: MichelsonMap<string, number[]> = new MichelsonMap();
        map_remove_ten_items.set(this.accountAddress!, [1,2,3,4,5,6,7,8,9,10]);
        const remove_ten_items_op = await contracts.get("World_contract")!.methodsObject.remove_items({
            lot_id: 0, remove_map: map_remove_ten_items
        }).send();
        await remove_ten_items_op.confirmation();
        console.log("remove_items (10):\t" + await this.feesToString(remove_ten_items_op));
        console.log();

        // set_permissions
        const perm_op = await contracts.get("World_contract")!.methods.set_permissions([{
            add_permission: {
                owner: this.accountAddress,
                permittee: contracts.get("Dutch_contract")!.address,
                token_id: 0,
                perm: 7
            }
        }]).send()
        await perm_op.confirmation();
        console.log("set_permissions:\t" + await this.feesToString(perm_op));

        // get item
        const get_item_op = await contracts.get("World_contract")!.methodsObject.get_item({
            lot_id: 0, issuer: this.accountAddress, item_id: 11
        }).send({ mutez: true, amount: 1000000 });
        await get_item_op.confirmation();
        console.log("get_item:\t\t" + await this.feesToString(get_item_op));
        console.log();
        console.log();

        /**
         * Auctions
         */
        // set operator
        const place_op_op = await contracts.get("places_FA2_contract")!.methods.update_operators([{
            add_operator: {
                owner: this.accountAddress,
                operator: contracts.get("Dutch_contract")!.address,
                token_id: 0
            }
        }]).send()
        await place_op_op.confirmation();
        console.log("update_operators:\t" + await this.feesToString(place_op_op));

        const whitelist_enable_op = await contracts.get("Dutch_contract")!.methodsObject.manage_whitelist([{
            whitelist_enabled: false
        }]).send()
        await whitelist_enable_op.confirmation();
        console.log("manage_whitelist:\t" + await this.feesToString(whitelist_enable_op));
        console.log();

        let current_time = Math.floor(Date.now() / 1000) + config.sandbox.blockTime;
        const create_auction_op = await contracts.get("Dutch_contract")!.methodsObject.create({
            token_id: 0,
            start_price: 200000,
            end_price: 100000,
            start_time: current_time.toString(),
            end_time: (current_time + 2000).toString(),
            fa2: contracts.get("places_FA2_contract")!.address
        }).send();
        await create_auction_op.confirmation();
        console.log("create_auction:\t\t" + await this.feesToString(create_auction_op));
        await sleep(config.sandbox.blockTime * 1000);

        const bid_op = await contracts.get("Dutch_contract")!.methodsObject.bid({auction_id: 0}).send({amount: 200000, mutez: true});
        await bid_op.confirmation();
        console.log("bid:\t\t\t" + await this.feesToString(bid_op));
        console.log();

        current_time = Math.floor(Date.now() / 1000) + config.sandbox.blockTime;
        const create_auction1_op = await contracts.get("Dutch_contract")!.methodsObject.create({
            token_id: 0,
            start_price: 200000,
            end_price: 100000,
            start_time: current_time.toString(),
            end_time: (current_time + 2000).toString(),
            fa2: contracts.get("places_FA2_contract")!.address
        }).send();
        await create_auction1_op.confirmation();
        console.log("create_auction:\t\t" + await this.feesToString(create_auction1_op));
        await sleep(config.sandbox.blockTime * 1000);

        const cancel_op = await contracts.get("Dutch_contract")!.methodsObject.cancel({auction_id: 1}).send();
        await cancel_op.confirmation();
        console.log("cancel:\t\t\t" + await this.feesToString(cancel_op));
        console.log();
        console.log();

        /**
         * Test adhoc operator storage effects on gas consumption.
         */
        // set 100 regular operators
        const op_alot = [];
        for (const n of [...Array(100).keys()])
            op_alot.push({
                add_operator: {
                    owner: this.accountAddress,
                    operator: contracts.get("Minter_contract")!.address,
                    token_id: n
                }
            });
        const op_alot_op = await contracts.get("items_FA2_contract")!.methods.update_operators(
            op_alot
        ).send()
        await op_alot_op.confirmation();
        console.log("update_operators (100):\t\t" + await this.feesToString(op_alot_op));
        console.log();

        // token transfer
        const transfer_before_op = await contracts.get("items_FA2_contract")!.methodsObject.transfer([{
            from_: this.accountAddress,
            txs: [{
                to_: contracts.get("Minter_contract")!.address,
                amount: 1,
                token_id: 0
            }]
        }]).send();
        await transfer_before_op.confirmation();
        console.log("transfer:\t\t\t" + await this.feesToString(transfer_before_op));

        // set adhoc operators
        const item_adhoc_op_op = await contracts.get("items_FA2_contract")!.methodsObject.update_adhoc_operators({
            add_adhoc_operators: [{
                operator: contracts.get("Minter_contract")!.address,
                token_id: 0
            }]
        }).send()
        await item_adhoc_op_op.confirmation();
        console.log("update_adhoc_operators:\t\t" + await this.feesToString(item_adhoc_op_op));

        // set max adhoc operators
        const adhoc_ops = [];
        for (const n of [...Array(100).keys()])
            adhoc_ops.push({
                operator: contracts.get("Minter_contract")!.address,
                token_id: n
            });
        const item_adhoc_max_op = contracts.get("items_FA2_contract")!.methodsObject.update_adhoc_operators({
            add_adhoc_operators: adhoc_ops
        });
        const item_adhoc_max_op_op = await item_adhoc_max_op.send()
        await item_adhoc_max_op_op.confirmation();
        console.log("update_adhoc_operators (100):\t" + await this.feesToString(item_adhoc_max_op_op));
        // Do that again to see storage diff
        const item_adhoc_max_op_op2 = await item_adhoc_max_op.send()
        await item_adhoc_max_op_op2.confirmation();
        console.log("update_adhoc_operators (100):\t" + await this.feesToString(item_adhoc_max_op_op2));

        // tokens transfer
        const transfer_after_op = await contracts.get("items_FA2_contract")!.methodsObject.transfer([{
            from_: this.accountAddress,
            txs: [{
                to_: contracts.get("Minter_contract")!.address,
                amount: 1,
                token_id: 0
            }]
        }]).send();
        await transfer_after_op.confirmation();
        console.log("transfer (100 adhoc):\t\t" + await this.feesToString(transfer_after_op));

        // set adhoc operators
        const item_adhoc_after_op = await contracts.get("items_FA2_contract")!.methodsObject.update_adhoc_operators({
            add_adhoc_operators: [{
                operator: contracts.get("Minter_contract")!.address,
                token_id: 0
            }]
        }).send()
        await item_adhoc_after_op.confirmation();
        console.log("update_adhoc_operators (reset):\t" + await this.feesToString(item_adhoc_after_op));

        // final transfer after adhoc reset
        const transfer_final_op = await contracts.get("items_FA2_contract")!.methodsObject.transfer([{
            from_: this.accountAddress,
            txs: [{
                to_: contracts.get("Minter_contract")!.address,
                amount: 1,
                token_id: 0
            }]
        }]).send();
        await transfer_final_op.confirmation();
        console.log("transfer (reset):\t\t" + await this.feesToString(transfer_final_op));
        console.log();

        // mint again
        const mint_batch2 = this.tezos.wallet.batch();
        await this.mintNewItem('assets/Duck.glb', 4212, 10000, mint_batch2, contracts.get("Minter_contract")!);
        await this.mintNewItem('assets/Duck.glb', 4212, 10000, mint_batch2, contracts.get("Minter_contract")!);
        const mint_batch2_op = await mint_batch2.send();
        await mint_batch2_op.confirmation();
        console.log("mint some:\t\t\t" + await this.feesToString(mint_batch2_op));

        // Do that again to see storage diff
        const item_adhoc_max_op_op3 = await item_adhoc_max_op.send()
        await item_adhoc_max_op_op3.confirmation();
        console.log("update_adhoc_operators (100):\t" + await this.feesToString(item_adhoc_max_op_op3));
    }

    private async mintAndPlace(contracts: PostDeployContracts, per_batch: number = 100, batches: number = 30, token_id: number = 0) {
        assert(this.tezos);

        console.log(kleur.bgGreen("Single Place stress test: " + token_id));

        const mint_batch = this.tezos.wallet.batch();
        await this.mintNewItem('assets/Duck.glb', 4212, 10000, mint_batch, contracts.get("Minter_contract")!);
        this.mintNewPlaces([await this.prepareNewPlace([0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]])], mint_batch, contracts.get("Minter_contract")!);
        const mint_batch_op = await mint_batch.send();
        await mint_batch_op.confirmation();

        // set operator
        const op_op = await contracts.get("items_FA2_contract")!.methods.update_operators([{
            add_operator: {
                owner: this.accountAddress,
                operator: contracts.get("World_contract")!.address,
                token_id: token_id
            }
        }]).send()
        await op_op.confirmation();

        const item_list = [];
        for (let i = 0; i < per_batch; ++i)
            item_list.push({ item: { token_id: token_id, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } });

        for (let i = 0; i < batches; ++i) {
            console.log("Placing batch: ", i + 1);
            const place_ten_items_op = await contracts.get("World_contract")!.methodsObject.place_items({
                lot_id: token_id, item_list: item_list
            }).send();
            await place_ten_items_op.confirmation();
            console.log("place_items:\t" + await this.feesToString(place_ten_items_op));
        }

        /*const place_items_op = await contracts.World_contract.methodsObject.place_items({
            lot_id: token_id, item_list: [{ item: { token_id: token_id, token_amount: 1, mutez_per_token: 1000000, item_data: "01800040520000baa6c9c2460a4000" } }]
        }).send();
        await place_items_op.confirmation();

        const map_update_one_item: MichelsonMap<string, object[]> = new MichelsonMap();
        map_update_one_item.set(this.accountAddress!, [{ item_id: 0, item_data: "01800041b1be48a779c9c244023dd5" }]);
        const set_item_data_op = await contracts.World_contract.methodsObject.set_item_data({
            lot_id: token_id, update_map: map_update_one_item
        }).send();
        await set_item_data_op.confirmation();
        console.log("set_item_data:\t" + await this.feesToString(set_item_data_op));*/
    }

    protected async stressTestSingle(contracts: PostDeployContracts, per_batch: number = 100, batches: number = 30, token_id: number = 0) {
        const set_item_limit_op = await contracts.get("World_contract")!.methodsObject.update_item_limit(10000).send();
        await set_item_limit_op.confirmation();

        this.mintAndPlace(contracts);
    }

    protected async stressTestMulti(contracts: PostDeployContracts) {
        const set_item_limit_op = await contracts.get("World_contract")!.methodsObject.update_item_limit(10000).send();
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