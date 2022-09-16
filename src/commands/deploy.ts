import * as smartpy from './smartpy';
import * as ipfs from '../ipfs'
import { char2Bytes } from '@taquito/utils'
import assert from 'assert';
import kleur from 'kleur';
import DeployBase, { DeployContractBatch, sleep } from './DeployBase';
import { ContractAbstraction, MichelsonMap, OpKind, TransactionWalletOperation, Wallet, WalletOperationBatch } from '@taquito/taquito';
import config from '../user.config';
import fs from 'fs';
import { BatchWalletOperation } from '@taquito/taquito/dist/types/wallet/batch-operation';


enum DeployMode { None, DevWorld, GasTest, StressTestSingle, StressTestMulti };

type PostDeployContracts = {
    items_FA2_contract: ContractAbstraction<Wallet>,
    places_FA2_contract: ContractAbstraction<Wallet>,
    dao_FA2_contract: ContractAbstraction<Wallet>,
    Minter_contract: ContractAbstraction<Wallet>,
    World_contract: ContractAbstraction<Wallet>,
    Dutch_contract: ContractAbstraction<Wallet>,
    interiors_FA2_contract: ContractAbstraction<Wallet>,
}

// TODO: finish this stuff!
// some issues: dependent transactions: setting adming, etc
export default class Deploy extends DeployBase {
    // Compiles metadata, uploads it and then compiles again with metadata set.
    // Note: target_args needs to exclude metadata.
    private async compile_contract(target_name: string, file_name: string, contract_name: string, target_args: string[], metadata?: ipfs.ContractMetadata) {
        var metadata_url;
        if (metadata === undefined) {
            // Compile metadata
            smartpy.compile_metadata(target_name, file_name, contract_name, target_args.concat(['metadata = sp.utils.metadata_of_url("metadata_dummy")']));

            const metadtaFile = `${target_name}_metadata.json`;
            const metadtaPath = `./build/${metadtaFile}`;
            const contract_metadata = JSON.parse(fs.readFileSync(metadtaPath, { encoding: 'utf-8' }));

            metadata_url = await ipfs.upload_metadata(contract_metadata, this.isSandboxNet);
        }
        else {
            metadata_url = await ipfs.upload_contract_metadata(metadata, this.isSandboxNet);
        }

        // Compile contract with metadata set.
        smartpy.compile_newtarget(target_name, file_name, contract_name, target_args.concat([`metadata = sp.utils.metadata_of_url("${metadata_url}")`]));
    }

    protected override async deployDo() {
        assert(this.tezos);

        // prepare batch
        const daoWasDeployed = this.getDeployment("FA2_DAO");

        const fa2_batch = new DeployContractBatch(this);

        //
        // Items
        //
        await this.compile_contract("FA2_Items", "Tokens", "tz1andItems", [
            `admin = sp.address("${this.accountAddress}")`
        ]);

        fa2_batch.addToBatch("FA2_Items");

        //
        // Places
        //
        await this.compile_contract("FA2_Places", "Tokens", "tz1andPlaces", [
            `admin = sp.address("${this.accountAddress}")`
        ]);

        fa2_batch.addToBatch("FA2_Places");

        //
        // Interiors
        //
        await this.compile_contract("FA2_Interiors", "Tokens", "tz1andInteriors", [
            `admin = sp.address("${this.accountAddress}")`
        ]);

        fa2_batch.addToBatch("FA2_Interiors");

        //
        // DAO
        //
        await this.compile_contract("FA2_DAO", "Tokens", "tz1andDAO", [
            `admin = sp.address("${this.accountAddress}")`
        ]);

        fa2_batch.addToBatch("FA2_DAO");

        // send batch.
        const [items_FA2_contract, places_FA2_contract, interiors_FA2_contract, dao_FA2_contract] = await fa2_batch.deployBatch();

        if(!daoWasDeployed) {
            // Mint 0 dao.
            console.log("Minting dao tokens")
            const tokenMetadataMap = new MichelsonMap();
            tokenMetadataMap.set("decimals", char2Bytes("6"));
            tokenMetadataMap.set("name", char2Bytes("tz1and DAO"));
            tokenMetadataMap.set("symbol", char2Bytes("tz1aDAO"));

            const dao_mint_op = await dao_FA2_contract.methodsObject.mint([{
                to_: this.accountAddress,
                amount: 0,
                token: { new: tokenMetadataMap }
            }]).send();
            await dao_mint_op.confirmation();

            console.log("Successfully minted 0 DAO");
            console.log(`>> Transaction hash: ${dao_mint_op.opHash}\n`);
        }

        //
        // Minter
        //
        const minterWasDeployed = this.getDeployment("TL_Minter");

        // prepare minter/dutch batch
        const tezland_batch = new DeployContractBatch(this);

        // Compile and deploy Minter contract.
        await this.compile_contract("TL_Minter", "TL_Minter", "TL_Minter", [
            `administrator = sp.address("${this.accountAddress}")`,
            `items_contract = sp.address("${items_FA2_contract.address}")`,
            `places_contract = sp.address("${places_FA2_contract.address}")`
        ]);

        tezland_batch.addToBatch("TL_Minter");
        //const Minter_contract = await this.deploy_contract("TL_Minter");

        //
        // Dutch
        //
        // Compile and deploy Dutch auction contract.
        await this.compile_contract("TL_Dutch", "TL_Dutch", "TL_Dutch", [
            `administrator = sp.address("${this.accountAddress}")`,
            `items_contract = sp.address("${items_FA2_contract.address}")`,
            `places_contract = sp.address("${places_FA2_contract.address}")`
        ]);

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
        // Compile and deploy Places contract.
        // IMPORTANT NOTE: target name changed so on next mainnet deply it will automatically deploy the v2!
        await this.compile_contract("TL_World_v2", "Worlds", "tz1andWorld", [
            `administrator = sp.address("${this.accountAddress}")`,
            `items_contract = sp.address("${items_FA2_contract.address}")`,
            `places_contract = sp.address("${places_FA2_contract.address}")`
        ]);

        const World_contract = await this.deploy_contract("TL_World_v2");

        console.log("Set allowed place tokens on world...")
        const allowed_places_op = await World_contract.methodsObject.set_allowed_place_token([
            {
                add_allowed_place_token: places_FA2_contract.address
            },
            {
                add_allowed_place_token: interiors_FA2_contract.address
            }
        ]).send();
        await allowed_places_op.confirmation();
        console.log("Successfully set allowed places on world");
        console.log(`>> Transaction hash: ${allowed_places_op.opHash}\n`);

        //
        // Post deploy
        //
        // If this is a sandbox deploy, run the post deploy tasks.
        const post_deploy = this.isSandboxNet ? DeployMode.GasTest : DeployMode.None;

        await this.runPostDeply(post_deploy, {
            items_FA2_contract: items_FA2_contract,
            places_FA2_contract: places_FA2_contract,
            dao_FA2_contract: dao_FA2_contract,
            Minter_contract: Minter_contract,
            World_contract: World_contract,
            Dutch_contract: Dutch_contract,
            interiors_FA2_contract: interiors_FA2_contract
        });
    }

    private async runPostDeply(
        deploy_mode: DeployMode,
        contracts: PostDeployContracts) {

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
            console.log("REACT_APP_ITEM_CONTRACT=" + contracts.items_FA2_contract.address);
            console.log("REACT_APP_PLACE_CONTRACT=" + contracts.places_FA2_contract.address);
            console.log("REACT_APP_DAO_CONTRACT=" + contracts.dao_FA2_contract.address);
            console.log("REACT_APP_WORLD_CONTRACT=" + contracts.World_contract.address);
            console.log("REACT_APP_MINTER_CONTRACT=" + contracts.Minter_contract.address);
            console.log("REACT_APP_DUTCH_AUCTION_CONTRACT=" + contracts.Dutch_contract.address);
            console.log("REACT_APP_INTERIORS_CONTRACT=" + contracts.interiors_FA2_contract.address);
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
    typename: tezlandDutchAuctions
    
  tezlandInteriors:
    address: ${contracts.interiors_FA2_contract.address}
    typename: tezlandPlaces\n`);
    }
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

    private mintNewInteriorPlaces(mint_args: any[], batch: WalletOperationBatch, interiors_FA2_contract: ContractAbstraction<Wallet>) {
        batch.with([{
            kind: OpKind.TRANSACTION,
            ...interiors_FA2_contract.methodsObject.mint(
                mint_args
            ).toTransferParams()
        }]);
    }

    private async prepareNewPlace(center: number[], border: number[][]): Promise<any> {
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

        const metadata_map = new MichelsonMap<string,string>({ prim: "map", args: [{prim: "string"}, {prim: "bytes"}]});
        metadata_map.set('', Buffer.from(place_metadata_url, 'utf8').toString('hex'));
        return {
            to_: this.accountAddress,
            metadata: metadata_map
        }
    }

    private async prepareNewInteriorPlace(center: number[], border: number[][]): Promise<any> {
        const place_metadata_url = await ipfs.upload_place_metadata({
            name: "Interior Place",
            description: "A nice place",
            minter: this.accountAddress!,
            centerCoordinates: center,
            borderCoordinates: border,
            buildHeight: 200,
            placeType: "interior"
        }, this.isSandboxNet);
        console.log(`interior place token metadata: ${place_metadata_url}`);

        const metadata_map = new MichelsonMap<string,string>({ prim: "map", args: [{prim: "string"}, {prim: "bytes"}]});
        metadata_map.set('', Buffer.from(place_metadata_url, 'utf8').toString('hex'));
        return {
            to_: this.accountAddress,
            metadata: metadata_map
        }
    }

    private async deployDevWorld(contracts: PostDeployContracts) {
        assert(this.tezos);

        console.log(kleur.bgGreen("Deploying dev world"));

        // prepare batch
        const mint_batch = this.tezos.wallet.batch();

        await this.mintNewItem('assets/Lantern.glb', 5394, 100, mint_batch, contracts.Minter_contract);
        await this.mintNewItem('assets/Fox.glb', 576, 25, mint_batch, contracts.Minter_contract);
        await this.mintNewItem('assets/Duck.glb', 4212, 75, mint_batch, contracts.Minter_contract);
        await this.mintNewItem('assets/DragonAttenuation.glb', 134995, 66, mint_batch, contracts.Minter_contract);

        // don't mint places for now. use generate map.
        const places = [];
        places.push(await this.prepareNewPlace([0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]]));
        places.push(await this.prepareNewPlace([22, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]]));
        places.push(await this.prepareNewPlace([22, 0, -22], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]]));
        places.push(await this.prepareNewPlace([0, 0, -25], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10], [0, 0, 14]]));
        this.mintNewPlaces(places, mint_batch, contracts.Minter_contract);

        const interior_places = [];
        interior_places.push(await this.prepareNewInteriorPlace([0, 0, 0], [[100, 0, 100], [100, 0, -100], [-100, 0, -100], [-100, 0, 100]]));
        interior_places.push(await this.prepareNewInteriorPlace([0, 0, 0], [[100, 0, 100], [100, 0, -100], [-100, 0, -100], [-100, 0, 100]]));
        interior_places.push(await this.prepareNewInteriorPlace([0, 0, 0], [[100, 0, 100], [100, 0, -100], [-100, 0, -100], [-100, 0, 100]]));
        interior_places.push(await this.prepareNewInteriorPlace([0, 0, 0], [[100, 0, 100], [100, 0, -100], [-100, 0, -100], [-100, 0, 100]]));
        this.mintNewInteriorPlaces(interior_places, mint_batch, contracts.interiors_FA2_contract);

        // send batch.
        const mint_batch_op = await mint_batch.send();
        await mint_batch_op.confirmation();

        console.log("Successfully minted items");
        console.log(`>> Transaction hash: ${mint_batch_op.opHash}\n`);
    }

    private async feesToString (op: TransactionWalletOperation|BatchWalletOperation): Promise<string> {
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

    private async gasTestSuite(contracts: PostDeployContracts) {
        assert(this.tezos);
        //assert(this.accountAddress);

        console.log(kleur.bgGreen("Running gas test suite"));

        const mint_batch = this.tezos.wallet.batch();
        await this.mintNewItem('assets/Duck.glb', 4212, 10000, mint_batch, contracts.Minter_contract);
        this.mintNewPlaces([await this.prepareNewPlace([0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]])], mint_batch, contracts.Minter_contract);
        this.mintNewPlaces([await this.prepareNewPlace([0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]])], mint_batch, contracts.Minter_contract);
        const mint_batch_op = await mint_batch.send();
        await mint_batch_op.confirmation();
        console.log();

        // set operator
        const op_op = await contracts.items_FA2_contract.methods.update_operators([{
            add_operator: {
                owner: this.accountAddress,
                operator: contracts.World_contract.address,
                token_id: 0
            }
        }]).send()
        await op_op.confirmation();
        console.log("update_operators:\t" + await this.feesToString(op_op));

        const placeKey0 = { place_contract: contracts.places_FA2_contract.address, lot_id: 0 };
        const placeKey1 = { place_contract: contracts.places_FA2_contract.address, lot_id: 1 };

        /**
         * World
         */
        // place one item to make sure storage is set.
        const list_one_item: MichelsonMap<string, object[]> = new MichelsonMap();
        list_one_item.set(contracts.items_FA2_contract.address, [{ item: { token_id: 0, token_amount: 1, mutez_per_token: 1, item_data: "ffffffffffffffffffffffffffffff" } }]);
        const setup_storage = await contracts.World_contract.methodsObject.place_items({
            place_key: placeKey0, place_item_map: list_one_item
        }).send();
        await setup_storage.confirmation();
        console.log("create place 0 (item):\t" + await this.feesToString(setup_storage));

        // NOTE: for some reason the first created place is more expensive? some weird storage diff somewhere...
        const setup_storage1 = await contracts.World_contract.methodsObject.place_items({
            place_key: placeKey1, place_item_map: list_one_item
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
        const creat_op = await World_contract.methodsObject.set_place_props({ place_key: placeKey0, props: "ffffff" }).send();
        await creat_op.confirmation();
        console.log("create place (props):\t" + await feesToString(creat_op));*/

        // place props
        const props_map = new MichelsonMap<string, string>();
        props_map.set('00', '000000');
        const place_props_op = await contracts.World_contract.methodsObject.set_place_props({ place_key: placeKey0, props: props_map }).send();
        await place_props_op.confirmation();
        console.log("set_place_props:\t" + await this.feesToString(place_props_op));
        console.log();

        // place one item
        const place_one_item_op = await contracts.World_contract.methodsObject.place_items({
            place_key: placeKey0, place_item_map: list_one_item
        }).send();
        await place_one_item_op.confirmation();
        console.log("place_items (1):\t" + await this.feesToString(place_one_item_op));

        // place ten items
        const list_ten_items: MichelsonMap<string, object[]> = new MichelsonMap();
        list_ten_items.set (contracts.items_FA2_contract.address, [
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
        ]);
        const place_ten_items_op = await contracts.World_contract.methodsObject.place_items({
            place_key: placeKey0, place_item_map: list_ten_items
        }).send();
        await place_ten_items_op.confirmation();
        console.log("place_items (10):\t" + await this.feesToString(place_ten_items_op));
        console.log();

        // set one items data
        const map_update_one_item_issuer: MichelsonMap<string, MichelsonMap<string, object[]>> = new MichelsonMap();
        const map_update_one_item_token: MichelsonMap<string, object[]> = new MichelsonMap();
        map_update_one_item_token.set(contracts.items_FA2_contract.address, [{ item_id: 0, item_data: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }]);
        map_update_one_item_issuer.set(this.accountAddress!, map_update_one_item_token);
        const set_item_data_op = await contracts.World_contract.methodsObject.set_item_data({
            place_key: placeKey0, update_map: map_update_one_item_issuer
        }).send();
        await set_item_data_op.confirmation();
        console.log("set_item_data (1):\t" + await this.feesToString(set_item_data_op));

            // set ten items data
        const map_update_ten_items_issuer: MichelsonMap<string, MichelsonMap<string, object[]>> = new MichelsonMap();
        const map_update_ten_items_token: MichelsonMap<string, object[]> = new MichelsonMap();
        map_update_ten_items_token.set(contracts.items_FA2_contract.address, [
            { item_id: 1, item_data: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" },
            { item_id: 2, item_data: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" },
            { item_id: 3, item_data: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" },
            { item_id: 4, item_data: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" },
            { item_id: 5, item_data: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" },
            { item_id: 6, item_data: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" },
            { item_id: 7, item_data: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" },
            { item_id: 8, item_data: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" },
            { item_id: 9, item_data: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" },
            { item_id: 10, item_data: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
        ]);
        map_update_ten_items_issuer.set(this.accountAddress!, map_update_ten_items_token);
        const set_ten_items_data_op = await contracts.World_contract.methodsObject.set_item_data({
            place_key: placeKey0, update_map: map_update_ten_items_issuer
        }).send();
        await set_ten_items_data_op.confirmation();
        console.log("set_item_data (10):\t" + await this.feesToString(set_ten_items_data_op));
        console.log();

        // remove one item
        const map_remove_one_item_issuer: MichelsonMap<string, MichelsonMap<string, number[]>> = new MichelsonMap();
        const map_remove_one_item_token: MichelsonMap<string, number[]> = new MichelsonMap();
        map_remove_one_item_token.set(contracts.items_FA2_contract.address, [0]);
        map_remove_one_item_issuer.set(this.accountAddress!, map_remove_one_item_token);
        const remove_one_item_op = await contracts.World_contract.methodsObject.remove_items({
            place_key: placeKey0, remove_map: map_remove_one_item_issuer
        }).send();
        await remove_one_item_op.confirmation();
        console.log("remove_items (1):\t" + await this.feesToString(remove_one_item_op));

        // remove ten items
        const map_remove_ten_items_issuer: MichelsonMap<string, MichelsonMap<string, number[]>> = new MichelsonMap();
        const map_remove_ten_items_token: MichelsonMap<string, number[]> = new MichelsonMap();
        map_remove_ten_items_token.set(contracts.items_FA2_contract.address, [1,2,3,4,5,6,7,8,9,10]);
        map_remove_ten_items_issuer.set(this.accountAddress!, map_remove_ten_items_token);
        const remove_ten_items_op = await contracts.World_contract.methodsObject.remove_items({
            place_key: placeKey0, remove_map: map_remove_ten_items_issuer
        }).send();
        await remove_ten_items_op.confirmation();
        console.log("remove_items (10):\t" + await this.feesToString(remove_ten_items_op));
        console.log();

        // set_permissions
        const perm_op = await contracts.World_contract.methods.set_permissions([{
            add_permission: {
                place_key: placeKey0,
                owner: this.accountAddress,
                permittee: contracts.Dutch_contract.address,
                perm: 7
            }
        }]).send()
        await perm_op.confirmation();
        console.log("set_permissions:\t" + await this.feesToString(perm_op));

        // get item
        const get_item_op = await contracts.World_contract.methodsObject.get_item({
            place_key: placeKey0, issuer: this.accountAddress, fa2: contracts.items_FA2_contract.address, item_id: 11
        }).send({ mutez: true, amount: 1000000 });
        await get_item_op.confirmation();
        console.log("get_item:\t\t" + await this.feesToString(get_item_op));
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
        console.log("update_operators:\t" + await this.feesToString(place_op_op));

        const whitelist_enable_op = await contracts.Dutch_contract.methodsObject.manage_whitelist([{
            whitelist_enabled: false
        }]).send()
        await whitelist_enable_op.confirmation();
        console.log("manage_whitelist:\t" + await this.feesToString(whitelist_enable_op));
        console.log();

        let current_time = Math.floor(Date.now() / 1000) + config.sandbox.blockTime;
        const create_auction_op = await contracts.Dutch_contract.methodsObject.create({
            token_id: 0,
            start_price: 200000,
            end_price: 100000,
            start_time: current_time.toString(),
            end_time: (current_time + 2000).toString(),
            fa2: contracts.places_FA2_contract.address
        }).send();
        await create_auction_op.confirmation();
        console.log("create_auction:\t\t" + await this.feesToString(create_auction_op));
        await sleep(config.sandbox.blockTime * 1000);

        const bid_op = await contracts.Dutch_contract.methodsObject.bid({auction_id: 0}).send({amount: 200000, mutez: true});
        await bid_op.confirmation();
        console.log("bid:\t\t\t" + await this.feesToString(bid_op));
        console.log();

        current_time = Math.floor(Date.now() / 1000) + config.sandbox.blockTime;
        const create_auction1_op = await contracts.Dutch_contract.methodsObject.create({
            token_id: 0,
            start_price: 200000,
            end_price: 100000,
            start_time: current_time.toString(),
            end_time: (current_time + 2000).toString(),
            fa2: contracts.places_FA2_contract.address
        }).send();
        await create_auction1_op.confirmation();
        console.log("create_auction:\t\t" + await this.feesToString(create_auction1_op));
        await sleep(config.sandbox.blockTime * 1000);

        const cancel_op = await contracts.Dutch_contract.methodsObject.cancel({auction_id: 1}).send();
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
                    operator: contracts.Minter_contract.address,
                    token_id: n
                }
            });
        const op_alot_op = await contracts.items_FA2_contract.methods.update_operators(
            op_alot
        ).send()
        await op_alot_op.confirmation();
        console.log("update_operators (100):\t\t" + await this.feesToString(op_alot_op));
        console.log();

        // token transfer
        const transfer_before_op = await contracts.items_FA2_contract.methodsObject.transfer([{
            from_: this.accountAddress,
            txs: [{
                to_: contracts.Minter_contract.address,
                amount: 1,
                token_id: 0
            }]
        }]).send();
        await transfer_before_op.confirmation();
        console.log("transfer:\t\t\t" + await this.feesToString(transfer_before_op));

        // set adhoc operators
        const item_adhoc_op_op = await contracts.items_FA2_contract.methodsObject.update_adhoc_operators({
            add_adhoc_operators: [{
                operator: contracts.Minter_contract.address,
                token_id: 0
            }]
        }).send()
        await item_adhoc_op_op.confirmation();
        console.log("update_adhoc_operators:\t\t" + await this.feesToString(item_adhoc_op_op));

        // set max adhoc operators
        const adhoc_ops = [];
        for (const n of [...Array(100).keys()])
            adhoc_ops.push({
                operator: contracts.Minter_contract.address,
                token_id: n
            });
        const item_adhoc_max_op = contracts.items_FA2_contract.methodsObject.update_adhoc_operators({
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
        const transfer_after_op = await contracts.items_FA2_contract.methodsObject.transfer([{
            from_: this.accountAddress,
            txs: [{
                to_: contracts.Minter_contract.address,
                amount: 1,
                token_id: 0
            }]
        }]).send();
        await transfer_after_op.confirmation();
        console.log("transfer (100 adhoc):\t\t" + await this.feesToString(transfer_after_op));

        // set adhoc operators
        const item_adhoc_after_op = await contracts.items_FA2_contract.methodsObject.update_adhoc_operators({
            add_adhoc_operators: [{
                operator: contracts.Minter_contract.address,
                token_id: 0
            }]
        }).send()
        await item_adhoc_after_op.confirmation();
        console.log("update_adhoc_operators (reset):\t" + await this.feesToString(item_adhoc_after_op));

        // final transfer after adhoc reset
        const transfer_final_op = await contracts.items_FA2_contract.methodsObject.transfer([{
            from_: this.accountAddress,
            txs: [{
                to_: contracts.Minter_contract.address,
                amount: 1,
                token_id: 0
            }]
        }]).send();
        await transfer_final_op.confirmation();
        console.log("transfer (reset):\t\t" + await this.feesToString(transfer_final_op));
        console.log();

        // mint again
        const mint_batch2 = this.tezos.wallet.batch();
        await this.mintNewItem('assets/Duck.glb', 4212, 10000, mint_batch2, contracts.Minter_contract);
        await this.mintNewItem('assets/Duck.glb', 4212, 10000, mint_batch2, contracts.Minter_contract);
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
        await this.mintNewItem('assets/Duck.glb', 4212, 10000, mint_batch, contracts.Minter_contract);
        this.mintNewPlaces([await this.prepareNewPlace([0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]])], mint_batch, contracts.Minter_contract);
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

        const item_map: MichelsonMap<string, object[]> = new MichelsonMap();
        item_map.set(contracts.items_FA2_contract.address, item_list)

        for (let i = 0; i < batches; ++i) {
            console.log("Placing batch: ", i + 1);
            const place_ten_items_op = await contracts.World_contract.methodsObject.place_items({
                place_key: {place_contract: contracts.places_FA2_contract.address, lot_id: token_id }, place_item_map: item_map
            }).send();
            await place_ten_items_op.confirmation();
            console.log("place_items:\t" + await this.feesToString(place_ten_items_op));
        }

        /*const place_items_op = await contracts.World_contract.methodsObject.place_items({
            lot_id: token_id, place_item_map: michelsonmap... [{ item: { token_id: token_id, token_amount: 1, mutez_per_token: 1000000, item_data: "ffffffffffffffffffffffffffffff" } }]
        }).send();
        await place_items_op.confirmation();

        const map_update_one_item: MichelsonMap<string, object[]> = new MichelsonMap();
        map_update_one_item.set(this.accountAddress!, [{ item_id: 0, item_data: "000000000000000000000000000000" }]);
        const set_item_data_op = await contracts.World_contract.methodsObject.set_item_data({
            lot_id: token_id, update_map: map_update_one_item
        }).send();
        await set_item_data_op.confirmation();
        console.log("set_item_data:\t" + await this.feesToString(set_item_data_op));*/
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
