import assert from 'assert';
import kleur from 'kleur';
import MinterBlacklistPostDeploy from './minterblacklist-post';
import config from '../user.config';
import { DeployMode } from '../config/config';
import { char2Bytes, bytes2Char } from '@taquito/utils'
import { MichelsonMap } from '@taquito/taquito';


export default class MinterBlacklist extends MinterBlacklistPostDeploy {
    protected override async deployDo() {
        assert(this.tezos);

        // If this is a sandbox deploy, run the post deploy tasks.
        const deploy_mode = this.isSandboxNet ? config.sandbox.deployMode : DeployMode.None;
        const debug_asserts = this.isSandboxNet && (deploy_mode != DeployMode.GasTest);

        console.log(kleur.magenta(`Compiling with debug_asserts=${debug_asserts}\n`))

        //
        // Get v2 deployments.
        //
        const Minter_v2_contract = await this.tezos.wallet.at(this.deploymentsReg.getContract("TL_Minter_v2")!);
        const Blacklist_contract = await this.tezos.wallet.at(this.deploymentsReg.getContract("TL_Blacklist")!);
        const Registry_contract = await this.tezos.wallet.at(this.deploymentsReg.getContract("TL_TokenRegistry")!);

        //
        // Upgrade minter
        //
        await this.run_flag_task("minter_v2_1_upgraded", async () => {
            const minter_v2_1_metadata = await this.upgrade_entrypoint(Minter_v2_contract,
                "TL_minter_v2_blacklist", "upgrades/TL_Minter_v2_1", "TL_Minter_v2_1",
                // contract params
                [
                    `administrator = sp.address("${this.accountAddress}")`,
                    `registry = sp.address("${Registry_contract.address}")`,
                    `blacklist = sp.address("${Blacklist_contract.address}")`
                ],
                // entrypoints to upgrade
                ["mint_public", "mint_private"], "byId");

            // Update metadata on v1 contracts
            await this.run_op_task("Updating metadata on v2 minter contract...", async () => {
                assert(minter_v2_1_metadata);
                return Minter_v2_contract.methods.update_settings([{metadata: MichelsonMap.fromLiteral({ "": char2Bytes(minter_v2_1_metadata) })}]).send();
            });
        });

        //
        // Post deploy
        //
        await this.runPostDeploy(deploy_mode, new Map());
    }
}
