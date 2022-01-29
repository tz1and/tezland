import * as smartpy from './smartpy';
import { TezosToolkit, ContractAbstraction, ContractProvider, WalletOperationBatch, OpKind, MichelsonMap } from "@taquito/taquito";
import { InMemorySigner } from "@taquito/signer";
import * as ipfs from '../ipfs'
import { OperationContentsAndResultOrigination } from '@taquito/rpc';
import { BatchWalletOperation } from '@taquito/taquito/dist/types/wallet/batch-operation';
import { char2Bytes } from '@taquito/utils'
import { performance } from 'perf_hooks';
import config from '../user.config';
import assert from 'assert';
import kleur from 'kleur';


async function deploy_contract(contract_name: string, Tezos: TezosToolkit): Promise<ContractAbstraction<ContractProvider>> {
    var orig_op = await Tezos.contract.originate({
        code: require(`../../build/${contract_name}.json`),
        init: require(`../../build/${contract_name}_storage.json`),
    });

    var contract = await orig_op.contract();

    console.log(`Successfully deployed contract ${contract_name}`);
    console.log(`>> Transaction hash: ${orig_op.hash}`);
    console.log(`>> Contract address: ${contract.address}\n`);

    return contract;
};

function deploy_contract_batch(contract_name: string, batch: WalletOperationBatch) {
    batch.withOrigination({
        code: require(`../../build/${contract_name}.json`),
        init: require(`../../build/${contract_name}_storage.json`),
    });
};

// NOTE: only works with single origination per op
async function get_originated_contracts_batch(batch_op: BatchWalletOperation, Tezos: TezosToolkit): Promise<ContractAbstraction<ContractProvider>[]> {
    const contracts = [];

    console.log(`Successfully deployed contracts in batch`);
    console.log(`>> Transaction hash: ${batch_op.opHash}`);

    var results = await batch_op.operationResults();
    for (const res of results) {
        if (res.kind === OpKind.ORIGINATION) {
            const orig_res = res as OperationContentsAndResultOrigination;

            // TODO: check if exists
            const contract_address = orig_res.metadata.operation_result!.originated_contracts![0];

            console.log(`>> Contract address: ${contract_address}`);

            contracts.push(
                await Tezos.contract.at(contract_address)
            );
        }
    }

    console.log();

    return contracts;
}

export async function deploy(options: any): Promise<void> {
    // TODO: have this in some helper function.
    if(!options.network) options.network = config.defaultNetwork;
    const networkConfig = config.networks[options.network];
    assert(networkConfig, `Network config not found for '${options.network}'`);
    const deployerKey = networkConfig.accounts.deployer;
    assert(networkConfig.accounts, `deployer account not set for '${options.network}'`)

    console.log(kleur.red(`Deploying to '${networkConfig.network}' on ${networkConfig.url} ...\n`));

    try {
        const start_time = performance.now();

        const signer = await InMemorySigner.fromSecretKey(deployerKey);
        const Tezos = new TezosToolkit(networkConfig.url);
        Tezos.setProvider({ signer: signer });

        const accountAddress = await signer.publicKeyHash();

        // prepare batch
        const fa2_batch = Tezos.wallet.batch();

        //
        // Items
        //
        const items_metadata_url = await ipfs.upload_contract_metadata({
            name: 'tz1aND Items',
            description: 'tz1aND Item FA2 tokens',
            interfaces: ["TZIP-12"],
            version: '1.0.0'
        }, true);

        // Compile and deploy Items FA2 contract.
        smartpy.compile_newtarget("FA2_Items", "FA2", ['config = FA2_contract.items_config()',
            `metadata = sp.utils.metadata_of_url("${items_metadata_url}")`,
            `admin = sp.address("${accountAddress}")`]);

        deploy_contract_batch("FA2_Items", fa2_batch);

        //
        // Places
        //
        const places_metadata_url = await ipfs.upload_contract_metadata({
            name: 'tz1aND Places',
            description: 'tz1aND Places FA2 tokens',
            interfaces: ["TZIP-12"],
            version: '1.0.0'
        }, true);

        // Compile and deploy Places FA2 contract.
        smartpy.compile_newtarget("FA2_Places", "FA2", ['config = FA2_contract.places_config()',
            `metadata = sp.utils.metadata_of_url("${places_metadata_url}")`,
            `admin = sp.address("${accountAddress}")`]);

        deploy_contract_batch("FA2_Places", fa2_batch);

        //
        // DAO
        //
        const dao_metadata_url = await ipfs.upload_contract_metadata({
            name: 'tz1aND DAO',
            description: 'tz1aND Places FA2 tokens',
            interfaces: ["TZIP-12"],
            version: '1.0.0'
        }, true);

        // Compile and deploy Places FA2 contract.
        smartpy.compile_newtarget("FA2_DAO", "FA2", ['config = FA2_contract.dao_config()',
            `metadata = sp.utils.metadata_of_url("${dao_metadata_url}")`,
            `admin = sp.address("${accountAddress}")`]);

        deploy_contract_batch("FA2_DAO", fa2_batch);

        // send batch.
        const fa2_batch_op = await fa2_batch.send();
        await fa2_batch_op.confirmation();
        const [items_FA2_contract, places_FA2_contract, dao_FA2_contract] = await get_originated_contracts_batch(fa2_batch_op, Tezos);

        //
        // Minter
        //
        // Minter can't be batched because others depend on it.
        //
        const minter_metadata_url = await ipfs.upload_contract_metadata({
            name: 'tz1aND Minter',
            description: 'tz1aND Items and Places minter',
            interfaces: [],
            version: '1.0.0'
        });

        // Compile and deploy Minter contract.
        smartpy.compile_newtarget("TL_Minter", "TL_Minter", [`manager = sp.address("${accountAddress}")`,
        `items_contract = sp.address("${items_FA2_contract.address}")`,
        `places_contract = sp.address("${places_FA2_contract.address}")`,
        `metadata = sp.utils.metadata_of_url("${minter_metadata_url}")`]);

        const Minter_contract = await deploy_contract("TL_Minter", Tezos);

        // Set the minter as the token administrator
        console.log("Setting minter as token admin...")
        const set_admin_batch = Tezos.wallet.batch();
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

        // prepare others batch
        const tezland_batch = Tezos.wallet.batch();

        //
        // World (Marketplaces)
        //
        const world_metadata_url = await ipfs.upload_contract_metadata({
            name: 'tz1aND World',
            description: 'tz1aND Virtual World',
            interfaces: [],
            version: '1.0.0'
        });

        // Compile and deploy Places contract.
        smartpy.compile_newtarget("TL_World", "TL_World", [`manager = sp.address("${accountAddress}")`,
        `items_contract = sp.address("${items_FA2_contract.address}")`,
        `places_contract = sp.address("${places_FA2_contract.address}")`,
        `minter = sp.address("${Minter_contract.address}")`,
        `dao_contract = sp.address("${dao_FA2_contract.address}")`,
        `terminus = sp.timestamp(${Math.floor(Date.now() / 1000)}).add_days(60)`,
        `metadata = sp.utils.metadata_of_url("${world_metadata_url}")`]);

        await deploy_contract_batch("TL_World", tezland_batch);

        //
        // Dutch
        //
        const dutch_metadata_url = await ipfs.upload_contract_metadata({
            name: 'tz1aND Dutch Auctions',
            description: 'tz1aND Item and Place Dutch auctions',
            interfaces: [],
            version: '1.0.0'
        });

        // Compile and deploy Dutch auction contract.
        smartpy.compile_newtarget("TL_Dutch", "TL_Dutch", [`manager = sp.address("${accountAddress}")`,
        `items_contract = sp.address("${items_FA2_contract.address}")`,
        `places_contract = sp.address("${places_FA2_contract.address}")`,
        `minter = sp.address("${Minter_contract.address}")`,
        `metadata = sp.utils.metadata_of_url("${dutch_metadata_url}")`]);

        await deploy_contract_batch("TL_Dutch", tezland_batch);

        const tezland_batch_op = await tezland_batch.send();
        await tezland_batch_op.confirmation();
        const [World_contract, Dutch_contract] = await get_originated_contracts_batch(tezland_batch_op, Tezos);

        // Mint 0 dao and set the world as the dao administrator
        console.log("Setting world as dao admin")
        const tokenMetadataMap = new MichelsonMap();
        tokenMetadataMap.set("decimals", char2Bytes("6"));
        tokenMetadataMap.set("name", char2Bytes("tz1aND DAO"));
        tokenMetadataMap.set("symbol", char2Bytes("tz1aDAO"));

        const dao_admin_batch = Tezos.wallet.batch();
        dao_admin_batch.with([
            {
                kind: OpKind.TRANSACTION,
                ...dao_FA2_contract.methodsObject.mint({
                    address: accountAddress,
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

        // If this is a test deploy, mint some test items.
        if(options.network === "sandbox") {
            console.log(kleur.magenta("Minting tokens for testing...\n"));

            const mintNewItem = async (model_path: string, amount: number, batch: WalletOperationBatch) => {
                const mesh_url = await ipfs.upload_item_model(model_path);
                console.log(`item model: ${mesh_url}`);

                // Create item metadata and upload it
                const item_metadata_url = await ipfs.upload_item_metadata(Minter_contract.address, mesh_url);
                console.log(`item token metadata: ${item_metadata_url}`);

                batch.with([{
                    kind: OpKind.TRANSACTION,
                    ...Minter_contract.methodsObject.mint_Item({
                        address: accountAddress,
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
                    minter: accountAddress,
                    centerCoordinates: center,
                    borderCoordinates: border,
                    buildHeight: 10,
                    placeType: "exterior"
                });
                console.log(`place token metadata: ${place_metadata_url}`);

                batch.with([{
                    kind: OpKind.TRANSACTION,
                    ...Minter_contract.methodsObject.mint_Place({
                        address: accountAddress,
                        metadata: Buffer.from(place_metadata_url, 'utf8').toString('hex')
                    }).toTransferParams()
                }]);
            }

            // prepare batch
            const mint_batch = Tezos.wallet.batch();

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


        const end_time = performance.now();
        console.log(kleur.green(`Deploy ran in ${((end_time - start_time) / 1000).toFixed(1)}s`));
    } catch (error) {
        console.error(error);
    }
};
