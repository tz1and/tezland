import { char2Bytes } from '@taquito/utils'
import assert from 'assert';
import { DeployContractBatch } from '../commands/DeployBase';
import { MichelsonMap, OpKind } from '@taquito/taquito';
import PostDeploy from '../deploy/postdeploy';
import config from '../user.config';
import { DeployMode } from '../config/config';


export default class Deploy extends PostDeploy {
    protected override async deployDo() {
        assert(this.tezos);

        // prepare batch
        const daoWasDeployed = this.deploymentsReg.getContract("FA2_DAO");

        const fa2_batch = new DeployContractBatch(this);

        //
        // Items
        //
        await fa2_batch.addToBatch("FA2_Items", "Tokens", "tz1andItems", [
            `admin = sp.address("${this.accountAddress}")`
        ]);

        //
        // Places
        //
        await fa2_batch.addToBatch("FA2_Places", "Tokens", "tz1andPlaces", [
            `admin = sp.address("${this.accountAddress}")`
        ]);

        //
        // DAO
        //
        await fa2_batch.addToBatch("FA2_DAO", "Tokens", "tz1andDAO", [
            `admin = sp.address("${this.accountAddress}")`
        ]);

        // send batch.
        const [items_FA2_contract, places_FA2_contract, dao_FA2_contract] = await fa2_batch.deployBatch();

        if(!daoWasDeployed) {
            await this.run_op_task("Minting dao tokens...", async () => {
                const tokenMetadataMap = new MichelsonMap();
                tokenMetadataMap.set("decimals", char2Bytes("6"));
                tokenMetadataMap.set("name", char2Bytes("tz1and DAO"));
                tokenMetadataMap.set("symbol", char2Bytes("tz1aDAO"));

                return dao_FA2_contract.methodsObject.mint([{
                    to_: this.accountAddress,
                    amount: 0,
                    token: { new: tokenMetadataMap }
                }]).send();
            });
        }

        //
        // Minter
        //
        const minterWasDeployed = this.deploymentsReg.getContract("TL_Minter");

        // prepare minter/dutch batch
        const tezland_batch = new DeployContractBatch(this);

        // Compile and deploy Minter contract.
        await tezland_batch.addToBatch("TL_Minter", "legacy/TL_Minter", "TL_Minter", [
            `administrator = sp.address("${this.accountAddress}")`,
            `items_contract = sp.address("${items_FA2_contract.address}")`,
            `places_contract = sp.address("${places_FA2_contract.address}")`
        ]);

        //const Minter_contract = await this.deploy_contract("TL_Minter");

        //
        // Dutch
        //
        // Compile and deploy Dutch auction contract.
        await tezland_batch.addToBatch("TL_Dutch", "legacy/TL_Dutch", "TL_Dutch", [
            `administrator = sp.address("${this.accountAddress}")`,
            `items_contract = sp.address("${items_FA2_contract.address}")`,
            `places_contract = sp.address("${places_FA2_contract.address}")`
        ]);

        //const Dutch_contract = await this.deploy_contract("TL_Dutch");

        const [Minter_contract, Dutch_contract] = await tezland_batch.deployBatch();

        if (!minterWasDeployed) {
            await this.run_op_task("Setting minter as token admin...", async () => {
                return this.tezos!.wallet.batch().with([
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
                ]).send();
            });
        }

        //
        // World (Marketplaces)
        //
        // Compile and deploy Places contract.
        const World_contract = await this.deploy_contract("TL_World", "legacy/TL_World", "TL_World", [
            `administrator = sp.address("${this.accountAddress}")`,
            `items_contract = sp.address("${items_FA2_contract.address}")`,
            `places_contract = sp.address("${places_FA2_contract.address}")`,
            `dao_contract = sp.address("${dao_FA2_contract.address}")`,
            `name = "tz1and World"`,
            `description = "tz1and Virtual World"`
        ]);

        //
        // Post deploy
        //
        // If this is a sandbox deploy, run the post deploy tasks.
        const deploy_mode = this.isSandboxNet ? config.sandbox.deployMode : DeployMode.None;
        
        await this.runPostDeploy(deploy_mode, new Map(Object.entries({
            items_FA2_contract: items_FA2_contract,
            places_FA2_contract: places_FA2_contract,
            dao_FA2_contract: dao_FA2_contract,
            Minter_contract: Minter_contract,
            World_contract: World_contract,
            Dutch_contract: Dutch_contract
        })));
    }
}
