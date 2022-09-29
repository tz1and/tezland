import * as child from 'child_process';
import * as kleur from 'kleur';
import config from '../user.config';
const sleep = require('util').promisify(setTimeout);

const bcdtag = "pr-914"
const sandbox_version = "20220510"
const sandbox_type = "ithacabox"

function configEnv(): string {
    return `TAG=${bcdtag} SANDBOX_VERSION=${sandbox_version} SANDBOX_TYPE=${sandbox_type} SANDBOX_BLOCKTIME=${config.sandbox.blockTime}`;
}

export async function start(full?: boolean): Promise<void> {
    console.log(kleur.yellow('starting sandbox...'));

    try {
        /*child.execSync(
            `COMPOSE_PROJECT_NAME=bcdbox TAG=${bcdtag} docker-compose -f docker-compose.yml pull`,
            {stdio: 'inherit'}
        )*/

        const containers = full ? '' : 'ipfs';

        const command = `COMPOSE_PROJECT_NAME=bcdbox ${configEnv()} docker-compose -f docker-compose.yml up -d ${containers}`;
        console.log("running: ", command);
        child.execSync(
            command,
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

export async function pull(): Promise<void> {
    console.log(kleur.yellow('pulling sandbox...'));

    try {
        const command = `COMPOSE_PROJECT_NAME=bcdbox ${configEnv()} docker-compose -f docker-compose.yml pull`;
        console.log("running: ", command);
        child.execSync(
            command,
            {stdio: 'inherit'}
        )
    } catch (err) {
        console.log(kleur.red("failed to pull sandbox"))
    }
}

export async function kill(): Promise<void> {
    console.log(kleur.yellow('killing sandbox...'));

    try {
        const command = `COMPOSE_PROJECT_NAME=bcdbox ${configEnv()} docker-compose -f docker-compose.yml down -v`;
        console.log("running: ", command);
        child.execSync(
            command,
            {stdio: 'inherit'}
        )
    } catch (err) {
        console.log(kleur.red("failed to kill sandbox"))
    }
}

export async function logs(): Promise<void> {
    console.log(kleur.yellow('killing sandbox...'));

    try {
        const command = `COMPOSE_PROJECT_NAME=bcdbox ${configEnv()} docker-compose -f docker-compose.yml logs -f`;
        console.log("running: ", command);
        child.execSync(
            command,
            {stdio: 'inherit'}
        )
    } catch (err) {
        console.log(kleur.red("failed to kill sandbox"))
    }
}

export async function info(): Promise<void> {
    try {
        child.execSync(
            `COMPOSE_PROJECT_NAME=bcdbox ${configEnv()} docker-compose exec flextesa ${sandbox_type} info`,
            {stdio: 'inherit'}
        )
    } catch (err) {
        console.log(kleur.red("failed to get sandbox info"))
    }
}