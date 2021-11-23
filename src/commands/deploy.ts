import * as smartpy from './smartpy';
import { TezosToolkit, ContractAbstraction, ContractProvider } from "@taquito/taquito";
import { InMemorySigner } from "@taquito/signer";


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

    // Compile and deploy Items FA2 contract.
    smartpy.compile_newtarget("FA2_Items", "FA2", ['config = FA2_contract.items_config()',
      'metadata = sp.utils.metadata_of_url("https://example.com")',
      `admin = sp.address("${accountAddress}")`]);

    const items_FA2_contract = await deploy_contract("FA2_Items", Tezos);

    // Compile and deploy Places FA2 contract.
    smartpy.compile_newtarget("FA2_Places", "FA2", ['config = FA2_contract.places_config()',
      'metadata = sp.utils.metadata_of_url("https://example.com")',
      `admin = sp.address("${accountAddress}")`]);

    const places_FA2_contract = await deploy_contract("FA2_Places", Tezos);
    
    // Compile and deploy Minter contract.
    smartpy.compile_newtarget("TL_Minter", "TL_Minter", [`sp.address("${accountAddress}")`,
      `sp.address("${items_FA2_contract.address}")`,
      `sp.address("${places_FA2_contract.address}")`]);

    const Minter_contract = await deploy_contract("TL_Minter", Tezos);

    // Set the minter as the token administrator
    console.log("Setting minter as token admin...")
    const items_admin_op = await items_FA2_contract.methods.set_administrator(Minter_contract.address).send();
    await items_admin_op.confirmation();

    const places_admin_op = await places_FA2_contract.methods.set_administrator(Minter_contract.address).send();
    await places_admin_op.confirmation();

    // Compile and deploy Places contract.
    smartpy.compile_newtarget("TL_Places", "TL_Places", [`sp.address("${accountAddress}")`,
      `sp.address("${items_FA2_contract.address}")`,
      `sp.address("${places_FA2_contract.address}")`,
      `sp.address("${Minter_contract.address}")`]);

    const Places_contract = await deploy_contract("TL_Places", Tezos);

    // TEMP
    // mint some Item tokens
    console.log("Minting Item tokens")
    const mint_item_op = await Minter_contract.methodsObject.mint_Item({address: accountAddress,
      amount: 100,
      royalties: 250,
      metadata: Buffer.from("test_metadata", 'utf8').toString('hex')}).send();
    await mint_item_op.confirmation();

    // mint a Place token
    console.log("Minting Place token")
    const mint_place_op = await Minter_contract.methodsObject.mint_Place({address: accountAddress,
      metadata: Buffer.from("test_metadata", 'utf8').toString('hex')}).send();
    await mint_place_op.confirmation();

    // Set operators
    console.log("Set item operators")
    const operator_op = await items_FA2_contract.methods.update_operators([{
      add_operator: {
          owner: accountAddress,
          operator: Places_contract.address,
          token_id: 0
      }}]).send();
    await operator_op.confirmation();

    //todo: use half float? https://github.com/petamoriken/float16/blob/master/src/_util/converter.mjs
    // http://www.fox-toolkit.org/ftp/fasthalffloatconversion.pdf

    var float32 = new Float32Array(8);
    float32[0] = 1.1; float32[1] = 5.1; float32[2] = 2.1; float32[3] = 0.0; // quaternion xyzw
    float32[4] = 10.0; // scale
    float32[5] = 100.0; float32[6] = 200.0; float32[7] = -50.0; // position xyz
    var view = new Uint8Array(float32.buffer);
    const toHexString = (bytes: Uint8Array) => bytes.reduce((str: String, byte: Number) => str + byte.toString(16).padStart(2, '0'), '');
    //const example_item_data = toHexString(view);
    const example_item_data = "ffffffffffffffffffffffffffffffff"

    {
      const place_id = 0;

      console.log("Place a lot of items")
      for (let j = 0; j < 5; j++) {
        const place_items_op = await Places_contract.methodsObject.place_items({
          lot_id: place_id, item_list: [
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data},
            {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data}
          ]}).send();
        console.log('Operation hash:', place_items_op.hash);
        await place_items_op.confirmation();
      }

      console.log("Place a single item")
      const place_item_op = await Places_contract.methodsObject.place_items({
        lot_id: place_id, item_list: [
          {token_amount: 1, token_id: 0, xtz_per_token: 1000000, item_data: example_item_data}
        ]}).send();
      console.log('Operation hash:', place_item_op.hash);
      await place_item_op.confirmation();

      console.log("Remove some items")
      const remove_items_op = await Places_contract.methodsObject.remove_items({
        lot_id: place_id, item_list: [1,2,3,55]}).send();
      await remove_items_op.confirmation();

      console.log("Remove a lot of items")
      const remove_many_items_op = await Places_contract.methodsObject.remove_items({
        lot_id: place_id, item_list: [...Array(40)].map((_, i) => 100 + i)}).send();
      await remove_many_items_op.confirmation();

      console.log("Get an item")
      const get_item_op = await Places_contract.methodsObject.get_item({
        lot_id: place_id, item_id: 99}).send({ amount: 1000000, mutez: true });
      await get_item_op.confirmation();
    }

  } catch (error) {
    console.log(error);
  }
};
