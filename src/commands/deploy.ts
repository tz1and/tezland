import * as smartpy from './smartpy';
import { TezosToolkit, ContractAbstraction, ContractProvider } from "@taquito/taquito";
import { InMemorySigner } from "@taquito/signer";
import * as ipfs from '../ipfs'
import {
  Float16Array, isFloat16Array,
  getFloat16, setFloat16,
  hfround,
} from "@petamoriken/float16";


async function deploy_contract(contract_name: string, Tezos: TezosToolkit): Promise<ContractAbstraction<ContractProvider>> {
  var orig_op = await Tezos.contract.originate({
    code: require(`../../build/${contract_name}.json`),
    init: require(`../../build/${contract_name}_storage.json`),
  });

  var contract = await orig_op.contract();

  console.log(`Successfully deployed contract ${contract_name}`);
  console.log(`>> Transaction hash: ${orig_op.hash}`);
  console.log(`>> Contract address: ${contract.address}`);

  return contract;
};

export async function deploy(/*contract_name: string*/): Promise<void> {
  try {
    // Create signer and toolkit
    if (!process.env.TEZOS_RPC_URL) throw Error("TEZOS_RPC_URL not set");
    if (!process.env.ORIGINATOR_PRIVATE_KEY) throw Error("ORIGINATOR_PRIVATE_KEY not set");

    const { TEZOS_RPC_URL, ORIGINATOR_PRIVATE_KEY } = process.env;

    const signer = await InMemorySigner.fromSecretKey(ORIGINATOR_PRIVATE_KEY);
    const Tezos = new TezosToolkit(TEZOS_RPC_URL);
    Tezos.setProvider({ signer: signer });

    const accountAddress = await signer.publicKeyHash();

    //
    // Items
    //
    const items_metadata_url = await ipfs.upload_contract_metadata({
      name: 'tz1aND Items',
      description: 'tz1aND Item FA2 tokens',
      interfaces: ["TZIP-12"],
      version: '1.0.0'});

    // Compile and deploy Items FA2 contract.
    smartpy.compile_newtarget("FA2_Items", "FA2", ['config = FA2_contract.items_config()',
      `metadata = sp.utils.metadata_of_url("${items_metadata_url}")`,
      `admin = sp.address("${accountAddress}")`]);

    const items_FA2_contract = await deploy_contract("FA2_Items", Tezos);

    //
    // Places
    //
    const places_metadata_url = await ipfs.upload_contract_metadata({
      name: 'tz1aND Places',
      description: 'tz1aND Places FA2 tokens',
      interfaces: ["TZIP-12"],
      version: '1.0.0'});

    // Compile and deploy Places FA2 contract.
    smartpy.compile_newtarget("FA2_Places", "FA2", ['config = FA2_contract.places_config()',
      `metadata = sp.utils.metadata_of_url("${places_metadata_url}")`,
      `admin = sp.address("${accountAddress}")`]);

    const places_FA2_contract = await deploy_contract("FA2_Places", Tezos);

    //
    // Minter
    //
    const minter_metadata_url = await ipfs.upload_contract_metadata({
      name: 'tz1aND Minter',
      description: 'tz1aND Items and Places minter',
      interfaces: [],
      version: '1.0.0'});
    
    // Compile and deploy Minter contract.
    smartpy.compile_newtarget("TL_Minter", "TL_Minter", [`manager = sp.address("${accountAddress}")`,
      `items_contract = sp.address("${items_FA2_contract.address}")`,
      `places_contract = sp.address("${places_FA2_contract.address}")`,
      `metadata = sp.utils.metadata_of_url("${minter_metadata_url}")`]);

    const Minter_contract = await deploy_contract("TL_Minter", Tezos);

    // Set the minter as the token administrator
    console.log("Setting minter as token admin...")
    const items_admin_op = await items_FA2_contract.methods.set_administrator(Minter_contract.address).send();
    await items_admin_op.confirmation();

    const places_admin_op = await places_FA2_contract.methods.set_administrator(Minter_contract.address).send();
    await places_admin_op.confirmation();

    //
    // World (Marketplaces)
    //
    const marketplaces_metadata_url = await ipfs.upload_contract_metadata({
      name: 'tz1aND World',
      description: 'tz1aND Virtual World',
      interfaces: [],
      version: '1.0.0'});

    // Compile and deploy Places contract.
    smartpy.compile_newtarget("TL_Places", "TL_Places", [`manager = sp.address("${accountAddress}")`,
      `items_contract = sp.address("${items_FA2_contract.address}")`,
      `places_contract = sp.address("${places_FA2_contract.address}")`,
      `minter = sp.address("${Minter_contract.address}")`,
      `metadata = sp.utils.metadata_of_url("${marketplaces_metadata_url}")`]);

    const Places_contract = await deploy_contract("TL_Places", Tezos);

    //
    // Dutch
    //
    const dutch_metadata_url = await ipfs.upload_contract_metadata({
      name: 'tz1aND Dutch Auctions',
      description: 'tz1aND Item and Place Dutch auctions',
      interfaces: [],
      version: '1.0.0'});

    // Compile and deploy Dutch auction contract.
    smartpy.compile_newtarget("TL_Dutch", "TL_Dutch", [`manager = sp.address("${accountAddress}")`,
      `items_contract = sp.address("${items_FA2_contract.address}")`,
      `places_contract = sp.address("${places_FA2_contract.address}")`,
      `minter = sp.address("${Minter_contract.address}")`,
      `metadata = sp.utils.metadata_of_url("${dutch_metadata_url}")`]);
      
    const Dutch_contract = await deploy_contract("TL_Dutch", Tezos);

    // TEMP
    const mintNewItem = async (model_path: string, amount: number) => {
      const mesh_url = await ipfs.upload_item_model(model_path);
      console.log(`item model: ${mesh_url}`);

      // Create item metadata and upload it
      const item_metadata_url = await ipfs.upload_item_metadata(Minter_contract.address, mesh_url);
      console.log(`item token metadata: ${item_metadata_url}`);

      // mint some Item tokens
      console.log("Minting Item tokens")
      const mint_item_op = await Minter_contract.methodsObject.mint_Item({address: accountAddress,
        amount: amount,
        royalties: 250,
        metadata: Buffer.from(item_metadata_url, 'utf8').toString('hex')}).send();
      await mint_item_op.confirmation();
    }

    await mintNewItem('assets/Lantern.glb', 100);
    await mintNewItem('assets/Fox.glb', 25);
    await mintNewItem('assets/Duck.glb', 75);
    await mintNewItem('assets/DragonAttenuation.glb', 66);

    // Create place metadata and upload it
    const mintNewPlace = async (center: number[], border: number[][]) => {
      const place_metadata_url = await ipfs.upload_place_metadata(Minter_contract.address,
        center,
        border);
      console.log(`place token metadata: ${place_metadata_url}`);

      // mint a Place token
      console.log("Minting Place token")
      const mint_place_op = await Minter_contract.methodsObject.mint_Place({address: accountAddress,
        metadata: Buffer.from(place_metadata_url, 'utf8').toString('hex')}).send();
      await mint_place_op.confirmation();
    }

    await mintNewPlace([0,0,0], [[10,0,10], [10,0,-10], [-10,0,-10], [-10,0,10]]);
    await mintNewPlace([22,0,0], [[10,0,10], [10,0,-10], [-10,0,-10], [-10,0,10]]);
    await mintNewPlace([22,0,-22], [[10,0,10], [10,0,-10], [-10,0,-10], [-10,0,10]]);
    await mintNewPlace([0,0,-25], [[10,0,10], [10,0,-10], [-10,0,-10], [-10,0,10], [0,0,14]]);

    // Set operators
    /*console.log("Set item operators")
    const operator_op = await items_FA2_contract.methods.update_operators([{
      add_operator: {
          owner: accountAddress,
          operator: Places_contract.address,
          token_id: 0
      }}]).send();
    await operator_op.confirmation();

    const toHexString = (bytes: Uint8Array) => bytes.reduce((str: String, byte: Number) => str + byte.toString(16).padStart(2, '0'), '');

    {
      const place_id = 0;

      console.log("Place a lot of items")
      for (let j = 0; j < 5; j++) {
        const item_list = new Array();
        for (let i = 0; i < 10; i++) {
          // 4 floats for quat, 1 float scale, 3 floats pos = 16 bytes
          const array = new Uint8Array(16);
          const view = new DataView(array.buffer);
          // quat
          setFloat16(view, 0, 0);
          setFloat16(view, 2, 0);
          setFloat16(view, 4, 0);
          setFloat16(view, 6, 1);
          // scale
          setFloat16(view, 8, 1);
          // pos
          setFloat16(view, 10, Math.random() * 20 - 10);
          setFloat16(view, 12, 1);
          setFloat16(view, 14, Math.random() * 20 - 10);
          const example_item_data = toHexString(array);
          //console.log(example_item_data);

          item_list.push({token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data});
        }

        const place_items_op = await Places_contract.methodsObject.place_items({
          lot_id: place_id, item_list: item_list
        }).send();
        console.log('Operation hash:', place_items_op.hash);
        await place_items_op.confirmation();
      }

      console.log("Place a single item")
      const place_item_op = await Places_contract.methodsObject.place_items({
        lot_id: place_id, item_list: [
          {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: "ffffffffffffffffffffffffffffffff"}
        ]}).send();
      console.log('Operation hash:', place_item_op.hash);
      await place_item_op.confirmation();

      console.log("Remove some items")
      const remove_items_op = await Places_contract.methodsObject.remove_items({
        lot_id: place_id, item_list: [1,2,3,45]}).send();
      await remove_items_op.confirmation();

      console.log("Remove a lot of items")
      const remove_many_items_op = await Places_contract.methodsObject.remove_items({
        lot_id: place_id, item_list: [...Array(10)].map((_, i) => 30 + i)}).send();
      await remove_many_items_op.confirmation();

      console.log("Get an item")
      const get_item_op = await Places_contract.methodsObject.get_item({
        lot_id: place_id, item_id: 47}).send({ amount: 1000000, mutez: true });
      await get_item_op.confirmation();
    }*/

    console.log('\n');
    console.log("REACT_APP_ITEM_CONTRACT=" + items_FA2_contract.address);
    console.log("REACT_APP_PLACE_CONTRACT=" + places_FA2_contract.address);
    console.log("REACT_APP_MARKETPLACES_CONTRACT=" + Places_contract.address);
    console.log("REACT_APP_MINTER_CONTRACT=" + Minter_contract.address);
    console.log("REACT_APP_DUTCH_AUCTION_CONTRACT=" + Dutch_contract.address);

  } catch (error) {
    console.log(error);
  }
};
