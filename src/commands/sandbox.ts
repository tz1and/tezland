import * as child from 'child_process';
import kleur from 'kleur';
import config from '../user.config';
import { promisify } from 'util';
const sleep = promisify(setTimeout);


function configEnv(): string {
    return `COMPOSE_PROJECT_NAME=bcdbox TAG=${config.sandbox.bcdVersion} \
TZKT_VERSION=${config.sandbox.tzktVersion} \
SANDBOX_VERSION=${config.sandbox.flextesaVersion} \
SANDBOX_TYPE=${config.sandbox.flextesaProtocol} \
SANDBOX_BLOCKTIME=${config.sandbox.blockTime}`;
}

export async function start(full?: boolean): Promise<void> {
    console.log(kleur.yellow('starting sandbox...'));

    try {
        /*child.execSync(
            `TAG=${bcdtag} docker-compose -f docker-compose.yml pull`,
            {stdio: 'inherit'}
        )*/

        const containers = full ? '' : 'ipfs';

        const command = `${configEnv()} docker-compose -f docker-compose.yml up -d ${containers}`;
        console.log("running:", command);
        child.execSync(
            command,
            {stdio: 'inherit'}
        )

        // Sleep a couple of seconds to make sure everything is actually started.
        await sleep(5000);

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

export async function pull(services: string[]): Promise<void> {
    console.log(kleur.yellow('pulling sandbox... ' + services.join(' ')));

    try {
        const command = `${configEnv()} docker-compose -f docker-compose.yml pull ${services.join(' ')}`;
        console.log("running:", command);
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
        const command = `${configEnv()} docker-compose -f docker-compose.yml down -v`;
        console.log("running:", command);
        child.execSync(
            command,
            {stdio: 'inherit'}
        )
    } catch (err) {
        console.log(kleur.red("failed to kill sandbox"))
    }
}

export async function logs(services: string[]): Promise<void> {
    console.log(kleur.yellow('sandbox logs... ' + services.join(' ')));

    try {
        const command = `${configEnv()} docker-compose -f docker-compose.yml logs -f ${services.join(' ')}`;
        console.log("running:", command);
        child.execSync(
            command,
            {stdio: 'inherit'}
        )
    } catch (err) {
        console.log(kleur.red("failed start sandbox log"))
    }
}

export async function info(): Promise<void> {
    try {
        child.execSync(
            `${configEnv()} docker-compose exec flextesa ${config.sandbox.flextesaProtocol} info`,
            {stdio: 'inherit'}
        )
    } catch (err) {
        console.log(kleur.red("failed to get sandbox info"))
    }
}

export async function isRunning(full: boolean): Promise<boolean> {
    const checkContainerName = full ? 'flextesa' : 'ipfs';
    const command = `${configEnv()} docker-compose -f docker-compose.yml ps -q ${checkContainerName}`;

    //console.log("running:", command);
    const output = child.execSync(command, {encoding: 'utf-8'}).trim();

    // Output will either have the container ID (64 chars) or be empty.
    // Return true if not empty.
    return output.length !== 0;
}

export async function startIfNotRunning(full: boolean) {
    const sandboxRunning = await isRunning(full);

    if (!sandboxRunning) await start(full);
}