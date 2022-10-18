import { char2Bytes } from '@taquito/utils'
import assert from 'assert';
import { DeployContractBatch } from './DeployBase';
import { MichelsonMap, OpKind } from '@taquito/taquito';
import PostDeploy from './postdeploy';


// TODO: finish this stuff!
// some issues: dependent transactions: setting adming, etc
export default class Deploy extends PostDeploy {
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
        // DAO
        //
        await this.compile_contract("FA2_DAO", "Tokens", "tz1andDAO", [
            `admin = sp.address("${this.accountAddress}")`
        ]);

        fa2_batch.addToBatch("FA2_DAO");

        // send batch.
        const [items_FA2_contract, places_FA2_contract, dao_FA2_contract] = await fa2_batch.deployBatch();

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
        await this.compile_contract("TL_World", "TL_World", "TL_World", [
            `administrator = sp.address("${this.accountAddress}")`,
            `items_contract = sp.address("${items_FA2_contract.address}")`,
            `places_contract = sp.address("${places_FA2_contract.address}")`,
            `dao_contract = sp.address("${dao_FA2_contract.address}")`,
            `name = "tz1and World"`,
            `description = "tz1and Virtual World"`
        ]);

        const World_contract = await this.deploy_contract("TL_World");

        //
        // Post deploy
        //
        await this.runPostDeploy(new Map(Object.entries({
            items_FA2_contract: items_FA2_contract,
            places_FA2_contract: places_FA2_contract,
            dao_FA2_contract: dao_FA2_contract,
            Minter_contract: Minter_contract,
            World_contract: World_contract,
            Dutch_contract: Dutch_contract
        })));
    }
}
