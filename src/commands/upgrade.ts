import * as smartpy from './smartpy';
import * as ipfs from '../ipfs'
import { char2Bytes } from '@taquito/utils'
import assert from 'assert';
import kleur from 'kleur';
import DeployBase, { DeployContractBatch, sleep } from './DeployBase';
import { ContractAbstraction, MichelsonMap, OpKind, TransactionWalletOperation, Wallet, WalletOperationBatch } from '@taquito/taquito';
import fs from 'fs';


// some issues: dependent transactions: setting adming, etc
export default class Upgrade extends DeployBase {
    constructor(options: any) {
        super(options);
        this.cleanDeploymentsInSandbox = false;
    }

    // Compiles metadata, uploads it and then compiles again with metadata set.
    // Note: target_args needs to exclude metadata.
    private upgrade_entrypoint(target_name: string, file_name: string, contract_name: string, target_args: string[], entrypoints: string[]) {
        // Compile contract with metadata set.
        smartpy.upgrade_newtarget(target_name, file_name, contract_name, target_args.concat(['metadata = sp.utils.metadata_of_url("metadata_dummy")']), entrypoints);
    }

    protected override async deployDo() {
        assert(this.tezos);

        // TODO: get from deployments
        //const items_address = this.getDeployment("FA2_Items");
        const items_address = "KT1HgHtvNxzQrkCnZtTL5a3omcYHKZ7fKdqW";
        const places_address = "KT1HgHtvNxzQrkCnZtTL5a3omcYHKZ7fKdqW";
        const dao_address = "KT1HgHtvNxzQrkCnZtTL5a3omcYHKZ7fKdqW";

        this.upgrade_entrypoint("TL_World_upgrade_migrate", "TL_World_upgrade_migrate", "TL_World_upgrade_migrate", [`administrator = sp.address("${this.accountAddress}")`,
            `items_contract = sp.address("${items_address}")`,
            `places_contract = sp.address("${places_address}")`,
            `dao_contract = sp.address("${dao_address}")`],
            ["set_item_data"]);

        const world_contract = await this.tezos.wallet.at(this.getDeployment("TL_World"));

        const upgrade_op = await world_contract.methodsObject.update_ep({
            ep_name: {set_item_data: null},
            new_code: JSON.parse(fs.readFileSync(`./build/TL_World_upgrade_migrate_ep__set_item_data.json`, "utf-8"))
        }).send();
        await upgrade_op.confirmation();
    }
}
