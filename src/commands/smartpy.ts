import * as child from 'child_process';
import * as kleur from 'kleur';
import * as fs from 'fs';
import config from '../user.config';

// Expected location of SmartPy CLI.
const SMART_PY_INSTALL_DIR = "./bin/smartpy"
const SMART_PY_CLI = SMART_PY_INSTALL_DIR + "/SmartPy.sh"
const test_out_dir = "./tests/test_output"

const CHECK_MARK = "\u2713"
const CROSS_MARK = "\u2717"

export function test(contract_names: string[]) {
    if(contract_names.length > 0)
        contract_names.forEach(contract_name => test_single('./tests', contract_name));
    else {
        for (const test_dir of ['./tests/upgrades', './tests'])
            fs.readdirSync(test_dir).forEach(file => {
                if(fs.lstatSync(test_dir + '/' + file).isFile() && file.endsWith('_tests.py'))
                    test_single(test_dir, file.slice(0, -9));
            });
    }

    console.log(`Test results are in ${test_out_dir}`)
}

export function test_single(dir: string, contract_name: string) {
    if (config.smartpy.exclude_tests.has(contract_name)) {
        console.log(kleur.blue(`- Skipping tests for contract '${contract_name}' (excluded in user.config)`));
        return;
    }

    console.log(kleur.yellow(`Running tests for contract '${contract_name}' ...`));

    try {
        // Build artifact directory.
        const contract_in = `${dir}/${contract_name}_tests.py`

        child.execSync(`${SMART_PY_CLI} test ${contract_in} ${test_out_dir} --html`, {stdio: 'inherit'})

        console.log(kleur.green(`${CHECK_MARK} Tests for '${contract_name}' succeeded`))

    } catch(err) {
        console.log(kleur.red(`${CROSS_MARK} Tests for '${contract_name}' failed: ${err}`))
    }
}

export function compile_metadata(target_name: string, file_name: string, contract_name: string, target_args: string[]): void {
    console.log(kleur.yellow(`Compiling contract '${contract_name}' ...`));

    // Build artifact directory.
    const target_out_dir = "./build/targets"
    const tmp_out_dir = "./build/tmp_contract_build"

    // Make target dir if it doesn't exist
    if (!fs.existsSync(target_out_dir)) fs.mkdirSync(target_out_dir, { recursive: true });

    // write the compilation target
    fs.writeFileSync(`./${target_out_dir}/${target_name}_target.py`, `import smartpy as sp
${file_name}_contract = sp.io.import_script_from_url("file:contracts/${file_name}.py")
sp.add_compilation_target("${target_name}", ${file_name}_contract.${contract_name}(
    ${target_args.join(', ')}
    ))`)

    // cleanup
    if (fs.existsSync(tmp_out_dir)) fs.rmSync(tmp_out_dir, {recursive: true})

    console.log(`Compiling metadata for ${target_name}`)

    const contract_in = `${target_out_dir}/${target_name}_target.py`

    child.execSync(`${SMART_PY_CLI} compile ${contract_in} ${tmp_out_dir}`, {stdio: 'inherit'})

    console.log(`Extracting metadata ...`)

    const metadata_out = `${target_name}_metadata.json`
    const metadata_compiled = `${target_name}/step_000_cont_0_metadata.metadata_base.json`

    if (fs.existsSync(`${tmp_out_dir}/${metadata_compiled}`)) {
        fs.copyFileSync(`${tmp_out_dir}/${metadata_compiled}`, `./build/${metadata_out}`)
        console.log(kleur.green(`Metadata written to ${metadata_out}`))
    }

    console.log()
}

export function compile_newtarget(target_name: string, file_name: string, contract_name: string, target_args: string[]): void {
    console.log(kleur.yellow(`Compiling contract '${contract_name}' ...`));

    // Build artifact directory.
    const target_out_dir = "./build/targets"
    const tmp_out_dir = "./build/tmp_contract_build"

    // Make target dir if it doesn't exist
    if (!fs.existsSync(target_out_dir)) fs.mkdirSync(target_out_dir, { recursive: true });

    // write the compilation target
    fs.writeFileSync(`./${target_out_dir}/${target_name}_target.py`, `import smartpy as sp
${target_name}_contract = sp.io.import_script_from_url("file:contracts/${file_name}.py")
sp.add_compilation_target("${target_name}", ${target_name}_contract.${contract_name}(
    ${target_args.join(', ')}
    ))`)

    // cleanup
    if (fs.existsSync(tmp_out_dir)) fs.rmSync(tmp_out_dir, {recursive: true})

    console.log(`Compiling ${target_name}`)

    const contract_in = `${target_out_dir}/${target_name}_target.py`

    child.execSync(`${SMART_PY_CLI} compile ${contract_in} ${tmp_out_dir}`, {stdio: 'inherit'})

    console.log(`Extracting Michelson contract and storage ...`)

    const contract_out = `${target_name}.json`
    const storage_out = `${target_name}_storage.json`
    const contract_compiled = `${target_name}/step_000_cont_0_contract.json`
    const storage_compiled = `${target_name}/step_000_cont_0_storage.json`

    fs.copyFileSync(`${tmp_out_dir}/${contract_compiled}`, `./build/${contract_out}`)
    console.log(kleur.green(`Michelson contract written to ${contract_out}`))

    fs.copyFileSync(`${tmp_out_dir}/${storage_compiled}`, `./build/${storage_out}`)
    console.log(kleur.green(`Michelson storage written to ${storage_out}`))

    console.log()
}

export function upgrade_newtarget(target_name: string, file_name: string, contract_name: string, target_args: string[], entrypoints: string[]): Map<string, string> {
    console.log(kleur.yellow(`Compiling contract '${contract_name}' ...`));

    // Build artifact directory.
    const target_out_dir = "./build/upgrade"
    const tmp_out_dir = "./build/tmp_contract_build"

    // Make target dir if it doesn't exist
    if (!fs.existsSync(target_out_dir)) fs.mkdirSync(target_out_dir, { recursive: true });

    // Grab raw michelson from compiled storage.

    // write the compilation target
    fs.writeFileSync(`./${target_out_dir}/${target_name}_upgrade.py`, `import smartpy as sp
${target_name}_contract = sp.io.import_script_from_url("file:contracts/${file_name}.py")

@sp.add_target(name = "${target_name}", kind = "upgrade")
def upgrade():
    admin = sp.test_account("Administrator")

    scenario = sp.test_scenario()
    instance = ${target_name}_contract.${contract_name}(${target_args.join(', ')})
    scenario += instance

    # Build a map from upgradeable_entrypoints, names to id
    # and output the expression.
    scenario.show({
        **{entrypoint: sp.contract_entrypoint_id(instance, entrypoint) for entrypoint in instance.upgradeable_entrypoints}},
        html=True, compile=True)`)

    // cleanup
    if (fs.existsSync(tmp_out_dir)) fs.rmSync(tmp_out_dir, {recursive: true})

    console.log(`Compiling ${target_name}`)

    const contract_in = `${target_out_dir}/${target_name}_upgrade.py`

    child.execSync(`${SMART_PY_CLI} kind upgrade ${contract_in} ${tmp_out_dir} --html`, {stdio: 'inherit'})

    console.log(`Extracting entry point map from output ...`)

    // We can just parse the python expression for the ep map as json.
    const ep_map_compiled = `${tmp_out_dir}/${target_name}/step_001_expression.py`;
    let ep_map = JSON.parse(fs.readFileSync(ep_map_compiled, "utf-8").replace(/'/g, '"'));

    console.log(`Extracting code to upgrade from storage ...`)

    // Parse the compiled contracts storage to extract eps from.
    const storage_compiled = `${tmp_out_dir}/${target_name}/step_000_cont_0_storage.json`
    let storage = JSON.parse(fs.readFileSync(storage_compiled, "utf-8"));

    const code_map = new Map<string, string>();

    // For all the entrypoints we are looking for
    for (const ep_name of entrypoints) {
        const ep_search_id = ep_map[ep_name];

        // For all lazy entry points in compiled storage
        for (const lazy_ep of storage.args[1]) {
            // extract id and lambda
            const ep_id = parseInt(lazy_ep.args[0].int);
            const ep_lambda = lazy_ep.args[1];

            if (ep_id === ep_search_id) {
                // write lambda
                const ep_out = `${target_name}_ep__${ep_name}.json`
                fs.writeFileSync(`./build/${ep_out}`, JSON.stringify(ep_lambda, null, 4));

                console.log(kleur.green(`Code written written to ${ep_out}`))
                code_map.set(ep_name, `./build/${ep_out}`);
                break;
            }
        }
    }

    // TODO: function for extracting metadata.
    console.log(`Extracting metadata ...`)

    const metadata_out = `${target_name}_metadata.json`
    const metadata_compiled = `${target_name}/step_000_cont_0_metadata.metadata_base.json`

    if (fs.existsSync(`${tmp_out_dir}/${metadata_compiled}`)) {
        fs.copyFileSync(`${tmp_out_dir}/${metadata_compiled}`, `./build/${metadata_out}`)
        console.log(kleur.green(`Metadata written to ${metadata_out}`))
    }

    console.log();
    return code_map;
}

export function install(force?: boolean): void {
    if (force === undefined) force = false;

    if (fs.existsSync(SMART_PY_INSTALL_DIR) && !force) {
        console.log("SmartPy already installed (use --force to upgrade).")
        return;
    }

    child.execSync(`sh <(curl -s https://smartpy.io/cli/install.sh) --prefix ${SMART_PY_INSTALL_DIR} --yes`, {stdio: 'inherit'})
}