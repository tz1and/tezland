import * as ipfs from '../ipfs'
import { char2Bytes, bytes2Char } from '@taquito/utils'
import assert from 'assert';
import kleur from 'kleur';
import { DeployContractBatch } from './DeployBase';
import { ContractAbstraction, MichelsonMap, OpKind, Wallet, WalletContract, MichelCodecPacker } from '@taquito/taquito';
import { MichelsonV1Expression } from '@taquito/rpc';
import { Schema } from '@taquito/michelson-encoder';
import PostUpgrade from './postupgrade';
import config from '../user.config';
import { DeployMode } from '../config/config';
import BigNumber from 'bignumber.js'
import fs from 'fs';


export default class Upgrade extends PostUpgrade {
    protected override async deployDo() {
        assert(this.tezos);

        // If this is a sandbox deploy, run the post deploy tasks.
        const deploy_mode = this.isSandboxNet ? config.sandbox.deployMode : DeployMode.None;
        const debug_asserts = this.isSandboxNet && (deploy_mode != DeployMode.GasTest);

        console.log(kleur.magenta(`Compiling with debug_asserts=${debug_asserts}\n`))

        //
        // Get v1 deployments.
        //
        const tezlandItems = await this.tezos.wallet.at(this.deploymentsReg.getContract("FA2_Items")!);
        const tezlandPlaces = await this.tezos.wallet.at(this.deploymentsReg.getContract("FA2_Places")!);
        const tezlandDAO = await this.tezos.wallet.at(this.deploymentsReg.getContract("FA2_DAO")!);
        const tezlandWorld = await this.tezos.wallet.at(this.deploymentsReg.getContract("TL_World")!);
        const tezlandMinter = await this.tezos.wallet.at(this.deploymentsReg.getContract("TL_Minter")!);
        const tezlandDutchAuctions = await this.tezos.wallet.at(this.deploymentsReg.getContract("TL_Dutch")!);

        //
        // Pause World v1 and Minter v1 for upgrade.
        //
        await this.run_flag_task("pause_for_v2_upgrade", async () => {
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
        });

        //
        // Token Registry, Legacy Royalties, Blacklist
        //
        let Registry_contract: ContractAbstraction<Wallet>,
            LegacyRoyalties_contract: ContractAbstraction<Wallet>,
            Blacklist_contract: ContractAbstraction<Wallet>;;
        {
            const tezland_batch = new DeployContractBatch(this);

            // Compile and deploy registry contract.
            await tezland_batch.addToBatch("TL_TokenRegistry", "TL_TokenRegistry", "TL_TokenRegistry", [
                `administrator = sp.address("${this.accountAddress}")`,
                `collections_public_key = sp.key("${await this.getAccountPubkey("collections_signer")}")`
            ]);

            // Compile and deploy legacy royalties contract.
            await tezland_batch.addToBatch("TL_LegacyRoyalties", "TL_LegacyRoyalties", "TL_LegacyRoyalties", [
                `administrator = sp.address("${this.accountAddress}")`
            ]);

            // Blacklist
            await tezland_batch.addToBatch("TL_Blacklist", "TL_Blacklist", "TL_Blacklist", [
                `administrator = sp.address("${this.accountAddress}")`
            ], false);

            [Registry_contract, LegacyRoyalties_contract, Blacklist_contract] = await tezland_batch.deployBatch();
        }

        //
        // Place Proxy Parent
        //
        let PlaceTokenProxyParent_contract: ContractAbstraction<Wallet>;
        {
            PlaceTokenProxyParent_contract = await this.deploy_contract("PlaceTokenProxyParent", "Tokens", "PlaceTokenProxyParent", [
                `admin = sp.address("${this.accountAddress}")`,
                `parent = sp.address("${this.accountAddress}")`,
                `blacklist = sp.address("${Blacklist_contract.address}")`,
                `name="tz1and Place Token Proxy Parent"`,
                `description="tz1and Place tokens load code from this contract. It's useless otherwise."`
            ]);
        }

        //
        // Minter v2, Items v2, Places v2 and Interiors.
        //
        // TODO: deploy places and interiors as paused! Unpause when tzkt shows images and names.
        let Minter_v2_contract: ContractAbstraction<Wallet>,
            interiors_FA2_contract: ContractAbstraction<Wallet>,
            places_v2_FA2_contract: ContractAbstraction<Wallet>,
            items_v2_FA2_contract: ContractAbstraction<Wallet>;
        {
            const tezland_batch = new DeployContractBatch(this);

            // Compile and deploy Minter contract.
            await tezland_batch.addToBatch("TL_Minter_v2", "TL_Minter_v2", "TL_Minter_v2", [
                `administrator = sp.address("${this.accountAddress}")`,
                `registry = sp.address("${Registry_contract.address}")`
            ]);

            await tezland_batch.addToBatch("FA2_Interiors", "Tokens", "PlaceTokenProxyChild", [
                `admin = sp.address("${this.accountAddress}")`,
                `parent = sp.address("${PlaceTokenProxyParent_contract.address}")`,
                `blacklist = sp.address("${Blacklist_contract.address}")`,
                `name="tz1and Interiors"`,
                `description="tz1and Interior FA2 Tokens."`
            ]);

            await tezland_batch.addToBatch("FA2_Places_v2", "Tokens", "PlaceTokenProxyChild", [
                `admin = sp.address("${this.accountAddress}")`,
                `parent = sp.address("${PlaceTokenProxyParent_contract.address}")`,
                `blacklist = sp.address("${Blacklist_contract.address}")`,
                `name="tz1and Places"`,
                `description="tz1and Place FA2 Tokens (v2)."`
            ]);

            // NOTE: Public collection is not a proxy, but it's lazy.
            await tezland_batch.addToBatch("FA2_Items_v2", "Tokens", "tz1andItems_v2", [
                `admin = sp.address("${this.accountAddress}")`
            ]);

            [Minter_v2_contract, interiors_FA2_contract, places_v2_FA2_contract, items_v2_FA2_contract] = await tezland_batch.deployBatch();

            await this.run_flag_task("minter_v2_initialised", async () => {
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
            });
        }

        // Royalties adapters
        let RoyaltiesAdapterLegacyAndV1_contract: ContractAbstraction<Wallet>,
            RoyaltiesAdapter_contract: ContractAbstraction<Wallet>;
        {
            RoyaltiesAdapterLegacyAndV1_contract = await this.deploy_contract("TL_RoyaltiesAdapterLegacyAndV1", "TL_RoyaltiesAdapterLegacyAndV1", "TL_RoyaltiesAdapterLegacyAndV1", [
                `legacy_royalties = sp.address("${LegacyRoyalties_contract.address}")`
            ], false);

            RoyaltiesAdapter_contract = await this.deploy_contract("TL_RoyaltiesAdapter", "TL_RoyaltiesAdapter", "TL_RoyaltiesAdapter", [
                `registry = sp.address("${Registry_contract.address}")`,
                `v1_and_legacy_adapter = sp.address("${RoyaltiesAdapterLegacyAndV1_contract.address}")`
            ], false);
        }

        //
        // World v2 (Marketplaces)
        //
        let World_v2_contract: ContractAbstraction<Wallet>;
        {
            // Compile and deploy Places contract.
            // IMPORTANT NOTE: target name changed so on next mainnet deply it will automatically deploy the v2!
            World_v2_contract = await this.deploy_contract("TL_World_v2", "TL_World_v2", "TL_World_v2", [
                `administrator = sp.address("${this.accountAddress}")`,
                `registry = sp.address("${Registry_contract.address}")`,
                `royalties_adapter = sp.address("${RoyaltiesAdapter_contract.address}")`,
                `paused = sp.bool(True)`,
                `items_tokens = sp.address("${tezlandItems.address}")`,
                `name = "tz1and World"`,
                `description = "tz1and Virtual World v2"`,
                `debug_asserts = ${debug_asserts ? "True" : "False"}`
            ]);

            await this.run_flag_task("world_v2_initialised", async () => {
                await this.run_op_task("Set allowed place tokens on world...", async () => {
                    return this.tezos!.wallet.batch().with([
                        // Set fees to 3.5% on world contract.
                        {
                            kind: OpKind.TRANSACTION,
                            ...World_v2_contract.methods.update_settings([{fees: 35}]).toTransferParams()
                        },
                        // Set allowed place tokens on world
                        {
                            kind: OpKind.TRANSACTION,
                            ...World_v2_contract.methodsObject.set_allowed_place_token([{
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
                            }]).toTransferParams()
                        }
                    ]).send()
                });
            });
        }

        //
        // Item Collection Proxy Parent
        //
        let ItemCollectionProxyParent_contract: ContractAbstraction<Wallet>;
        {
            ItemCollectionProxyParent_contract = await this.deploy_contract("ItemCollectionProxyParent", "Tokens", "ItemCollectionProxyParent", [
                `admin = sp.address("${this.accountAddress}")`,
                `parent = sp.address("${this.accountAddress}")`,
                `blacklist = sp.address("${Blacklist_contract.address}")`
            ]);
        }

        //
        // Token Factory and Dutch v2
        //
        let Factory_contract: ContractAbstraction<Wallet>,
            Dutch_v2_contract: ContractAbstraction<Wallet>;
        {
            const tezland_batch = new DeployContractBatch(this);

            // Compile and deploy fa2 factory contract.
            await tezland_batch.addToBatch("TL_TokenFactory", "TL_TokenFactory", "TL_TokenFactory", [
                `administrator = sp.address("${this.accountAddress}")`,
                `registry = sp.address("${Registry_contract.address}")`,
                `minter = sp.address("${Minter_v2_contract.address}")`,
                `proxy_parent = sp.address("${ItemCollectionProxyParent_contract.address}")`,
                `blacklist = sp.address("${Blacklist_contract.address}")`
            ]);

            // Compile and deploy Minter contract.
            await tezland_batch.addToBatch("TL_Dutch_v2", "TL_Dutch_v2", "TL_Dutch_v2", [
                `administrator = sp.address("${this.accountAddress}")`,
                `world_contract = sp.address("${World_v2_contract.address}")`
            ]);

            [Factory_contract, Dutch_v2_contract] = await tezland_batch.deployBatch();

            await this.run_flag_task("dutch_v2_and_factory_initialised", async () => {
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
                        },
                        // Set fees to 6% on dutch contract.
                        {
                            kind: OpKind.TRANSACTION,
                            ...Dutch_v2_contract.methods.update_settings([{fees: 60}]).toTransferParams()
                        }
                    ]).send();
                });
            });
        }

        // TODO: deploy dutch separately. might not deploy factory immediately.

        //
        // Upgrade v1 contracts.
        //
        await this.run_flag_task("world_v1_1_upgraded", async () => {
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
                ["set_item_data", "get_item"]);

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
        });

        await this.run_flag_task("minter_v1_1_upgraded", async () => {
            const minter_v1_1_metadata = await this.upgrade_entrypoint(tezlandMinter,
                "TL_Minter_deprecate", "upgrades/TL_Minter_v1_1", "TL_Minter_v1_1",
                // contract params
                [
                    `administrator = sp.address("${this.accountAddress}")`,
                    `items_contract = sp.address("${tezlandItems.address}")`,
                    `places_contract = sp.address("${tezlandPlaces.address}")`
                ],
                // entrypoints to upgrade
                ["mint_Place"]);

            await this.run_op_task("Updating metadata on v1 minter contract...", async () => {
                assert(minter_v1_1_metadata);
                return tezlandMinter.methodsObject.mint_Place([{
                    to_: this.accountAddress,
                    metadata: MichelsonMap.fromLiteral({ "metadata_uri": char2Bytes(minter_v1_1_metadata) })
                }]).send();
            });
        });

        await this.run_flag_task("dutch_v1_1_upgraded", async () => {
            const dutch_v1_1_metadata = await this.upgrade_entrypoint(tezlandDutchAuctions,
                "TL_Dutch_deprecate", "upgrades/TL_Dutch_v1_1", "TL_Dutch_v1_1",
                // contract params
                [
                    `administrator = sp.address("${this.accountAddress}")`,
                    `items_contract = sp.address("${tezlandItems.address}")`,
                    `places_contract = sp.address("${tezlandPlaces.address}")`
                ],
                // entrypoints to upgrade
                ["cancel", "bid"]);

            await this.run_op_task("Updating metadata on v1 dutch contract...", async () => {
                assert(dutch_v1_1_metadata);
                return tezlandDutchAuctions.methodsObject.bid({
                    auction_id: 0,
                    extension: MichelsonMap.fromLiteral({ "metadata_uri": char2Bytes(dutch_v1_1_metadata) })
                }).send();
            });
        });

        //
        // Run upgrades.
        //

        var totalMigrationFee = new BigNumber(0);

        // Cancel v1 auctions
        await this.run_flag_task("auctions_v1_cancelled", async () => {
            await this.cancelV1AuctionsAndPauseTransfers(tezlandDutchAuctions, tezlandPlaces);
        });

        // Re-mint and re-distribute place tokens.
        await this.run_flag_task("places_redistributed", async () => {
            const placeRedistFee = await this.reDistributePlaces(places_v2_FA2_contract, tezlandPlaces);
            totalMigrationFee = totalMigrationFee.plus(placeRedistFee);
        });

        // Run world migration.
        await this.run_flag_task("world_migrated", async () => {
            const worldMigrationFee = await this.migrateWorld(World_v2_contract, tezlandWorld, places_v2_FA2_contract);
            totalMigrationFee = totalMigrationFee.plus(worldMigrationFee);
        });

        console.log("Total fee for migration:", totalMigrationFee.toNumber() / 1000000);

        //
        // Post deploy
        //
        await this.runPostDeploy(deploy_mode, new Map(Object.entries({
            ItemCollectionProxyParent_contract: ItemCollectionProxyParent_contract,
            PlaceProxyParent_contract: PlaceTokenProxyParent_contract,
            items_FA2_contract: tezlandItems, // Deprecated, but still usable
            items_v2_FA2_contract: items_v2_FA2_contract,
            places_FA2_contract: tezlandPlaces, // Deprecated
            places_v2_FA2_contract: places_v2_FA2_contract,
            interiors_FA2_contract: interiors_FA2_contract,
            dao_FA2_contract: tezlandDAO,
            Minter_contract: tezlandMinter, // Deprecated
            Minter_v2_contract: Minter_v2_contract,
            World_contract: tezlandWorld, // Deprecated
            World_v2_contract: World_v2_contract,
            Dutch_contract: tezlandDutchAuctions,// Deprecated
            Dutch_v2_contract: Dutch_v2_contract,
            Factory_contract: Factory_contract,
            Registry_contract: Registry_contract,
            LegacyRoyalties_contract: LegacyRoyalties_contract,
            RoyaltiesAdapter_contract: RoyaltiesAdapter_contract,
            Blacklist_contract: Blacklist_contract
        })));
    }

    protected async cancelV1AuctionsAndPauseTransfers(tezlandDutchAuctions: WalletContract, tezlandPlaces: WalletContract) {
        assert(this.tezos);
        const v1auctionstorage = (await tezlandDutchAuctions.storage()) as any;

        // TODO: maybe get list of auctions from indexer instead?
        const auction_id: BigNumber = v1auctionstorage.auction_id;

        const batch = this.tezos.wallet.batch();

        // TODO: use bignumber. auction_id surely is a bignumber.
        for (let id = new BigNumber(0); id.lt(auction_id); id=id.plus(1)) {
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
    }

    protected async reDistributePlaces(tezlandPlacesV2: WalletContract, tezlandPlacesV1: WalletContract) {
        assert(this.tezos);
        const num_tokens_v1: BigNumber = await tezlandPlacesV1.contractViews.count_tokens().executeView({viewCaller: this.accountAddress!});
        const num_tokens_v2: BigNumber = await tezlandPlacesV2.contractViews.count_tokens().executeView({viewCaller: this.accountAddress!});

        console.log("num_tokens_v1", num_tokens_v1.toNumber())
        console.log("num_tokens_v2", num_tokens_v2.toNumber())

        const v1placestorage = (await tezlandPlacesV1.storage()) as any;

        // get metadata map.
        const metadata_v1_map = new Map<number, string>();
        {
            const place_metadata_map_v1_path = `${this.deploymentsDir}/place_metadata_map_v1.json`;

            if (fs.existsSync(place_metadata_map_v1_path)) {
                console.log("Loading cached v1 metadata map...");
                const json_file = fs.readFileSync(place_metadata_map_v1_path).toString("utf-8");
                for (const [key, value] of Object.entries<string>(JSON.parse(json_file)))
                    metadata_v1_map.set(parseInt(key), value);
            }
            else {
                console.log("Fetching place metadata...");
                for (let i = new BigNumber(0); i.lt(num_tokens_v1); i=i.plus(1)) {
                    console.log("Fetching metadata for", i.toNumber());
                    const entry = await v1placestorage.token_metadata.get(i);
                    const metadata_bytes = entry.token_info.get("");
                    assert(metadata_bytes);
                    metadata_v1_map.set(i.toNumber(), bytes2Char(metadata_bytes));
                }

                // Write the metadata file
                fs.writeFileSync(place_metadata_map_v1_path, JSON.stringify(Object.fromEntries(metadata_v1_map)));
            }
        }

        // get v2 metadata map.
        // TODO: Need to parallelise place metadata re-upload?
        // Otherwise it could take 40+ minutes in prod.
        const metadata_v2_map = new Map<number, string>();
        {
            const place_metadata_map_v2_path = `${this.deploymentsDir}/place_metadata_map_v2.json`;

            if (fs.existsSync(place_metadata_map_v2_path)) {
                console.log("Loading cached v2 metadata map...");
                const json_file = fs.readFileSync(place_metadata_map_v2_path).toString("utf-8");
                for (const [key, value] of Object.entries<string>(JSON.parse(json_file)))
                    metadata_v2_map.set(parseInt(key), value);
            }
            else {
                console.log("Uploading v2 place metadata...");

                const royalties_address: string = "tz1UZFB9kGauB6F5c2gfJo4hVcvrD8MeJ3Vf";

                //const upload_promises: Promise<[number, string]>[] = [];

                const reupload_metadata = async (token_id: number, metadata_url: string): Promise<[number, string]> => {
                    console.log("Reuploading metadata for", token_id);
                    // Update royalties to be 10%.
                    const metadata_file = await ipfs.downloadFile(metadata_url);
                    const file_string = Buffer.from(metadata_file).toString('utf8');

                    const parsed_metadata = JSON.parse(file_string);
                    parsed_metadata.name = `tz1and Place #${token_id}`;
                    parsed_metadata.minter = this.accountAddress!;
                    parsed_metadata.symbol = "PLACE";
                    parsed_metadata.royalties = {
                        decimals: 3,
                        shares: Object.fromEntries(new Map([
                            [royalties_address, 100]
                        ]))
                    }

                    const updated_metadata = await ipfs.upload_metadata(parsed_metadata, this.isSandboxNet);

                    return [token_id, updated_metadata];
                }

                for (let i = new BigNumber(0); i.lt(num_tokens_v1); i=i.plus(1)) {
                    const metadata_url = metadata_v1_map.get(i.toNumber());
                    assert(metadata_url);
                    //upload_promises.push(reupload_metadata(i.toNumber(), metadata_url))
                    const [key, value] = await reupload_metadata(i.toNumber(), metadata_url);
                    metadata_v2_map.set(key, value);
                }

                /*for (const [key, value] of (await Promise.all(upload_promises))) {
                    metadata_v2_map.set(key, value);
                }*/

                // Write the metadata file
                fs.writeFileSync(place_metadata_map_v2_path, JSON.stringify(Object.fromEntries(metadata_v2_map)));
            }
        }

        // Get owner map.
        const owner_map = new Map<number, string>();
        {
            const place_owner_map_v1_path = `${this.deploymentsDir}/place_owner_map_v1.json`;

            if (fs.existsSync(place_owner_map_v1_path)) {
                console.log("Loading cached v1 place owner map...");
                const json_file = fs.readFileSync(place_owner_map_v1_path).toString("utf-8");
                for (const [key, value] of Object.entries<string>(JSON.parse(json_file)))
                    owner_map.set(parseInt(key), value);
            }
            else {
                console.log("Fetching place owners...");
                for (let i = new BigNumber(0); i.lt(num_tokens_v1); i=i.plus(1)) {
                    console.log("Fetching owner for", i.toNumber());
                    const address = await v1placestorage.ledger.get(i);
                    owner_map.set(i.toNumber(), address);
                }

                // Write the metadata file
                fs.writeFileSync(place_owner_map_v1_path, JSON.stringify(Object.fromEntries(owner_map)));
            }
        }

        // Make sure no places are owned by contracts.
        owner_map.forEach((v, k) => {
            if(v.startsWith("KT")) throw new Error(`Error: Place #${k} is owned by contract.`);
        });

        let totalFee = new BigNumber(0);

        // re-mint and -distribute places in v2.
        if (num_tokens_v1.minus(num_tokens_v2).gt(0)) {
            let mint_batch: any[] = [];
            for (let i = num_tokens_v2; i.lt(num_tokens_v1); i=i.plus(1)) {
                // Add to mint batch
                const metadata = new MichelsonMap<string,string>({ prim: "map", args: [{prim: "string"}, {prim: "bytes"}]});
                const metadata_url = metadata_v2_map.get(i.toNumber());
                assert(metadata_url);
                metadata.set('', char2Bytes(metadata_url));

                const place_owner = owner_map.get(i.toNumber());
                assert(place_owner);
                const current_place_list = [{
                    to_: place_owner,
                    metadata: metadata
                }];

                // Estimate size with added op. If too large, send batch.
                // Estimate should throw when limits are reached.
                try {
                    const mint_batch_temp = mint_batch.concat(current_place_list);
                    await this.tezos.estimate.transfer(tezlandPlacesV2.methodsObject.mint(mint_batch_temp).toTransferParams());
                    // If it succeeds, the temp batch becomes the new batch.
                    mint_batch = mint_batch_temp;
                } catch(e) {
                    // If it fails (op limits), send op.
                    const op = await this.run_op_task(`Re-mint places x${mint_batch.length}`, () => {
                        return tezlandPlacesV2.methodsObject.mint(mint_batch).send();
                    });
                    const receipt = await op.receipt();
                    console.log("Fee for this batch:", receipt.totalFee.plus(receipt.totalStorageBurn).toNumber() / 1000000);
                    totalFee = totalFee.plus(receipt.totalFee.plus(receipt.totalStorageBurn));
                    // And reset batch with the list that pushed it over the limit.
                    mint_batch = current_place_list;
                }
            }

            // If we have any places left to minter after, mint them.
            if (mint_batch.length > 0) {
                const op = await this.run_op_task(`Re-mint places x${mint_batch.length}`, () => {
                    return tezlandPlacesV2.methodsObject.mint(mint_batch).send();
                });
                const receipt = await op.receipt();
                console.log("Fee for this batch:", receipt.totalFee.plus(receipt.totalStorageBurn).toNumber() / 1000000);
                totalFee = totalFee.plus(receipt.totalFee.plus(receipt.totalStorageBurn));
            }
        }
        else {
            console.log("No places to re-mint.")
        }

        console.log("Total fee for re-distributing places:", totalFee.toNumber() / 1000000);

        return totalFee;
    }

    private async packSetNat(set: BigNumber[]) {
        // Type as michelson expression
        const setStorageType: MichelsonV1Expression = {
            prim: 'set', args: [ { prim: 'nat' }]
        };

        // Encode result as a michelson expression.
        const storageSchema = new Schema(setStorageType);
        const setEncoded = storageSchema.Encode(set);

        // Pack encoded michelson data.
        const packer = new MichelCodecPacker();
        const packedSet = await packer.packData({ data: setEncoded, type: setStorageType });
        return packedSet.packed;
    }

    protected async migrateWorld(tezlandWorldV2: WalletContract, tezlandWorldV1: WalletContract, tezlandPlacesV2: WalletContract) {
        assert(this.tezos);
        await this.run_op_task("Set migration contract on World v2...", async () => {
            return tezlandWorldV2.methods.update_settings([{migration_from: tezlandWorldV1.address}]).send()
        });

        const num_tokens: BigNumber = await tezlandPlacesV2.contractViews.count_tokens().executeView({viewCaller: this.accountAddress!});

        const v1worldstorage = (await tezlandWorldV1.storage()) as any;

        // TODO: do in batches of 100 or so. record last id in reg?

        let empty_places_skipped = 0;
        let totalFee = new BigNumber(0);

        //const batch = this.tezos!.wallet.batch();
        let batch_places: BigNumber[] = [];
        for (let i = new BigNumber(0); i.lt(num_tokens); i=i.plus(1)) {
            // Check if place is empty. If it is, skip migration.
            const place = await v1worldstorage.places.get(i);
            if (!place) {
                //console.log(`Place #${i} is empty, skipping.`);
                ++empty_places_skipped;
                continue;
            }

            // Estimate size with added op. If too large, send batch.
            // Estimate should throw when limits are reached.
            try {
                const batch_places_temp = batch_places.concat([i]);
                await this.tezos.estimate.transfer(tezlandWorldV1.methodsObject.set_item_data({
                    lot_id: 0,
                    update_map: new MichelsonMap(),
                    extension: {"place_set": await this.packSetNat(batch_places_temp)}
                }).toTransferParams());
                // If it succeeds, the temp batch becomes the new batch.
                batch_places = batch_places_temp;
            } catch(e) {
                // If it fails (op limits), send op.
                const op = await this.run_op_task(`Migrate world x${batch_places.length}`, async () => {
                    return tezlandWorldV1.methodsObject.set_item_data({
                        lot_id: 0,
                        update_map: new MichelsonMap(),
                        extension: {"place_set": await this.packSetNat(batch_places)}
                    }).send();
                });
                const receipt = await op.receipt();
                console.log("Fee for this batch:", receipt.totalFee.plus(receipt.totalStorageBurn).toNumber() / 1000000);
                totalFee = totalFee.plus(receipt.totalFee.plus(receipt.totalStorageBurn));
                // And reset batch with the list that pushed it over the limit.
                batch_places = [i];
            }
        }

        if (batch_places.length > 0) {
            const op = await this.run_op_task(`Migrate world x${batch_places.length}`, async () => {
                return tezlandWorldV1.methodsObject.set_item_data({
                    lot_id: 0,
                    update_map: new MichelsonMap(),
                    extension: {"place_set": await this.packSetNat(batch_places)}
                }).send();
            });
            const receipt = await op.receipt();
            console.log("Fee for this batch:", receipt.totalFee.plus(receipt.totalStorageBurn).toNumber() / 1000000);
            totalFee = totalFee.plus(receipt.totalFee.plus(receipt.totalStorageBurn));
        }

        console.log("Empty places skipped:", empty_places_skipped);
        console.log("Total fee for migrating world:", totalFee.toNumber() / 1000000);

        await this.run_op_task("World v2: Remove migration contract...", async () => {
            return tezlandWorldV2.methods.update_settings([{migration_from: null}]).send()
        });

        // NOTE: world must be unpaused manually for prod!
        if (this.isSandboxNet) {
            await this.run_op_task("World v2: Unpause for dev...", async () => {
                return tezlandWorldV2.methods.update_settings([{paused: false}]).send()
            });
        }

        return totalFee;
    }
}
