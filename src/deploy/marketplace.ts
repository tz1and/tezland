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

        //
        // Post deploy
        //
        await this.runPostDeploy(deploy_mode, new Map(Object.entries({
            Factory_contract: Factory_contract,
            Registry_contract: Registry_contract,
            LegacyRoyalties_contract: LegacyRoyalties_contract,
            RoyaltiesAdapter_contract: RoyaltiesAdapter_contract
        })));
    }
}
