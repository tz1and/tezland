import * as smartpy from './smartpy';
import * as ipfs from '../ipfs'
import { char2Bytes } from '@taquito/utils'
import assert from 'assert';
import kleur from 'kleur';
import DeployBase, { DeployContractBatch, sleep } from './DeployBase';
import { ContractAbstraction, MichelsonMap, OpKind, TransactionWalletOperation, Wallet, WalletOperationBatch } from '@taquito/taquito';


enum DeployMode { DevWorld, GasTest, StressTestSingle, StressTestMulti };

type PostDeployContracts = {
    items_FA2_contract: ContractAbstraction<Wallet>,
    places_FA2_contract: ContractAbstraction<Wallet>,
    dao_FA2_contract: ContractAbstraction<Wallet>,
    Minter_contract: ContractAbstraction<Wallet>,
    World_contract: ContractAbstraction<Wallet>,
    Dutch_contract: ContractAbstraction<Wallet>
}

// TODO: finish this stuff!
// some issues: dependent transactions: setting adming, etc
export default class Deploy extends DeployBase {
    protected override async deployDo() {
        assert(this.tezos);

        // prepare batch
        const fa2_batch = new DeployContractBatch(this);

        //
        // Items
        //
        const items_metadata_url = await ipfs.upload_contract_metadata({
            name: 'tz1and Items',
            description: 'tz1and Item FA2 Tokens',
            interfaces: ["TZIP-12"],
            version: '1.0.0'
        }, this.isSandboxNet, true);

        // Compile and deploy Items FA2 contract.
        smartpy.compile_newtarget("FA2_Items", "FA2", ['config = FA2_contract.items_config()',
            `metadata = sp.utils.metadata_of_url("${items_metadata_url}")`,
            `admin = sp.address("${this.accountAddress}")`]);

        fa2_batch.addToBatch("FA2_Items");

        //
        // Places
        //
        const places_metadata_url = await ipfs.upload_contract_metadata({
            name: 'tz1and Places',
            description: 'tz1and Places FA2 Tokens',
            interfaces: ["TZIP-12"],
            version: '1.0.0'
        }, this.isSandboxNet, true);

        // Compile and deploy Places FA2 contract.
        smartpy.compile_newtarget("FA2_Places", "FA2", ['config = FA2_contract.places_config()',
            `metadata = sp.utils.metadata_of_url("${places_metadata_url}")`,
            `admin = sp.address("${this.accountAddress}")`]);

        fa2_batch.addToBatch("FA2_Places");

        //
        // DAO
        //
        const dao_metadata_url = await ipfs.upload_contract_metadata({
            name: 'tz1and DAO',
            description: 'tz1and DAO FA2 Token',
            interfaces: ["TZIP-12"],
            version: '1.0.0'
        }, this.isSandboxNet, true);

        // Compile and deploy Places FA2 contract.
        smartpy.compile_newtarget("FA2_DAO", "FA2", ['config = FA2_contract.dao_config()',
            `metadata = sp.utils.metadata_of_url("${dao_metadata_url}")`,
            `admin = sp.address("${this.accountAddress}")`]);

        fa2_batch.addToBatch("FA2_DAO");

        // send batch.
        const [items_FA2_contract, places_FA2_contract, dao_FA2_contract] = await fa2_batch.deployBatch();

        //
        // Minter
        //
        const minterWasDeployed = this.getDeployment("TL_Minter");

        // prepare minter/dutch batch
        const tezland_batch = new DeployContractBatch(this);

        const minter_metadata_url = await ipfs.upload_contract_metadata({
            name: 'tz1and Minter',
            description: 'tz1and Items and Places minter',
            interfaces: [],
            version: '1.0.0'
        }, this.isSandboxNet);

        // Compile and deploy Minter contract.
        smartpy.compile_newtarget("TL_Minter", "TL_Minter", [`administrator = sp.address("${this.accountAddress}")`,
        `items_contract = sp.address("${items_FA2_contract.address}")`,
        `places_contract = sp.address("${places_FA2_contract.address}")`,
        `metadata = sp.utils.metadata_of_url("${minter_metadata_url}")`]);

        tezland_batch.addToBatch("TL_Minter");
        //const Minter_contract = await this.deploy_contract("TL_Minter");

        //
        // Dutch
        //
        const dutch_metadata_url = await ipfs.upload_contract_metadata({
            name: 'tz1and Dutch Auctions',
            description: 'tz1and Places and Items Dutch auctions',
            interfaces: [],
            version: '1.0.0'
        }, this.isSandboxNet);

        // Compile and deploy Dutch auction contract.
        smartpy.compile_newtarget("TL_Dutch", "TL_Dutch", [`administrator = sp.address("${this.accountAddress}")`,
        `items_contract = sp.address("${items_FA2_contract.address}")`,
        `places_contract = sp.address("${places_FA2_contract.address}")`,
        `metadata = sp.utils.metadata_of_url("${dutch_metadata_url}")`]);

        tezland_batch.addToBatch("TL_Dutch");
        //const Dutch_contract = await this.deploy_contract("TL_Dutch");

        const [Minter_contract, Dutch_contract] = await tezland_batch.deployBatch();

        if (!minterWasDeployed) {
            // Set the minter as the token administrator
            console.log("Setting minter as token admin...")
            const set_admin_batch = this.tezos.wallet.batch();
            set_admin_batch.with([
                {
                    kind: OpKind.TRANSACTION,
                    ...items_FA2_contract.methods.transfer_administrator(Minter_contract.address).toTransferParams()
                },
                {
                    kind: OpKind.TRANSACTION,
                    ...places_FA2_contract.methods.transfer_administrator(Minter_contract.address).toTransferParams()
                },
                {
                    kind: OpKind.TRANSACTION,
                    ...Minter_contract.methods.accept_fa2_administrator([places_FA2_contract.address, items_FA2_contract.address]).toTransferParams()
                }
            ])

            const set_admin_batch_op = await set_admin_batch.send();
            await set_admin_batch_op.confirmation();

            console.log("Successfully set minter as tokens admin");
            console.log(`>> Transaction hash: ${set_admin_batch_op.opHash}\n`);
        }

        //
        // World (Marketplaces)
        //
        const worldWasDeployed = this.getDeployment("TL_World");

        const world_metadata_url = await ipfs.upload_contract_metadata({
            name: 'tz1and World',
            description: 'tz1and Virtual World',
            interfaces: [],
            version: '1.0.0'
        }, this.isSandboxNet);

        // Compile and deploy Places contract.
        smartpy.compile_newtarget("TL_World", "TL_World", [`administrator = sp.address("${this.accountAddress}")`,
        `items_contract = sp.address("${items_FA2_contract.address}")`,
        `places_contract = sp.address("${places_FA2_contract.address}")`,
        `dao_contract = sp.address("${dao_FA2_contract.address}")`,
        `metadata = sp.utils.metadata_of_url("${world_metadata_url}")`]);

        const World_contract = await this.deploy_contract("TL_World");

        if(!worldWasDeployed) {
            // Mint 0 dao and set the world as the dao administrator
            console.log("Setting world as dao admin")
            const tokenMetadataMap = new MichelsonMap();
            tokenMetadataMap.set("decimals", char2Bytes("6"));
            tokenMetadataMap.set("name", char2Bytes("tz1and DAO"));
            tokenMetadataMap.set("symbol", char2Bytes("tz1aDAO"));

            const dao_admin_batch = this.tezos.wallet.batch();
            dao_admin_batch.with([
                {
                    kind: OpKind.TRANSACTION,
                    ...dao_FA2_contract.methodsObject.mint({
                        address: this.accountAddress,
                        amount: 0,
                        token_id: 0,
                        metadata: tokenMetadataMap}).toTransferParams()
                },
                {
                    kind: OpKind.TRANSACTION,
                    ...dao_FA2_contract.methods.transfer_administrator(World_contract.address).toTransferParams()
                },
                {
                    kind: OpKind.TRANSACTION,
                    ...World_contract.methods.accept_fa2_administrator([dao_FA2_contract.address]).toTransferParams()
                }
            ])

            const dao_admin_batch_op = await dao_admin_batch.send();
            await dao_admin_batch_op.confirmation();

            console.log("Successfully set world as dao admin");
            console.log(`>> Transaction hash: ${dao_admin_batch_op.opHash}\n`);
        }

        // If this is a test deploy, mint some test items.
        if(this.isSandboxNet) {
            console.log(kleur.magenta("Minting tokens for testing...\n"));

            this.runPostDeply(DeployMode.DevWorld,
                {
                    items_FA2_contract: items_FA2_contract,
                    places_FA2_contract: places_FA2_contract,
                    dao_FA2_contract: dao_FA2_contract,
                    Minter_contract: Minter_contract,
                    World_contract: World_contract,
                    Dutch_contract: Dutch_contract
                }
            );
        }
    }

    private async runPostDeply(
        deploy_mode: DeployMode,
        contracts: PostDeployContracts) {
        switch (deploy_mode) {
            case DeployMode.DevWorld:
                this.deployDevWorld(contracts);
                break;
            case DeployMode.GasTest:
                this.gasTestSuite(contracts);
                break;
            case DeployMode.StressTestSingle:
                this.stressTestSingle(contracts);
                break;
            case DeployMode.StressTestMulti:
                this.stressTestMulti(contracts);
                break;
        }
    }

    private async mintNewItem(model_path: string, amount: number, batch: WalletOperationBatch, Minter_contract: ContractAbstraction<Wallet>) {
        assert(this.accountAddress);

        // Create item metadata and upload it
        const item_metadata_url = await ipfs.upload_item_metadata(Minter_contract.address, model_path, this.isSandboxNet);
        console.log(`item token metadata: ${item_metadata_url}`);

        const contributors: MichelsonMap<string, any> = new MichelsonMap();
        contributors.set(this.accountAddress, { relative_royalties: 1000, role: "minter" });

        batch.with([{
            kind: OpKind.TRANSACTION,
            ...Minter_contract.methodsObject.mint_Item({
                address: this.accountAddress,
                amount: amount,
                royalties: 250,
                contributors: contributors,
                metadata: Buffer.from(item_metadata_url, 'utf8').toString('hex')
            }).toTransferParams()
        }]);
    }

    // Create place metadata and upload it
    private async mintNewPlace(center: number[], border: number[][], batch: WalletOperationBatch, Minter_contract: ContractAbstraction<Wallet>) {
        const place_metadata_url = await ipfs.upload_place_metadata({
            name: "Some Place",
            description: "A nice place",
            minter: this.accountAddress!,
            centerCoordinates: center,
            borderCoordinates: border,
            buildHeight: 10,
            placeType: "exterior"
        }, this.isSandboxNet);
        console.log(`place token metadata: ${place_metadata_url}`);

        batch.with([{
            kind: OpKind.TRANSACTION,
            ...Minter_contract.methodsObject.mint_Place({
                address: this.accountAddress,
                metadata: Buffer.from(place_metadata_url, 'utf8').toString('hex')
            }).toTransferParams()
        }]);
    }

    private async deployDevWorld(contracts: PostDeployContracts) {
        assert(this.tezos);

        console.log(kleur.bgGreen("Deploying dev world"));

        // prepare batch
        const mint_batch = this.tezos.wallet.batch();

        await this.mintNewItem('assets/Lantern.glb', 100, mint_batch, contracts.Minter_contract);
        await this.mintNewItem('assets/Fox.glb', 25, mint_batch, contracts.Minter_contract);
        await this.mintNewItem('assets/Duck.glb', 75, mint_batch, contracts.Minter_contract);
        await this.mintNewItem('assets/DragonAttenuation.glb', 66, mint_batch, contracts.Minter_contract);

        // don't mint places for now. use generate map.
        await this.mintNewPlace([0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]], mint_batch, contracts.Minter_contract);
        await this.mintNewPlace([22, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]], mint_batch, contracts.Minter_contract);
        await this.mintNewPlace([22, 0, -22], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]], mint_batch, contracts.Minter_contract);
        await this.mintNewPlace([0, 0, -25], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10], [0, 0, 14]], mint_batch, contracts.Minter_contract);

        // send batch.
        const mint_batch_op = await mint_batch.send();
        await mint_batch_op.confirmation();

        console.log("Successfully minted items");
        console.log(`>> Transaction hash: ${mint_batch_op.opHash}\n`);

        console.log("REACT_APP_ITEM_CONTRACT=" + contracts.items_FA2_contract.address);
        console.log("REACT_APP_PLACE_CONTRACT=" + contracts.places_FA2_contract.address);
        console.log("REACT_APP_DAO_CONTRACT=" + contracts.dao_FA2_contract.address);
        console.log("REACT_APP_WORLD_CONTRACT=" + contracts.World_contract.address);
        console.log("REACT_APP_MINTER_CONTRACT=" + contracts.Minter_contract.address);
        console.log("REACT_APP_DUTCH_AUCTION_CONTRACT=" + contracts.Dutch_contract.address);
        console.log()
        console.log(`contracts:
  tezlandItems:
    address: ${contracts.items_FA2_contract.address}
    typename: tezlandItems

  tezlandPlaces:
    address: ${contracts.places_FA2_contract.address}
    typename: tezlandPlaces

  tezlandDAO:
    address: ${contracts.dao_FA2_contract.address}
    typename: tezlandDAO

  tezlandWorld:
    address: ${contracts.World_contract.address}
    typename: tezlandWorld

  tezlandMinter:
    address: ${contracts.Minter_contract.address}
    typename: tezlandMinter

  tezlandDutchAuctions:
    address: ${contracts.Dutch_contract.address}
    typename: tezlandDutchAuctions\n`);
    }

    private async gasTestSuite(contracts: PostDeployContracts) {
        assert(this.tezos);

        console.log(kleur.bgGreen("Running gas test suite"));

        const mint_batch = this.tezos.wallet.batch();
        await this.mintNewItem('assets/Duck.glb', 10000, mint_batch, contracts.Minter_contract);
        await this.mintNewPlace([0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]], mint_batch, contracts.Minter_contract);
        const mint_batch_op = await mint_batch.send();
        await mint_batch_op.confirmation();
        console.log();

        const feesToString = async (op: TransactionWalletOperation): Promise<string> => {
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

        // set operator
        const op_op = await contracts.items_FA2_contract.methods.update_operators([{
            add_operator: {
                owner: this.accountAddress,
                operator: contracts.World_contract.address,
                token_id: 0
            }
        }]).send()
        await op_op.confirmation();
        console.log("update_operators:\t" + await feesToString(op_op));

        /**
         * World
         */
        // place one item to make sure storage is set.
        const list_one_item = [{ item: { token_id: 0, token_amount: 1, mutez_per_token: 1, item_data: "ffffffffffffffffffffffffffffff" } }];
        const setup_storage = await contracts.World_contract.methodsObject.place_items({
            lot_id: 0, item_list: list_one_item
        }).send();
        await setup_storage.confirmation();
        console.log("create place (item):\t" + await feesToString(setup_storage));
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
        const place_props_op = await contracts.World_contract.methodsObject.set_place_props({ lot_id: 0, props: "000000" }).send();
        await place_props_op.confirmation();
        console.log("set_place_props:\t" + await feesToString(place_props_op));
        console.log();

        // place one item
        const place_one_item_op = await contracts.World_contract.methodsObject.place_items({
            lot_id: 0, item_list: list_one_item
        }).send();
        await place_one_item_op.confirmation();
        console.log("place_items (1):\t" + await feesToString(place_one_item_op));

        // place ten items
        const list_ten_items = [
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "ffffffffffffffffffffffffffffff" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "ffffffffffffffffffffffffffffff" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "ffffffffffffffffffffffffffffff" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "ffffffffffffffffffffffffffffff" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "ffffffffffffffffffffffffffffff" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "ffffffffffffffffffffffffffffff" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "ffffffffffffffffffffffffffffff" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "ffffffffffffffffffffffffffffff" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "ffffffffffffffffffffffffffffff" } },
            { item: { token_id: 0, token_amount: 1, mutez_per_token: 1000000, item_data: "ffffffffffffffffffffffffffffff" } }
        ];
        const place_ten_items_op = await contracts.World_contract.methodsObject.place_items({
            lot_id: 0, item_list: list_ten_items
        }).send();
        await place_ten_items_op.confirmation();
        console.log("place_items (10):\t" + await feesToString(place_ten_items_op));
        console.log();

        // set one items data
        const map_update_one_item: MichelsonMap<string, object[]> = new MichelsonMap();
        map_update_one_item.set(this.accountAddress!, [{ item_id: 0, item_data: "000000000000000000000000000000" }]);
        const set_item_data_op = await contracts.World_contract.methodsObject.set_item_data({
            lot_id: 0, update_map: map_update_one_item
        }).send();
        await set_item_data_op.confirmation();
        console.log("set_item_data (1):\t" + await feesToString(set_item_data_op));

            // set ten items data
        const map_update_ten_items: MichelsonMap<string, object[]> = new MichelsonMap();
        map_update_ten_items.set(this.accountAddress!, [
            { item_id: 1, item_data: "000000000000000000000000000000" },
            { item_id: 2, item_data: "000000000000000000000000000000" },
            { item_id: 3, item_data: "000000000000000000000000000000" },
            { item_id: 4, item_data: "000000000000000000000000000000" },
            { item_id: 5, item_data: "000000000000000000000000000000" },
            { item_id: 6, item_data: "000000000000000000000000000000" },
            { item_id: 7, item_data: "000000000000000000000000000000" },
            { item_id: 8, item_data: "000000000000000000000000000000" },
            { item_id: 9, item_data: "000000000000000000000000000000" },
            { item_id: 10, item_data: "000000000000000000000000000000" }
        ]);
        const set_ten_items_data_op = await contracts.World_contract.methodsObject.set_item_data({
            lot_id: 0, update_map: map_update_ten_items
        }).send();
        await set_ten_items_data_op.confirmation();
        console.log("set_item_data (10):\t" + await feesToString(set_ten_items_data_op));
        console.log();

        // remove one item
        const map_remove_one_item: MichelsonMap<string, number[]> = new MichelsonMap();
        map_remove_one_item.set(this.accountAddress!, [0]);
        const remove_one_item_op = await contracts.World_contract.methodsObject.remove_items({
            lot_id: 0, remove_map: map_remove_one_item
        }).send();
        await remove_one_item_op.confirmation();
        console.log("remove_items (1):\t" + await feesToString(remove_one_item_op));

        // remove ten items
        const map_remove_ten_items: MichelsonMap<string, number[]> = new MichelsonMap();
        map_remove_ten_items.set(this.accountAddress!, [1,2,3,4,5,6,7,8,9,10]);
        const remove_ten_items_op = await contracts.World_contract.methodsObject.remove_items({
            lot_id: 0, remove_map: map_remove_ten_items
        }).send();
        await remove_ten_items_op.confirmation();
        console.log("remove_items (10):\t" + await feesToString(remove_ten_items_op));
        console.log();

        // set_permissions
        const perm_op = await contracts.World_contract.methods.set_permissions([{
            add_permission: {
                owner: this.accountAddress,
                permittee: contracts.Dutch_contract.address,
                token_id: 0,
                perm: 7
            }
        }]).send()
        await perm_op.confirmation();
        console.log("set_permissions:\t" + await feesToString(perm_op));

        // get item
        const get_item_op = await contracts.World_contract.methodsObject.get_item({
            lot_id: 0, issuer: this.accountAddress, item_id: 11
        }).send({ mutez: true, amount: 1000000 });
        await get_item_op.confirmation();
        console.log("get_item:\t\t" + await feesToString(get_item_op));
        console.log();
        console.log();

        /**
         * Auctions
         */
        // set operator
        const place_op_op = await contracts.places_FA2_contract.methods.update_operators([{
            add_operator: {
                owner: this.accountAddress,
                operator: contracts.Dutch_contract.address,
                token_id: 0
            }
        }]).send()
        await place_op_op.confirmation();
        console.log("update_operators:\t" + await feesToString(place_op_op));

        const whitelist_enable_op = await contracts.Dutch_contract.methodsObject.manage_whitelist([{
            whitelist_enabled: false
        }]).send()
        await whitelist_enable_op.confirmation();
        console.log("manage_whitelist:\t" + await feesToString(whitelist_enable_op));
        console.log();

        let current_time = Math.floor(Date.now() / 1000) + 3;
        const create_auction_op = await contracts.Dutch_contract.methodsObject.create({
            token_id: 0,
            start_price: 200000,
            end_price: 100000,
            start_time: current_time.toString(),
            end_time: (current_time + 2000).toString(),
            fa2: contracts.places_FA2_contract.address
        }).send();
        await create_auction_op.confirmation();
        console.log("create_auction:\t\t" + await feesToString(create_auction_op));
        await sleep(3000);

        const bid_op = await contracts.Dutch_contract.methodsObject.bid(0).send({amount: 200000, mutez: true});
        await bid_op.confirmation();
        console.log("bid:\t\t\t" + await feesToString(bid_op));
        console.log();

        current_time = Math.floor(Date.now() / 1000) + 3;
        const create_auction1_op = await contracts.Dutch_contract.methodsObject.create({
            token_id: 0,
            start_price: 200000,
            end_price: 100000,
            start_time: current_time.toString(),
            end_time: (current_time + 2000).toString(),
            fa2: contracts.places_FA2_contract.address
        }).send();
        await create_auction1_op.confirmation();
        console.log("create_auction:\t\t" + await feesToString(create_auction1_op));
        await sleep(3000);

        const cancel_op = await contracts.Dutch_contract.methodsObject.cancel(1).send();
        await cancel_op.confirmation();
        console.log("cancel:\t\t\t" + await feesToString(cancel_op));
    }

    private async mintAndPlace(contracts: PostDeployContracts, per_batch: number = 100, batches: number = 30, token_id: number = 0) {
        assert(this.tezos);

        console.log(kleur.bgGreen("Single Place stress test: " + token_id));

        const mint_batch = this.tezos.wallet.batch();
        await this.mintNewItem('assets/Duck.glb', 10000, mint_batch, contracts.Minter_contract);
        await this.mintNewPlace([0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]], mint_batch, contracts.Minter_contract);
        const mint_batch_op = await mint_batch.send();
        await mint_batch_op.confirmation();

        // set operator
        const op_op = await contracts.items_FA2_contract.methods.update_operators([{
            add_operator: {
                owner: this.accountAddress,
                operator: contracts.World_contract.address,
                token_id: token_id
            }
        }]).send()
        await op_op.confirmation();

        const item_list = [];
        for (let i = 0; i < per_batch; ++i)
            item_list.push({ item: { token_id: token_id, token_amount: 1, mutez_per_token: 1000000, item_data: "ffffffffffffffffffffffffffffff" } });

        for (let i = 0; i < batches; ++i) {
            console.log("Placing batch: ", i + 1);
            const place_ten_items_op = await contracts.World_contract.methodsObject.place_items({
                lot_id: token_id, item_list: item_list
            }).send();
            await place_ten_items_op.confirmation();
        }

        /*const place_items_op = await contracts.World_contract.methodsObject.place_items({
            lot_id: token_id, item_list: [{ item: { token_id: token_id, token_amount: 1, mutez_per_token: 1000000, item_data: "ffffffffffffffffffffffffffffff" } }]
        }).send();
        await place_items_op.confirmation();

        const map_update_one_item: MichelsonMap<string, object[]> = new MichelsonMap();
        map_update_one_item.set(this.accountAddress!, [{ item_id: 0, item_data: "000000000000000000000000000000" }]);
        const set_item_data_op = await contracts.World_contract.methodsObject.set_item_data({
            lot_id: token_id, update_map: map_update_one_item
        }).send();
        await set_item_data_op.confirmation();*/
    }

    private async stressTestSingle(contracts: PostDeployContracts, per_batch: number = 100, batches: number = 30, token_id: number = 0) {
        const set_item_limit_op = await contracts.World_contract.methodsObject.update_item_limit(10000).send();
        await set_item_limit_op.confirmation();

        this.mintAndPlace(contracts);
    }

    private async stressTestMulti(contracts: PostDeployContracts) {
        const set_item_limit_op = await contracts.World_contract.methodsObject.update_item_limit(10000).send();
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
