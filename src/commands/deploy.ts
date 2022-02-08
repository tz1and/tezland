import * as smartpy from './smartpy';
import * as ipfs from '../ipfs'
import { char2Bytes } from '@taquito/utils'
import assert from 'assert';
import kleur from 'kleur';
import DeployBase, { DeployContractBatch } from './DeployBase';
import { MichelsonMap, OpKind, WalletOperationBatch } from '@taquito/taquito';


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
        // Minter can't be batched because others depend on it.
        //

        const minterWasDeployed = this.getDeployment("TL_Minter");

        const minter_metadata_url = await ipfs.upload_contract_metadata({
            name: 'tz1and Minter',
            description: 'tz1and Items and Places minter',
            interfaces: [],
            version: '1.0.0'
        }, this.isSandboxNet);

        // Compile and deploy Minter contract.
        smartpy.compile_newtarget("TL_Minter", "TL_Minter", [`manager = sp.address("${this.accountAddress}")`,
        `items_contract = sp.address("${items_FA2_contract.address}")`,
        `places_contract = sp.address("${places_FA2_contract.address}")`,
        `metadata = sp.utils.metadata_of_url("${minter_metadata_url}")`]);

        const Minter_contract = await this.deploy_contract("TL_Minter");

        if (!minterWasDeployed) {
            // Set the minter as the token administrator
            console.log("Setting minter as token admin...")
            const set_admin_batch = this.tezos.wallet.batch();
            set_admin_batch.with([
                {
                    kind: OpKind.TRANSACTION,
                    ...items_FA2_contract.methods.set_administrator(Minter_contract.address).toTransferParams()
                },
                {
                    kind: OpKind.TRANSACTION,
                    ...places_FA2_contract.methods.set_administrator(Minter_contract.address).toTransferParams()
                }
            ])

            const set_admin_batch_op = await set_admin_batch.send();
            await set_admin_batch_op.confirmation();

            console.log("Successfully set minter as tokens admin");
            console.log(`>> Transaction hash: ${set_admin_batch_op.opHash}\n`);
        }

        const worldWasDeployed = this.getDeployment("TL_World");

        // prepare others batch
        const tezland_batch = new DeployContractBatch(this);

        //
        // World (Marketplaces)
        //
        const world_metadata_url = await ipfs.upload_contract_metadata({
            name: 'tz1and World',
            description: 'tz1and Virtual World',
            interfaces: [],
            version: '1.0.0'
        }, this.isSandboxNet);

        // Compile and deploy Places contract.
        smartpy.compile_newtarget("TL_World", "TL_World", [`manager = sp.address("${this.accountAddress}")`,
        `items_contract = sp.address("${items_FA2_contract.address}")`,
        `places_contract = sp.address("${places_FA2_contract.address}")`,
        `minter = sp.address("${Minter_contract.address}")`,
        `dao_contract = sp.address("${dao_FA2_contract.address}")`,
        `terminus = sp.timestamp(${Math.floor(Date.now() / 1000)}).add_days(60)`,
        `metadata = sp.utils.metadata_of_url("${world_metadata_url}")`]);

        tezland_batch.addToBatch("TL_World");

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
        smartpy.compile_newtarget("TL_Dutch", "TL_Dutch", [`manager = sp.address("${this.accountAddress}")`,
        `items_contract = sp.address("${items_FA2_contract.address}")`,
        `places_contract = sp.address("${places_FA2_contract.address}")`,
        `minter = sp.address("${Minter_contract.address}")`,
        `metadata = sp.utils.metadata_of_url("${dutch_metadata_url}")`]);

        tezland_batch.addToBatch("TL_Dutch");

        const [World_contract, Dutch_contract] = await tezland_batch.deployBatch();

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
                    ...dao_FA2_contract.methods.set_administrator(World_contract.address).toTransferParams()
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

            const mintNewItem = async (model_path: string, amount: number, batch: WalletOperationBatch) => {
                // Create item metadata and upload it
                const item_metadata_url = await ipfs.upload_item_metadata(Minter_contract.address, model_path, this.isSandboxNet);
                console.log(`item token metadata: ${item_metadata_url}`);

                batch.with([{
                    kind: OpKind.TRANSACTION,
                    ...Minter_contract.methodsObject.mint_Item({
                        address: this.accountAddress,
                        amount: amount,
                        royalties: 250,
                        metadata: Buffer.from(item_metadata_url, 'utf8').toString('hex')
                    }).toTransferParams()
                }]);
            }

            // Create place metadata and upload it
            const mintNewPlace = async (center: number[], border: number[][], batch: WalletOperationBatch) => {
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

            // prepare batch
            const mint_batch = this.tezos.wallet.batch();

            await mintNewItem('assets/Lantern.glb', 100, mint_batch);
            await mintNewItem('assets/Fox.glb', 25, mint_batch);
            await mintNewItem('assets/Duck.glb', 75, mint_batch);
            await mintNewItem('assets/DragonAttenuation.glb', 66, mint_batch);

            // don't mint places for now. use generate map.
            await mintNewPlace([0, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]], mint_batch);
            await mintNewPlace([22, 0, 0], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]], mint_batch);
            await mintNewPlace([22, 0, -22], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10]], mint_batch);
            await mintNewPlace([0, 0, -25], [[10, 0, 10], [10, 0, -10], [-10, 0, -10], [-10, 0, 10], [0, 0, 14]], mint_batch);

            // send batch.
            const mint_batch_op = await mint_batch.send();
            await mint_batch_op.confirmation();

            console.log("Successfully minted items");
            console.log(`>> Transaction hash: ${mint_batch_op.opHash}\n`);
        }

        // TODO: create deployments folder and write to it

        console.log("REACT_APP_ITEM_CONTRACT=" + items_FA2_contract.address);
        console.log("REACT_APP_PLACE_CONTRACT=" + places_FA2_contract.address);
        console.log("REACT_APP_DAO_CONTRACT=" + dao_FA2_contract.address);
        console.log("REACT_APP_WORLD_CONTRACT=" + World_contract.address);
        console.log("REACT_APP_MINTER_CONTRACT=" + Minter_contract.address);
        console.log("REACT_APP_DUTCH_AUCTION_CONTRACT=" + Dutch_contract.address);
        console.log()
        console.log(`contracts:
  tezlandItems:
    address: ${items_FA2_contract.address}
    typename: tezlandItems

  tezlandPlaces:
    address: ${places_FA2_contract.address}
    typename: tezlandPlaces

  tezlandDAO:
    address: ${dao_FA2_contract.address}
    typename: tezlandDAO

  tezlandWorld:
    address: ${World_contract.address}
    typename: tezlandWorld

  tezlandMinter:
    address: ${Minter_contract.address}
    typename: tezlandMinter

  tezlandDutchAuctions:
    address: ${Dutch_contract.address}
    typename: tezlandDutchAuctions\n`);
    }
}
