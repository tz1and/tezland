import { program } from 'commander';
import * as sandbox from './commands/sandbox';
import * as smartpy from './commands/smartpy';
import Deploy from './commands/deploy';
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
    .description('Start the network sandbox. No effect on non-sandbox networks.')
    .action(sandbox.start)

sandbox_command
    .command('kill')
    .alias('k')
    .description('Kill running network sandbox. No effect on non-sandbox networks.')
    .action(sandbox.kill)

sandbox_command
    .command('info')
    .alias('i')
    .description('Displays sandbox info.')
    .action(sandbox.info)

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

try {
    program.parse();
} catch (err) {
    console.log("Parsing error: " + err);
}