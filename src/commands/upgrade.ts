import * as smartpy from './smartpy';
import * as ipfs from '../ipfs'
import { char2Bytes } from '@taquito/utils'
import assert from 'assert';
import kleur from 'kleur';
import DeployBase, { DeployContractBatch, sleep } from './DeployBase';
import { ContractAbstraction, MichelsonMap, OpKind, TransactionWalletOperation, Wallet, WalletOperationBatch } from '@taquito/taquito';
import fs from 'fs';


// TODO: need to move the deploy code here and make it update from v1.
// TODO: v2 gas tests, etc... from deploy_v2
// TODO: actually update metadata on World and Minter v1


export default class Upgrade extends DeployBase {
    constructor(options: any) {
        super(options);
        this.cleanDeploymentsInSandbox = false;
    }

    // Compiles contract, extracts lazy entrypoint code and deploys the updates.
    // Note: target_args needs to exclude metadata.
    private async upgrade_entrypoint(contract: ContractAbstraction<Wallet>, target_name: string, file_name: string, contract_name: string,
        target_args: string[], entrypoints: string[], upload_new_metadata: boolean): Promise<string | undefined> {
        // Compile contract with metadata set.
        const code_map = smartpy.upgrade_newtarget(target_name, file_name, contract_name, target_args.concat(['metadata = sp.utils.metadata_of_url("metadata_dummy")']), entrypoints);

        for (const ep_name of entrypoints) {
            console.log(`Updating entrypoint ${kleur.yellow(ep_name)}...`)
            const upgrade_op = await contract.methodsObject.update_ep({
                ep_name: {[ep_name]: null},
                new_code: JSON.parse(fs.readFileSync(code_map.get(ep_name)!, "utf-8"))
            }).send();
            await upgrade_op.confirmation();
            console.log(kleur.green(">> Done."), `Transaction hash: ${upgrade_op.opHash}`);
        }

        let metdata_url;
        if (upload_new_metadata) {
            const metadtaFile = `${target_name}_metadata.json`;
            const metadtaPath = `./build/${metadtaFile}`;
            const contract_metadata = JSON.parse(fs.readFileSync(metadtaPath, { encoding: 'utf-8' }));

            metdata_url = await ipfs.upload_metadata(contract_metadata, this.isSandboxNet);
        }

        console.log();
        return metdata_url;
    }

    protected override async deployDo() {
        assert(this.tezos);

        //
        // Get v1 deployments.
        //
        const tezlandItems = await this.tezos.wallet.at(this.getDeployment("FA2_Items"));
        const tezlandPlaces = await this.tezos.wallet.at(this.getDeployment("FA2_Places"));
        const tezlandDAO = await this.tezos.wallet.at(this.getDeployment("FA2_DAO"));
        const tezlandWorld = await this.tezos.wallet.at(this.getDeployment("TL_World"));
        const tezlandMinter = await this.tezos.wallet.at(this.getDeployment("TL_Minter"));
        const tezlandDutchAuctions = await this.tezos.wallet.at(this.getDeployment("TL_Dutch"));

        // TODO: pause relevant contracts during upgrade. Then unpause in the end.

        //
        // Minter v2 and Interiors.
        //
        let Minter_v2_contract, interiors_FA2_contract;
        {
            const minterV2WasDeployed = this.getDeployment("TL_Minter_v2");

            // prepare minter/interiors batch
            const tezland_batch = new DeployContractBatch(this);

            // Compile and deploy Minter contract.
            await this.compile_contract("TL_Minter_v2", "TL_Minter_v2", "TL_Minter", [
                `administrator = sp.address("${this.accountAddress}")`
            ]);
            tezland_batch.addToBatch("TL_Minter_v2");

            await this.compile_contract("FA2_Interiors", "Tokens", "tz1andInteriors", [
                `admin = sp.address("${this.accountAddress}")`
            ]);
            tezland_batch.addToBatch("FA2_Interiors");

            [Minter_v2_contract, interiors_FA2_contract] = await tezland_batch.deployBatch();

            if (!minterV2WasDeployed) {
                // Set the minter as the token administrator
                console.log("Setting minter as token admin...")
                const set_admin_batch = this.tezos.wallet.batch();
                set_admin_batch.with([
                    // Transfer items admin from minter v1 to minter v2
                    // Transfer places admin back to admin wallet
                    {
                        kind: OpKind.TRANSACTION,
                        ...tezlandMinter.methods.transfer_fa2_administrator([
                            {fa2: tezlandItems.address, proposed_fa2_administrator: Minter_v2_contract.address},
                            {fa2: tezlandPlaces.address, proposed_fa2_administrator: this.accountAddress},
                        ]).toTransferParams()
                    },
                    // accept items admin in minter v2
                    {
                        kind: OpKind.TRANSACTION,
                        ...Minter_v2_contract.methods.accept_fa2_administrator([tezlandItems.address]).toTransferParams()
                    },
                    // add items as public collection to minter v2
                    {
                        kind: OpKind.TRANSACTION,
                        ...Minter_v2_contract.methods.manage_public_collections([{add_collections: [tezlandItems.address]}]).toTransferParams()
                    }
                ])

                const set_admin_batch_op = await set_admin_batch.send();
                await set_admin_batch_op.confirmation();
                console.log(`>> Done. Transaction hash: ${set_admin_batch_op.opHash}\n`);
            }
        }

        //
        // Token Factory and Registry
        //
        let Registry_contract, Factory_contract;
        {
            const factoryWasDeployed = this.getDeployment("TL_TokenFactory");

            // prepare factory/registry batch
            const collection_batch = new DeployContractBatch(this);

            // Compile and deploy registry contract.
            await this.compile_contract("TL_TokenRegistry", "TL_TokenRegistry", "TL_TokenRegistry", [
                `administrator = sp.address("${this.accountAddress}")`,
                `minter = sp.address("${Minter_v2_contract.address}")`
            ]);

            collection_batch.addToBatch("TL_TokenRegistry");
            //const Registry_contract = await this.deploy_contract("TL_TokenRegistry");

            // Compile and deploy fa2 factory contract.
            await this.compile_contract("TL_TokenFactory", "TL_TokenFactory", "TL_TokenFactory", [
                `administrator = sp.address("${this.accountAddress}")`,
                `minter = sp.address("${Minter_v2_contract.address}")`
            ]);

            collection_batch.addToBatch("TL_TokenFactory");
            //const Dutch_contract = await this.deploy_contract("TL_TokenFactory");

            [Registry_contract, Factory_contract] = await collection_batch.deployBatch();

            if (!factoryWasDeployed) {
                // Set the minter permissions for factory
                console.log("Giving factory permissions to minter...")
                const minter_permissions_batch = this.tezos.wallet.batch();
                minter_permissions_batch.with([
                    {
                        kind: OpKind.TRANSACTION,
                        ...Minter_v2_contract.methods.manage_permissions([{add_permissions: [Factory_contract.address]}]).toTransferParams()
                    }
                ])
    
                const minter_permissions_batch_op = await minter_permissions_batch.send();
                await minter_permissions_batch_op.confirmation();
                console.log(`>> Done. Transaction hash: ${minter_permissions_batch_op.opHash}\n`);
            }
        }

        //
        // World v2 (Marketplaces)
        //
        let World_v2_contract;
        {
            const worldV2WasDeployed = this.getDeployment("TL_World_v2");

            // Compile and deploy Places contract.
            // IMPORTANT NOTE: target name changed so on next mainnet deply it will automatically deploy the v2!
            await this.compile_contract("TL_World_v2", "TL_World_v2", "TL_World", [
                `administrator = sp.address("${this.accountAddress}")`,
                `token_registry = sp.address("${Registry_contract.address}")`,
                `name = "tz1and World"`,
                `description = "tz1and Virtual World v2"`
            ]);

            World_v2_contract = await this.deploy_contract("TL_World_v2");

            if (!worldV2WasDeployed) {
                console.log("Set allowed place tokens on world...")
                const allowed_places_op = await World_v2_contract.methodsObject.set_allowed_place_token([
                    {
                        add_allowed_place_token: {
                            fa2: tezlandPlaces.address,
                            place_limits: {
                                chunk_limit: 1,
                                chunk_item_limit: 64
                            }
                        }
                    },
                    {
                        add_allowed_place_token: {
                            fa2: interiors_FA2_contract.address,
                            place_limits: {
                                chunk_limit: 1,
                                chunk_item_limit: 64
                            }
                        }
                    }
                ]).send();
                await allowed_places_op.confirmation();
                console.log(`>> Done. Transaction hash: ${allowed_places_op.opHash}\n`);
            }
        }

        //
        // Upgrade v1 contracts.
        //
        const world_v1_1_metadata = await this.upgrade_entrypoint(tezlandWorld,
            "TL_World_migrate_to_v2", "upgrades/TL_World_v1_1", "TL_World_v1_1",
            // contract params
            [
                `administrator = sp.address("${this.accountAddress}")`,
                `items_contract = sp.address("${tezlandItems.address}")`,
                `places_contract = sp.address("${tezlandPlaces.address}")`,
                `dao_contract = sp.address("${tezlandDAO.address}")`
            ],
            // entrypoints to upgrade
            ["set_item_data", "get_item"], true);

        const minter_v1_1_metadata = await this.upgrade_entrypoint(tezlandMinter,
            "TL_Minter_deprecate", "upgrades/TL_Minter_v1_1", "TL_Minter_v1_1",
            // contract params
            [
                `administrator = sp.address("${this.accountAddress}")`,
                `items_contract = sp.address("${tezlandItems.address}")`,
                `places_contract = sp.address("${tezlandPlaces.address}")`
            ],
            // entrypoints to upgrade
            ["mint_Place"], true);

        // Update metadata on v1 contracts
        {
            console.log("Updating metadata on v1 world contract...")
            assert(world_v1_1_metadata);
            const world_metadata_op = await tezlandWorld.methodsObject.get_item({
                lot_id: 0,
                item_id: 0,
                issuer: this.accountAddress,
                extension: MichelsonMap.fromLiteral({ "metadata_uri": char2Bytes(world_v1_1_metadata) })
            }).send();
            await world_metadata_op.confirmation();
            console.log(`>> Done. Transaction hash: ${world_metadata_op.opHash}\n`);

            console.log("Updating metadata on v1 minter contract...")
            assert(minter_v1_1_metadata);
            const minter_metadata_op = await tezlandMinter.methodsObject.mint_Place([{
                to_: this.accountAddress,
                metadata: MichelsonMap.fromLiteral({ "metadata_uri": char2Bytes(minter_v1_1_metadata) })
            }]).send();
            await minter_metadata_op.confirmation();
            console.log(`>> Done. Transaction hash: ${minter_metadata_op.opHash}\n`);
        }
    }
}
