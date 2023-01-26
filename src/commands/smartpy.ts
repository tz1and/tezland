import * as child from 'child_process';
import kleur from 'kleur';
import * as fs from 'fs';
import config from '../user.config';

// Expected location of SmartPy CLI.
const SMART_PY_INSTALL_DIR = "./bin/smartpy"
const SMART_PY_CLI = SMART_PY_INSTALL_DIR + "/SmartPy.sh"
type SmartPyTask = "compile" | "test"
const smartPyCli = (task: SmartPyTask, command: string) => `source .venv/bin/activate && PYTHONPATH="./" SMARTPY_NODE_DEV=${task} ${SMART_PY_CLI} ${command}`
const test_out_dir = "./tests/test_output"

type TestResult = "success" | "failed" | "skipped"

const CHECK_MARK = "\u2713"
const CROSS_MARK = "\u2717"

export function test(contract_names: string[], dir?: string) {
    if(contract_names.length > 0)
        contract_names.forEach(contract_name => test_single('./tests', contract_name));
    else {
        const test_dirs = dir ? new Set([dir]) : config.smartpy.test_dirs;
        const test_results = new Map<TestResult, number>()
        for (const test_dir of test_dirs) {
            console.log(`\nIn dir: ${test_dir}`)
            if (fs.existsSync(test_dir) && fs.lstatSync(test_dir).isDirectory())
                fs.readdirSync(test_dir).forEach(file => {
                    if(fs.lstatSync(test_dir + '/' + file).isFile() && file.endsWith('_tests.py')) {
                        const res = test_single(test_dir, file.slice(0, -9));
                        test_results.set(res, (test_results.get(res) || 0) + 1);
                    }
                });
            else console.warn(kleur.red(`'${test_dir}' does not exist or is not a directory.`));
        }
        // Print test results
        console.log();
        for (const [k,v] of test_results) console.log(`${k}: ${v}`)
    }

    console.log(`\nTest results are in ${test_out_dir}`)
}

export function test_single(dir: string, contract_name: string): TestResult {
    if (config.smartpy.exclude_tests.has(contract_name)) {
        console.log(kleur.blue(`- Skipping tests for contract '${contract_name}' (excluded in user.config)`));
        return "skipped";
    }

    console.log(kleur.yellow(`Running tests for contract '${contract_name}' ...`));

    try {
        // Build artifact directory.
        const contract_in = `${dir}/${contract_name}_tests.py`

        child.execSync(smartPyCli("test", `test ${contract_in} ${test_out_dir} --html`), {stdio: 'inherit'})

        console.log(kleur.green(`${CHECK_MARK} Tests for '${contract_name}' succeeded`))

        return "success"
    } catch(err) {
        console.log(kleur.red(`${CROSS_MARK} Tests for '${contract_name}' failed: ${err}`))
        return "failed"
    }
}

function optimise(target_name: string, file_in: string, file_out: string): string {
    if (false) {
        console.log(`Optimising ${target_name}`)

        child.execSync(`./bin/morley.sh optimize --contract ${file_in} -o ${file_out}`, {stdio: 'inherit'})
        return file_out;
    }

    return file_in;
}

// Returns path to metadata.
export function compile_metadata_substep(target_out_dir: string, target_name: string, file_name: string, contract_name: string, target_args: string[]): string {
    const tmp_out_dir = "./build/tmp_contract_build"
    const metadata_target_path = `${target_out_dir}/${target_name}_metadata_target.py`

    // Write the compilation target
    fs.writeFileSync(metadata_target_path, `import smartpy as sp
${target_name}_contract = sp.io.import_script_from_url("file:contracts/${file_name}.py")
sp.add_compilation_target("${target_name}", ${target_name}_contract.${contract_name}(
    ${target_args.join(', ')}
    ))`)

    // Delete tmp out dir if exists
    if (fs.existsSync(tmp_out_dir)) fs.rmSync(tmp_out_dir, {recursive: true})

    child.execSync(smartPyCli("compile", `compile ${metadata_target_path} ${tmp_out_dir}`), {stdio: 'inherit'})

    // TODO: function for extracting metadata.
    const metadata_compiled_path = `${tmp_out_dir}/${target_name}/step_000_cont_0_metadata.metadata_base.json`

    const metadata_out = `${target_name}_metadata.json`
    const metadata_out_path = `${target_out_dir}/${metadata_out}`

    if (fs.existsSync(metadata_compiled_path)) {
        fs.copyFileSync(metadata_compiled_path, metadata_out_path)
        console.log(kleur.green(`Compiled metadata: ${metadata_out}`))
    }
    else throw new Error(`Metadata not found at ${metadata_compiled_path}`)

    return metadata_out_path;
}

// Returns path to code and storage.
export function compile_code_substep(target_out_dir: string, target_name: string, file_name: string, contract_name: string, target_args: string[]): [string, string] {
    const tmp_out_dir = "./build/tmp_contract_build"
    const code_target_path = `${target_out_dir}/${target_name}_code_target.py`

    // Write the compilation target
    fs.writeFileSync(code_target_path, `import smartpy as sp
${target_name}_contract = sp.io.import_script_from_url("file:contracts/${file_name}.py")
sp.add_compilation_target("${target_name}", ${target_name}_contract.${contract_name}(
    ${target_args.join(', ')}
    ))`)

    // Delete tmp out dir if exists
    if (fs.existsSync(tmp_out_dir)) fs.rmSync(tmp_out_dir, {recursive: true})

    child.execSync(smartPyCli("compile", `compile ${code_target_path} ${tmp_out_dir}`), {stdio: 'inherit'})

    const contract_compiled = `${target_name}/step_000_cont_0_contract.json`
    //const contract_optimized = `${target_name}/step_000_cont_0_contract_opt.tz`
    //const final_contract = optimise(target_name, contract_compiled, contract_optimized);

    const storage_compiled = `${target_name}/step_000_cont_0_storage.json`

    const contract_out = `${target_name}.json`
    const contract_out_path = `${target_out_dir}/${contract_out}`
    const storage_out = `${target_name}_storage.json`
    const storage_out_path = `${target_out_dir}/${storage_out}`

    fs.copyFileSync(`${tmp_out_dir}/${contract_compiled}`, contract_out_path)
    console.log(kleur.green(`Compiled contract: ${contract_out}`))

    fs.copyFileSync(`${tmp_out_dir}/${storage_compiled}`, storage_out_path)
    console.log(kleur.green(`Compiled storage: ${storage_out}`))

    return [contract_out_path, storage_out_path];
}

// Returns ep code map and metadata path.
export function compile_upgrade(target_out_dir: string, target_name: string, file_name: string, contract_name: string, target_args: string[], entrypoints: string[]): [Map<string, [number, string]>, string] {
    const tmp_out_dir = "./build/tmp_contract_build"
    const upgrade_target_path = `${target_out_dir}/${target_name}_upgrade_target.py`

    // Make target dir if it doesn't exist
    if (!fs.existsSync(target_out_dir)) fs.mkdirSync(target_out_dir, { recursive: true });

    // Grab raw michelson from compiled storage.

    // write the compilation target
    fs.writeFileSync(upgrade_target_path, `import smartpy as sp
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

    // Delete tmp out dir if exists
    if (fs.existsSync(tmp_out_dir)) fs.rmSync(tmp_out_dir, {recursive: true})

    child.execSync(smartPyCli("compile", `kind upgrade ${upgrade_target_path} ${tmp_out_dir} --html`), {stdio: 'inherit'})

    // We can just parse the python expression for the ep map as json.
    const ep_map_compiled = `${tmp_out_dir}/${target_name}/step_001_expression.py`;
    let ep_map = JSON.parse(fs.readFileSync(ep_map_compiled, "utf-8").replace(/'/g, '"'));

    // Parse the compiled contracts storage to extract eps from.
    const storage_compiled = `${tmp_out_dir}/${target_name}/step_000_cont_0_storage.json`
    let storage = JSON.parse(fs.readFileSync(storage_compiled, "utf-8"));

    const code_map = new Map<string, [number, string]>();

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
                const ep_out_path = `${target_out_dir}/${ep_out}`
                fs.writeFileSync(ep_out_path, JSON.stringify(ep_lambda, null, 4));

                console.log(kleur.green(`Compiled entrypoint: ${ep_out}`))
                code_map.set(ep_name, [ep_id, ep_out_path]);
                break;
            }
        }
    }

    // TODO: function for extracting metadata.
    const metadata_compiled_path = `${tmp_out_dir}/${target_name}/step_000_cont_0_metadata.metadata_base.json`

    const metadata_out = `${target_name}_metadata.json`
    const metadata_out_path = `${target_out_dir}/${metadata_out}`

    if (fs.existsSync(`${metadata_compiled_path}`)) {
        fs.copyFileSync(`${metadata_compiled_path}`, metadata_out_path)
        console.log(kleur.green(`Compiled metadata: ${metadata_out}`))
    }
    else throw new Error(`Metadata not found at ${metadata_compiled_path}`)

    return [code_map, metadata_out_path];
}

export function install(force?: boolean): void {
    if (force === undefined) force = false;

    if (fs.existsSync(SMART_PY_INSTALL_DIR) && !force) {
        console.log("SmartPy already installed (use --force to upgrade).")
        return;
    }

    child.execSync(`sh <(curl -s https://smartpy.io/cli/install.sh) --prefix ${SMART_PY_INSTALL_DIR} --yes`, {stdio: 'inherit'})
}

export function version(): void {
    child.execSync(smartPyCli("test", "--version"), {stdio: 'inherit'})
}