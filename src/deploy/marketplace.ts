import * as ipfs from '../ipfs'
import { char2Bytes, bytes2Char } from '@taquito/utils'
import assert from 'assert';
import kleur from 'kleur';
import { DeployContractBatch } from '../commands/DeployBase';
import { ContractAbstraction, MichelsonMap, OpKind, Wallet, WalletContract, MichelCodecPacker } from '@taquito/taquito';
import { MichelsonV1Expression } from '@taquito/rpc';
import { Schema } from '@taquito/michelson-encoder';
import MarketplacePostDeploy from './marketplace-post';
import config from '../user.config';
import { DeployMode } from '../config/config';
import BigNumber from 'bignumber.js'
import fs from 'fs';


export default class Merketplace extends MarketplacePostDeploy {
    protected override async deployDo() {
        assert(this.tezos);

        // If this is a sandbox deploy, run the post deploy tasks.
        const deploy_mode = this.isSandboxNet ? config.sandbox.deployMode : DeployMode.None;
        const debug_asserts = this.isSandboxNet && (deploy_mode != DeployMode.GasTest);

        console.log(kleur.magenta(`Compiling with debug_asserts=${debug_asserts}\n`))

        //
        // Get v2 deployments.
        //
        const LegacyRoyalties_contract = await this.tezos.wallet.at(this.deploymentsReg.getContract("TL_LegacyRoyalties")!);
        const RoyaltiesAdapter_contract = await this.tezos.wallet.at(this.deploymentsReg.getContract("TL_RoyaltiesAdapter")!);
        const Registry_contract = await this.tezos.wallet.at(this.deploymentsReg.getContract("TL_TokenRegistry")!);
        const Factory_contract = await this.tezos.wallet.at(this.deploymentsReg.getContract("TL_TokenFactory")!);
        const FA2_Items_v2 = await this.tezos.wallet.at(this.deploymentsReg.getContract("FA2_Items_v2")!);

        //
        // Deploy marketplace
        //
        let Marketplace_contract = await this.deploy_contract("TL_Marketplace", "TL_Marketplace", "TL_Marketplace", [
            `administrator = sp.address("${this.accountAddress}")`,
            `registry = sp.address("${Registry_contract.address}")`,
            `royalties_adapter = sp.address("${RoyaltiesAdapter_contract.address}")`
        ]);

        //
        // Post deploy
        //
        await this.runPostDeploy(deploy_mode, new Map(Object.entries({
            items_v2_FA2_contract: FA2_Items_v2,
            Factory_contract: Factory_contract,
            Registry_contract: Registry_contract,
            LegacyRoyalties_contract: LegacyRoyalties_contract,
            RoyaltiesAdapter_contract: RoyaltiesAdapter_contract,
            Marketplace_contract: Marketplace_contract
        })));
    }
}
