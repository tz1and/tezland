import * as smartpy from './smartpy';
import * as ipfs from '../ipfs'
import { char2Bytes, bytes2Char } from '@taquito/utils'
import assert from 'assert';
import kleur from 'kleur';
import { DeployContractBatch } from './DeployBase';
import { ContractAbstraction, MichelsonMap, OpKind, Wallet, WalletContract } from '@taquito/taquito';
import fs from 'fs';
import PostUpgrade from './postupgrade';
import config from '../user.config';
import { DeployMode } from '../config/config';


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

        await this.run_op_task(`Updating entrypoints [${kleur.yellow(entrypoints.join(', '))}]...`, async () => {
            let upgrade_batch = this.tezos!.wallet.batch();
            for (const ep_name of entrypoints) {
                upgrade_batch.with([
                    {
                        kind: OpKind.TRANSACTION,
                        ...contract.methodsObject.update_ep({
                            ep_name: {[ep_name]: null},
                            new_code: JSON.parse(fs.readFileSync(code_map.get(ep_name)!, "utf-8"))
                        }).toTransferParams()
                    }
                ]);
            }
            return upgrade_batch.send();
        });

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

        // If this is a sandbox deploy, run the post deploy tasks.
        const deploy_mode = this.isSandboxNet ? config.sandbox.deployMode : DeployMode.None;
        const debug_asserts = this.isSandboxNet && (deploy_mode != DeployMode.GasTest);

        console.log(kleur.magenta(`Compiling with debug_asserts=${debug_asserts}\n`))

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
        await this.run_op_task("Pausing World v1, Dutch v1 and Minter v1...", async () => {
            return this.tezos!.wallet.batch().with([
                // Pause world v1.
                {
                    kind: OpKind.TRANSACTION,
                    ...tezlandWorld.methods.set_paused(true).toTransferParams()
                },
                // Pause dutch v1.
                {
                    kind: OpKind.TRANSACTION,
                    ...tezlandDutchAuctions.methods.set_paused(true).toTransferParams()
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
        let Registry_contract: ContractAbstraction<Wallet>,
            LegacyRoyalties_contract: ContractAbstraction<Wallet>;
        {
            // prepare registry/royalties batch
            const tezland_batch = new DeployContractBatch(this);

            // Compile and deploy registry contract.
            await this.compile_contract("TL_TokenRegistry", "TL_TokenRegistry", "TL_TokenRegistry", [
                `administrator = sp.address("${this.accountAddress}")`,
                `collections_public_key = sp.key("${await this.getAccountPubkey("collections_signer")}")`
            ]);
            tezland_batch.addToBatch("TL_TokenRegistry");

            // Compile and deploy legacy royalties contract.
            await this.compile_contract("TL_LegacyRoyalties", "TL_LegacyRoyalties", "TL_LegacyRoyalties", [
                `administrator = sp.address("${this.accountAddress}")`
            ]);
            tezland_batch.addToBatch("TL_LegacyRoyalties");

            [Registry_contract, LegacyRoyalties_contract] = await tezland_batch.deployBatch();
        }

        //
        // Minter v2, Dutch v2, Places v2 and Interiors.
        //
        // TODO: deploy places and interiors as paused! Unpause when tzkt shows images and names.
        let Minter_v2_contract: ContractAbstraction<Wallet>,
            interiors_FA2_contract: ContractAbstraction<Wallet>,
            places_v2_FA2_contract: ContractAbstraction<Wallet>,
            items_v2_FA2_contract: ContractAbstraction<Wallet>;
        {
            const minterV2WasDeployed = this.getDeployment("TL_Minter_v2");

            // prepare minter/interiors batch
            const tezland_batch = new DeployContractBatch(this);

            // Compile and deploy Minter contract.
            await this.compile_contract("TL_Minter_v2", "TL_Minter_v2", "TL_Minter_v2", [
                `administrator = sp.address("${this.accountAddress}")`,
                `registry = sp.address("${Registry_contract.address}")`
            ]);
            tezland_batch.addToBatch("TL_Minter_v2");

            await this.compile_contract("FA2_Interiors", "Tokens", "tz1andInteriors", [
                `admin = sp.address("${this.accountAddress}")`
            ]);
            tezland_batch.addToBatch("FA2_Interiors");

            await this.compile_contract("FA2_Places_v2", "Tokens", "tz1andPlaces_v2", [
                `admin = sp.address("${this.accountAddress}")`
            ]);
            tezland_batch.addToBatch("FA2_Places_v2");

            await this.compile_contract("FA2_Items_v2", "Tokens", "tz1andItems_v2", [
                `admin = sp.address("${this.accountAddress}")`
            ]);
            tezland_batch.addToBatch("FA2_Items_v2");

            [Minter_v2_contract, interiors_FA2_contract, places_v2_FA2_contract, items_v2_FA2_contract] = await tezland_batch.deployBatch();

            if (!minterV2WasDeployed) {
                // Set the minter as the token administrator
                await this.run_op_task("Setting minter as token admin...", async () => {
                    return this.tezos!.wallet.batch().with([
                        // Transfer items and place admin from minter v1 to admin wallet.
                        {
                            kind: OpKind.TRANSACTION,
                            ...tezlandMinter.methods.transfer_fa2_administrator([
                                {fa2: tezlandItems.address, proposed_fa2_administrator: this.accountAddress},
                                {fa2: tezlandPlaces.address, proposed_fa2_administrator: this.accountAddress},
                            ]).toTransferParams()
                        },
                        // Transfer items v2 admin to minter v2
                        {
                            kind: OpKind.TRANSACTION,
                            ...items_v2_FA2_contract.methods.transfer_administrator(Minter_v2_contract.address).toTransferParams()
                        },
                        // accept v2 items admin in minter v2
                        {
                            kind: OpKind.TRANSACTION,
                            ...Minter_v2_contract.methods.token_administration([{accept_fa2_administrator: [items_v2_FA2_contract.address]}]).toTransferParams()
                        },
                        // add items and items v2 as public collection to minter v2
                        {
                            kind: OpKind.TRANSACTION,
                            ...Registry_contract.methods.manage_collections([{
                                add_public: {
                                    [tezlandItems.address]: 1,
                                    [items_v2_FA2_contract.address]: 2
                                }
                            }]).toTransferParams()
                        },
                        // accept places admin from wallet
                        {
                            kind: OpKind.TRANSACTION,
                            ...tezlandPlaces.methods.accept_administrator().toTransferParams()
                        },
                        // accept items admin from wallet
                        {
                            kind: OpKind.TRANSACTION,
                            ...tezlandItems.methods.accept_administrator().toTransferParams()
                        }
                    ]).send();
                });
            }
        }

        // Royalties adapters
        let RoyaltiesAdapterLegacyAndV1_contract: ContractAbstraction<Wallet>,
            RoyaltiesAdapter_contract: ContractAbstraction<Wallet>;
        {
            await this.compile_contract("TL_RoyaltiesAdapterLegacyAndV1", "TL_RoyaltiesAdapterLegacyAndV1", "TL_RoyaltiesAdapterLegacyAndV1", [
                `legacy_royalties = sp.address("${LegacyRoyalties_contract.address}")`
            ]);
            RoyaltiesAdapterLegacyAndV1_contract = await this.deploy_contract("TL_RoyaltiesAdapterLegacyAndV1");

            await this.compile_contract("TL_RoyaltiesAdapter", "TL_RoyaltiesAdapter", "TL_RoyaltiesAdapter", [
                `registry = sp.address("${Registry_contract.address}")`,
                `v1_and_legacy_adapter = sp.address("${RoyaltiesAdapterLegacyAndV1_contract.address}")`
            ]);
            RoyaltiesAdapter_contract = await this.deploy_contract("TL_RoyaltiesAdapter");
        }

        //
        // World v2 (Marketplaces)
        //
        let World_v2_contract: ContractAbstraction<Wallet>;
        {
            const worldV2WasDeployed = this.getDeployment("TL_World_v2");

            // Compile and deploy Places contract.
            // IMPORTANT NOTE: target name changed so on next mainnet deply it will automatically deploy the v2!
            await this.compile_contract("TL_World_v2", "TL_World_v2", "TL_World_v2", [
                `administrator = sp.address("${this.accountAddress}")`,
                `registry = sp.address("${Registry_contract.address}")`,
                `royalties_adapter = sp.address("${RoyaltiesAdapter_contract.address}")`,
                `paused = sp.bool(True)`,
                `items_tokens = sp.address("${tezlandItems.address}")`,
                `name = "tz1and World"`,
                `description = "tz1and Virtual World v2"`,
                `debug_asserts = ${debug_asserts ? "True" : "False"}`
            ]);

            World_v2_contract = await this.deploy_contract("TL_World_v2");

            if (!worldV2WasDeployed) {
                await this.run_op_task("Set allowed place tokens on world...", async () => {
                    return World_v2_contract.methodsObject.set_allowed_place_token([
                        {
                            add: {
                                [places_v2_FA2_contract.address]: {
                                    chunk_limit: 2,
                                    chunk_item_limit: 64
                                },
                                [interiors_FA2_contract.address]: {
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
        // Token Factory and Dutch v2
        //
        // TODO: could probably deploy with world v2.
        let Factory_contract: ContractAbstraction<Wallet>,
            Dutch_v2_contract: ContractAbstraction<Wallet>;
        {
            const factoryWasDeployed = this.getDeployment("TL_TokenFactory");

            // prepare minter/interiors batch
            const tezland_batch = new DeployContractBatch(this);

            // Compile and deploy fa2 factory contract.
            await this.compile_contract("TL_TokenFactory", "TL_TokenFactory", "TL_TokenFactory", [
                `administrator = sp.address("${this.accountAddress}")`,
                `registry = sp.address("${Registry_contract.address}")`,
                `minter = sp.address("${Minter_v2_contract.address}")`
            ]);
            tezland_batch.addToBatch("TL_TokenFactory");

            // Compile and deploy Minter contract.
            await this.compile_contract("TL_Dutch_v2", "TL_Dutch_v2", "TL_Dutch_v2", [
                `administrator = sp.address("${this.accountAddress}")`,
                `world_contract = sp.address("${World_v2_contract.address}")`
            ]);
            tezland_batch.addToBatch("TL_Dutch_v2");

            [Factory_contract, Dutch_v2_contract] = await tezland_batch.deployBatch();

            if (!factoryWasDeployed) {
                await this.run_op_task("Giving registry permissions to factory contract...", async () => {
                    return this.tezos!.wallet.batch().with([
                        {
                            kind: OpKind.TRANSACTION,
                            ...Registry_contract.methods.manage_permissions([{add_permissions: [Factory_contract.address]}]).toTransferParams()
                        },
                        // add permitted FA2s in dutch v2
                        {
                            kind: OpKind.TRANSACTION,
                            ...Dutch_v2_contract.methods.manage_whitelist([
                                {add_permitted: {
                                    [places_v2_FA2_contract.address]: { whitelist_enabled: false, whitelist_admin: this.accountAddress },
                                    [interiors_FA2_contract.address]: { whitelist_enabled: false, whitelist_admin: this.accountAddress }
                                }}
                            ]).toTransferParams()
                        }
                    ]).send();
                });
            }
        }

        // TODO: move dutch v2 orig here

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
                `world_v2_contract = sp.address("${World_v2_contract.address}")`,
                `world_v2_place_contract = sp.address("${places_v2_FA2_contract.address}")`
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

        const dutch_v1_1_metadata = await this.upgrade_entrypoint(tezlandDutchAuctions,
            "TL_Dutch_deprecate", "upgrades/TL_Dutch_v1_1", "TL_Dutch_v1_1",
            // contract params
            [
                `administrator = sp.address("${this.accountAddress}")`,
                `items_contract = sp.address("${tezlandItems.address}")`,
                `places_contract = sp.address("${tezlandPlaces.address}")`
            ],
            // entrypoints to upgrade
            ["cancel", "bid"], true);

        // TODO: upgrade dutch v1 to be able to cancel auctions and metadata

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

        await this.run_op_task("Updating metadata on v1 dutch contract...", async () => {
            assert(dutch_v1_1_metadata);
            return tezlandDutchAuctions.methodsObject.bid({
                auction_id: 0,
                extension: MichelsonMap.fromLiteral({ "metadata_uri": char2Bytes(dutch_v1_1_metadata) })
            }).send();
        });

        await this.run_op_task("Updating metadata on v1 minter contract...", async () => {
            assert(minter_v1_1_metadata);
            return tezlandMinter.methodsObject.mint_Place([{
                to_: this.accountAddress,
                metadata: MichelsonMap.fromLiteral({ "metadata_uri": char2Bytes(minter_v1_1_metadata) })
            }]).send();
        });

        // Cancel v1 auctions
        await this.cancelV1AuctionsAndPauseTransfers(tezlandDutchAuctions, tezlandPlaces);

        // Re-mint and re-distribute place tokens.
        await this.reDistributePlaces(places_v2_FA2_contract, tezlandPlaces);

        // Run world migration.
        await this.migrateWorld(World_v2_contract, tezlandWorld, places_v2_FA2_contract);

        //
        // Post deploy
        //
        await this.runPostDeploy(deploy_mode, new Map(Object.entries({
            items_FA2_contract: tezlandItems,
            items_v2_FA2_contract: items_v2_FA2_contract,
            places_FA2_contract: tezlandPlaces,
            places_v2_FA2_contract: places_v2_FA2_contract,
            interiors_FA2_contract: interiors_FA2_contract,
            dao_FA2_contract: tezlandDAO,
            Minter_contract: tezlandMinter,
            Minter_v2_contract: Minter_v2_contract,
            World_contract: tezlandWorld,
            World_v2_contract: World_v2_contract,
            Dutch_contract: tezlandDutchAuctions,
            Dutch_v2_contract: Dutch_v2_contract,
            Factory_contract: Factory_contract,
            Registry_contract: Registry_contract,
            LegacyRoyalties_contract: LegacyRoyalties_contract,
            RoyaltiesAdapter_contract: RoyaltiesAdapter_contract
        })));
    }

    protected async cancelV1AuctionsAndPauseTransfers(tezlandDutchAuctions: WalletContract, tezlandPlaces: WalletContract) {
        const v1auctionstorage = (await tezlandDutchAuctions.storage()) as any;

        // TODO: maybe get list of auctions from indexer instead?
        const auction_id = v1auctionstorage.auction_id;

        const batch = this.tezos!.wallet.batch();

        for (let id = 0; id < auction_id; ++id) {
            const auction = await v1auctionstorage.auctions.get(id);
            if (auction) {
                console.log(`Cancelling auction #${id}.`);
                batch.with([{
                    kind: OpKind.TRANSACTION,
                    ...tezlandDutchAuctions.methodsObject.cancel({auction_id: id}).toTransferParams()
                }])
            }
        }

        // finally, pause place transfers.
        batch.with([{
            kind: OpKind.TRANSACTION,
            ...tezlandPlaces.methods.set_pause(true).toTransferParams()
        }])

        await this.run_op_task("Cancel V1 auctions and pause V1 place transfers", () => {
            return batch.send();
        });

        // TODO: set auctions cancelled in deploy reg
    }

    protected async reDistributePlaces(tezlandPlacesV2: WalletContract, tezlandPlacesV1: WalletContract) {
        const num_tokens = await tezlandPlacesV1.contractViews.count_tokens().executeView({viewCaller: this.accountAddress!});

        const v1placestorage = (await tezlandPlacesV1.storage()) as any;

        // get metadata map.
        const metadata_map = new Map<number, string>();
        for (let i = 0; i < num_tokens; ++i) {
            const entry = await v1placestorage.token_metadata.get(i);
            metadata_map.set(i, bytes2Char(entry.token_info.get("")!));
        }

        // Get owner map.
        const owner_map = new Map<number, string>();
        for (let i = 0; i < num_tokens; ++i) {
            const address = await v1placestorage.ledger.get(i);
            owner_map.set(i, address);
        }

        // Make sure no places are owned by contracts.
        owner_map.forEach((v, k) => {
            if(v.startsWith("KT")) throw new Error(`Error: Place #${k} is owned by contract.`);
        });

        // re-mint and -distribute places in v2.

        // TODO: do in batches of 100 or so. record last id in reg.

        const mint_batch: any[] = [];
        for (let i = 0; i < num_tokens; ++i) {
            const metadata = new MichelsonMap<string,string>({ prim: "map", args: [{prim: "string"}, {prim: "bytes"}]});
            metadata.set('', char2Bytes(metadata_map.get(i)!));
            mint_batch.push({
                to_: owner_map.get(i)!,
                metadata: metadata
            });
        }

        await this.run_op_task("Re-mint places", () => {
            return tezlandPlacesV2.methodsObject.mint(mint_batch).send();
        });

        // TODO: set places re-distributed in deploy reg.
    }

    protected async migrateWorld(tezlandWorldV2: WalletContract, tezlandWorldV1: WalletContract, tezlandPlacesV2: WalletContract) {
        await this.run_op_task("Set migration contract on World v2...", async () => {
            return tezlandWorldV2.methods.update_settings([{migration_from: tezlandWorldV1.address}]).send()
        });

        const num_tokens = await tezlandPlacesV2.contractViews.count_tokens().executeView({viewCaller: this.accountAddress!});

        const v1worldtorage = (await tezlandWorldV1.storage()) as any;

        // TODO: do in batches of 100 or so. record last id in reg.

        const batch = this.tezos!.wallet.batch();
        for (let i = 0; i < num_tokens; ++i) {
            // Check if place is empty. If it is, skip migration.
            const place = await v1worldtorage.places.get(i);
            if (!place) {
                console.log(`Place #${i} is empty, skipping.`);
                continue;
            }

            batch.with([{
                kind: OpKind.TRANSACTION,
                ...tezlandWorldV1.methodsObject.set_item_data({
                    lot_id: i,
                    update_map: new MichelsonMap()
                }).toTransferParams()
            }])
        }

        // @ts-expect-error
        if (batch.operations.length > 0)
            await this.run_op_task("Migrate world", () => {
                return batch.send();
            });

        await this.run_op_task("World v2: Remove migration contract and unpause...", async () => {
            return tezlandWorldV2.methods.update_settings([{migration_from: null}, {paused: false}]).send()
        });

        // TODO: set world migrated in deploy reg.
    }
}
