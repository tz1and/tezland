import * as smartpy from './smartpy';
import * as ipfs from '../ipfs'
import { char2Bytes } from '@taquito/utils'
import assert from 'assert';
import kleur from 'kleur';
import { DeployContractBatch } from './DeployBase';
import { ContractAbstraction, MichelsonMap, OpKind, Wallet } from '@taquito/taquito';
import fs from 'fs';
import PostUpgrade from './postupgrade';
import config from '../user.config';
import { DeployMode } from '../config/config';


// TODO: need to move the deploy code here and make it update from v1.
// TODO: v2 gas tests, etc... from deploy_v2
// TODO: actually update metadata on World and Minter v1


export default class Upgrade extends PostUpgrade {
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
            await this.run_op_task(`Updating entrypoint ${kleur.yellow(ep_name)}...`, async () => {
                return contract.methodsObject.update_ep({
                    ep_name: {[ep_name]: null},
                    new_code: JSON.parse(fs.readFileSync(code_map.get(ep_name)!, "utf-8"))
                }).send();
            });
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

        // TODO: add task flags to deploy registry. so I can tell if something already happened.

        //
        // Pause World v1 and Minter v1 for upgrade.
        //
        await this.run_op_task("Pausing World v1 and Minter v1...", async () => {
            return this.tezos!.wallet.batch().with([
                // Pause world v1.
                {
                    kind: OpKind.TRANSACTION,
                    ...tezlandWorld.methods.set_paused(true).toTransferParams()
                },
                // Pause minter v1.
                {
                    kind: OpKind.TRANSACTION,
                    ...tezlandMinter.methods.set_paused(true).toTransferParams()
                }
            ]).send();
        });

        //
        // Token Registry
        //
        let Registry_contract: ContractAbstraction<Wallet>;
        {
            // Compile and deploy registry contract.
            await this.compile_contract("TL_TokenRegistry", "TL_TokenRegistry", "TL_TokenRegistry", [
                `administrator = sp.address("${this.accountAddress}")`,
                `royalties_merkle_root = sp.bytes("0x00")`,
                `collections_merkle_root = sp.bytes("0x00")`
            ]);

            Registry_contract = await this.deploy_contract("TL_TokenRegistry");
        }

        //
        // Minter v2 and Interiors.
        //
        let Minter_v2_contract: ContractAbstraction<Wallet>, interiors_FA2_contract: ContractAbstraction<Wallet>;
        {
            const minterV2WasDeployed = this.getDeployment("TL_Minter_v2");

            // prepare minter/interiors batch
            const tezland_batch = new DeployContractBatch(this);

            // Compile and deploy Minter contract.
            await this.compile_contract("TL_Minter_v2", "TL_Minter_v2", "TL_Minter", [
                `administrator = sp.address("${this.accountAddress}")`,
                `token_registry = sp.address("${Registry_contract.address}")`
            ]);
            tezland_batch.addToBatch("TL_Minter_v2");

            await this.compile_contract("FA2_Interiors", "Tokens", "tz1andInteriors", [
                `admin = sp.address("${this.accountAddress}")`
            ]);
            tezland_batch.addToBatch("FA2_Interiors");

            [Minter_v2_contract, interiors_FA2_contract] = await tezland_batch.deployBatch();

            if (!minterV2WasDeployed) {
                // Set the minter as the token administrator
                await this.run_op_task("Setting minter as token admin...", async () => {
                    return this.tezos!.wallet.batch().with([
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
                            ...Registry_contract.methods.manage_public_collections([{add_collections: [tezlandItems.address]}]).toTransferParams()
                        },
                        // accept places admin from wallet
                        {
                            kind: OpKind.TRANSACTION,
                            ...tezlandPlaces.methods.accept_administrator().toTransferParams()
                        }
                    ]).send();
                });
            }
        }

        //
        // Token Factory
        //
        // TODO: could probably deploy with world v2.
        let Factory_contract: ContractAbstraction<Wallet>;
        {
            const factoryWasDeployed = this.getDeployment("TL_TokenFactory");

            // Compile and deploy fa2 factory contract.
            await this.compile_contract("TL_TokenFactory", "TL_TokenFactory", "TL_TokenFactory", [
                `administrator = sp.address("${this.accountAddress}")`,
                `token_registry = sp.address("${Registry_contract.address}")`,
                `minter = sp.address("${Minter_v2_contract.address}")`
            ]);

            Factory_contract = await this.deploy_contract("TL_TokenFactory");

            if (!factoryWasDeployed) {
                await this.run_op_task("Giving registry permissions to factory contract...", async () => {
                    return this.tezos!.wallet.batch().with([
                        {
                            kind: OpKind.TRANSACTION,
                            ...Registry_contract.methods.manage_permissions([{add_permissions: [Factory_contract.address]}]).toTransferParams()
                        }
                    ]).send();
                });
            }
        }

        //
        // World v2 (Marketplaces)
        //
        let World_v2_contract: ContractAbstraction<Wallet>;
        {
            const worldV2WasDeployed = this.getDeployment("TL_World_v2");

            // Compile and deploy Places contract.
            // IMPORTANT NOTE: target name changed so on next mainnet deply it will automatically deploy the v2!
            await this.compile_contract("TL_World_v2", "TL_World_v2", "TL_World", [
                `administrator = sp.address("${this.accountAddress}")`,
                `token_registry = sp.address("${Registry_contract.address}")`,
                `paused = sp.bool(True)`,
                `items_tokens = sp.address("${tezlandItems.address}")`,
                `name = "tz1and World"`,
                `description = "tz1and Virtual World v2"`
            ]);

            World_v2_contract = await this.deploy_contract("TL_World_v2");

            if (!worldV2WasDeployed) {
                await this.run_op_task("Set allowed place tokens on world...", async () => {
                    return World_v2_contract.methodsObject.set_allowed_place_token([
                        {
                            add_allowed_place_token: {
                                fa2: tezlandPlaces.address,
                                place_limits: {
                                    chunk_limit: 2,
                                    chunk_item_limit: 64
                                }
                            }
                        },
                        {
                            add_allowed_place_token: {
                                fa2: interiors_FA2_contract.address,
                                place_limits: {
                                    chunk_limit: 4,
                                    chunk_item_limit: 64
                                }
                            }
                        }
                    ]).send();
                });
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
                `dao_contract = sp.address("${tezlandDAO.address}")`,
                `world_v2_contract = sp.address("${World_v2_contract.address}")`
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
        await this.run_op_task("Updating metadata on v1 world contract...", async () => {
            assert(world_v1_1_metadata);
            return tezlandWorld.methodsObject.get_item({
                lot_id: 0,
                item_id: 0,
                issuer: this.accountAddress,
                extension: MichelsonMap.fromLiteral({ "metadata_uri": char2Bytes(world_v1_1_metadata) })
            }).send();
        });

        await this.run_op_task("Updating metadata on v1 minter contract...", async () => {
            assert(minter_v1_1_metadata);
            return tezlandMinter.methodsObject.mint_Place([{
                to_: this.accountAddress,
                metadata: MichelsonMap.fromLiteral({ "metadata_uri": char2Bytes(minter_v1_1_metadata) })
            }]).send();
        });

        //
        // TODO: Run migration and unpause World v2.
        //
        await this.run_op_task("Set migration contract on World v2...", async () => {
            return World_v2_contract.methods.update_settings([{migration_contract: tezlandWorld.address}]).send()
        });

        //
        // TODO: actually run migration.
        //

        await this.run_op_task("World v2: Remove migration contract and unpause...", async () => {
            return World_v2_contract.methods.update_settings([{migration_contract: null}, {paused: false}]).send()
        });

        //
        // Post deploy
        //
        // TODO: run world migration
        // TODO: post upgrade step, gas tests, etc
        // If this is a sandbox deploy, run the post deploy tasks.
        const deploy_mode = this.isSandboxNet ? config.sandbox.deployMode : DeployMode.None;
        
        await this.runPostDeploy(deploy_mode, new Map(Object.entries({
            items_FA2_contract: tezlandItems,
            places_FA2_contract: tezlandPlaces,
            interiors_FA2_contract: interiors_FA2_contract,
            dao_FA2_contract: tezlandDAO,
            Minter_contract: Minter_v2_contract,
            World_contract: World_v2_contract,
            Dutch_contract: tezlandDutchAuctions,
            Factory_contract: Factory_contract,
            Registry_contract: Registry_contract
        })));
    }
}
