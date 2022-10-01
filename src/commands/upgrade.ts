import * as smartpy from './smartpy';
import * as ipfs from '../ipfs'
import { char2Bytes } from '@taquito/utils'
import assert from 'assert';
import kleur from 'kleur';
import DeployBase, { DeployContractBatch, sleep } from './DeployBase';
import { ContractAbstraction, MichelsonMap, OpKind, TransactionWalletOperation, Wallet, WalletOperationBatch } from '@taquito/taquito';
import fs from 'fs';


// TODO: need to move the deploy code here and make it update from v1.


export default class Upgrade extends DeployBase {
    constructor(options: any) {
        super(options);
        this.cleanDeploymentsInSandbox = false;
    }

    // Compiles contract, extracts lazy entrypoint code and deploys the updates.
    // Note: target_args needs to exclude metadata.
    private async upgrade_entrypoint(contract: ContractAbstraction<Wallet>, target_name: string, file_name: string, contract_name: string, target_args: string[], entrypoints: string[]) {
        // Compile contract with metadata set.
        // TODO: should return map from ep to filename?
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

        console.log();
    }

    protected override async deployDo() {
        assert(this.tezos);

        // get v1 deployments.
        const tezlandItems = await this.tezos.wallet.at(this.getDeployment("FA2_Items"));
        const tezlandPlaces = await this.tezos.wallet.at(this.getDeployment("FA2_Places"));
        const tezlandDAO = await this.tezos.wallet.at(this.getDeployment("FA2_DAO"));
        const tezlandWorld = await this.tezos.wallet.at(this.getDeployment("TL_World"));
        const tezlandMinter = await this.tezos.wallet.at(this.getDeployment("TL_Minter"));
        const tezlandDutchAuctions = await this.tezos.wallet.at(this.getDeployment("TL_Dutch"));

        await this.upgrade_entrypoint(tezlandWorld, "TL_World_upgrade_migrate", "TL_World_upgrade_migrate", "TL_World_upgrade_migrate", [`administrator = sp.address("${this.accountAddress}")`,
            `items_contract = sp.address("${tezlandItems.address}")`,
            `places_contract = sp.address("${tezlandPlaces.address}")`,
            `dao_contract = sp.address("${tezlandDAO.address}")`,
            `name = "tz1and World"`,
            `description = "tz1and Virtual World"`],
            ["set_item_data", "get_item"]);
    }
}
