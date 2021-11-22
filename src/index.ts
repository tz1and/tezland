import { program } from 'commander';
import * as dotenv from "dotenv";
import * as sandbox from './commands/sandbox';
import * as smartpy from './commands/smartpy';
import * as deploy from './commands/deploy';
const packageJson = require('../package.json');

dotenv.config(); /* This loads the variables in your .env file to process.env */

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
    .argument('<contract_name>', 'name of contract')
    .action((contract_name) => {
        smartpy.test(contract_name);
    });

program
    .command('compile')
    .alias('c')
    .description('Compile contract.')
    .argument('<contract_name>', 'name of contract')
    .action((contract_name) => {
        smartpy.compile(contract_name);
    });

//
// Deploying
//

program
    .command('deploy')
    .alias('d')
    .description('Run a deploy script.')
    //.argument('<contract_name>', 'name of contract')
    .action((contract_name) => {
        deploy.deploy(); //(contract_name);
    });

try {
    program.parse();
} catch (err) {
    console.log("Parsing error: " + err);
}