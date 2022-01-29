import * as child from 'child_process';
import * as kleur from 'kleur';
import { TezosToolkit, VIEW_LAMBDA } from '@taquito/taquito';
import { InMemorySigner } from "@taquito/signer";
const sleep = require('util').promisify(setTimeout);

const bcdtag = "4.0.1337"

export async function start(): Promise<void> {
    console.log(kleur.yellow('starting sandbox...'));

    try {
        child.execSync(
            `COMPOSE_PROJECT_NAME=bcdbox TAG=${bcdtag} docker-compose -f docker-compose.yml up -d`,
            {stdio: 'inherit'}
        )

        /*console.log("Waiting to deploy lambda view contract");
        await sleep(20000);

        // Create signer and toolkit
        if (!process.env.TEZOS_RPC_URL) throw Error("TEZOS_RPC_URL not set");
        if (!process.env.ORIGINATOR_PRIVATE_KEY) throw Error("ORIGINATOR_PRIVATE_KEY not set");

        const { TEZOS_RPC_URL, ORIGINATOR_PRIVATE_KEY } = process.env;

        const signer = await InMemorySigner.fromSecretKey(ORIGINATOR_PRIVATE_KEY);
        const Tezos = new TezosToolkit(TEZOS_RPC_URL);
        Tezos.setProvider({ signer: signer });

        const op = await Tezos.contract.originate({
            code: VIEW_LAMBDA.code,
            storage: VIEW_LAMBDA.storage,
        });

        const lambdaContract = await op.contract();
        console.log("Lambda view contract: " + lambdaContract.address);*/
    } catch (err) {
        console.log(kleur.red("failed to start sandbox: " + err))
    }
}

export async function kill(): Promise<void> {
    console.log(kleur.yellow('killing sandbox...'));

    try {
        child.execSync(
            `COMPOSE_PROJECT_NAME=bcdbox TAG=${bcdtag} docker-compose -f docker-compose.yml down -v`,
            {stdio: 'inherit'}
        )
    } catch (err) {
        console.log(kleur.red("failed to kill sandbox"))
    }
}

export async function info(): Promise<void> {
    try {
        child.execSync(
            `COMPOSE_PROJECT_NAME=bcdbox TAG=${bcdtag} docker-compose exec flextesa granabox info`,
            {stdio: 'inherit'}
        )
    } catch (err) {
        console.log(kleur.red("failed to get sandbox info"))
    }
}