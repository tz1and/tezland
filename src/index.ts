import { program } from 'commander';
import * as sandbox from './commands/sandbox';
import * as smartpy from './commands/smartpy';
import Deploy from './commands/deploy';
import Upgrade from './commands/upgrade';
const packageJson = require('../package.json');

// configuration

program.version(packageJson.version, '-v, --version', 'Show version');

program
    .name("smartpy-node-dev")
    .usage("[global options] command");

program.showHelpAfterError('(add --help for additional information)');
program.exitOverride((err) => process.exit(0));

//
// Flextesa sandbox
//
var sandbox_command = program
    .command('sandbox')
    .description('Manage the bcdhub/flextesa sandbox')

sandbox_command
    .command('start')
    .alias('s')
    .description('Start the network sandbox.')
    .option('-f, --full', 'Run a full sandbox with flextesa, tzkt and bcd.')
    .action((options) => sandbox.start(options.full))

sandbox_command
    .command('pull')
    .alias('p')
    .description('Pull sandbox images.')
    .argument('[service_names...]', 'names of services (optional)')
    .action(async (service_names: string[]) => {
        await sandbox.pull(service_names);
    });

sandbox_command
    .command('kill')
    .alias('k')
    .description('Kill running network sandbox.')
    .action(sandbox.kill)

sandbox_command
    .command('info')
    .alias('i')
    .description('Displays sandbox info.')
    .action(sandbox.info)

sandbox_command
    .command('logs')
    .alias('l')
    .description('Displays sandbox logs.')
    .action(sandbox.logs)

//
// SmartPy stuff
//

program
    .command('test')
    .alias('t')
    .description('Runs tests.')
    .argument('[contract_names...]', 'names of contracts (optional)')
    .action((contract_names: string[]) => {
        smartpy.test(contract_names);
    });

//
// Deploying
//

program
    .command('deploy')
    .alias('d')
    .description('Run the deploy script.')
    .option('-n, --network [network]', 'the network to deploy to (optional)')
    .action(async (options) => {
        const deploy = new Deploy(options);
        await deploy.deploy();
    });

program
    .command('upgrade')
    .alias('u')
    .description('Run the upgrade script.')
    .option('-n, --network [network]', 'the network to upgrade on (optional)')
    .action(async (options) => {
        const upgrade = new Upgrade(options);
        await upgrade.deploy();
    });

program
    .command('install-smartpy')
    .description('Installs smartpy to bin.')
    .option('-f, --force', 'Force install if already installed.')
    .action((options) => {
        smartpy.install(options.force);
    });

try {
    program.parse();
} catch (err) {
    console.log("Parsing error: " + err);
}