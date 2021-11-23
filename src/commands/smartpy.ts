import * as child from 'child_process';
import * as kleur from 'kleur';
import * as fs from 'fs';

// Expected location of SmartPy CLI.
const SMART_PY_CLI = "~/smartpy-cli/SmartPy.sh"
const test_out_dir = "./tests/test_output"


export function test(contract_names: string[]) {
    if(contract_names.length > 0)
        contract_names.forEach(value => test_single(value));
    else {
        const test_dir = './tests/';
        fs.readdirSync(test_dir).forEach(file => {
            if(fs.lstatSync(test_dir + file).isFile() && file.endsWith('_tests.py'))
            test_single(file.substring(0, file.length - 9));
        });
    }

    console.log(`Test results are in ${test_out_dir}`)
}

export function test_single(contract_name: string) {
    console.log(kleur.yellow(`Running tests for contract '${contract_name}' ...`));

    try {
        // Build artifact directory.
        const contract_in = `./tests/${contract_name}_tests.py`

        child.execSync(`${SMART_PY_CLI} test ${contract_in} ${test_out_dir} --html`, {stdio: 'inherit'})

        console.log(kleur.green(`Tests for '${contract_name}' succeeded`))

    } catch(err) {
        console.log(kleur.red(`Tests for '${contract_name}' faile: ${err}`))
    }
}

export function compile(contract_name: string) {
    console.log(kleur.yellow(`Compiling contract '${contract_name}' ...`));

    try {
        // Build artifact directory.
        const tmp_out_dir = "./build/tmp_contract_build"
        const contract_in = `./contracts/${contract_name}.py`

        // cleanup
        fs.rmdirSync(tmp_out_dir, {recursive: true})

        child.execSync(`${SMART_PY_CLI} compile ${contract_in} ${tmp_out_dir}`, {stdio: 'inherit'})

        console.log(`Extracting Michelson contract and storage ...`)

        const contract_out = `${contract_name}.json`
        const storage_out = `${contract_name}_storage.json`
        const contract_compiled = `${contract_name}/step_000_cont_0_contract.json`
        const storage_compiled = `${contract_name}/step_000_cont_0_storage.json`

        fs.copyFileSync(`${tmp_out_dir}/${contract_compiled}`, `./build/${contract_out}`)
        fs.copyFileSync(`${tmp_out_dir}/${storage_compiled}`, `./build/${storage_out}`)

        console.log(kleur.green(`Michelson contract written to ${contract_out}`))

    } catch(err) {
        console.log('failed: ' + err)
    }
}

export function compile_newtarget(target_name: string, contract_name: string, target_args: string[]): void {
    console.log(kleur.yellow(`Compiling contract '${contract_name}' ...`));

    // Build artifact directory.
    const target_out_dir = "./build/targets"
    const tmp_out_dir = "./build/tmp_contract_build"

    console.log(`Building ${target_name} target`)

    // Make target dir if it doesn't exist
    if (!fs.existsSync(target_out_dir)) fs.mkdirSync(target_out_dir);

    // write the compilation target
    fs.writeFileSync(`./${target_out_dir}/${target_name}_target.py`, `import smartpy as sp
${contract_name}_contract = sp.io.import_script_from_url("file:contracts/${contract_name}.py")
sp.add_compilation_target("${target_name}", ${contract_name}_contract.${contract_name}(
    ${target_args.join(', ')}
    ))`)

    // cleanup
    fs.rmdirSync(tmp_out_dir, {recursive: true})

    console.log(`Compiling ${target_name}`)

    const contract_in = `${target_out_dir}/${target_name}_target.py`

    child.execSync(`${SMART_PY_CLI} compile ${contract_in} ${tmp_out_dir}`, {stdio: 'inherit'})

    console.log(`Extracting Michelson contract and storage ...`)

    const contract_out = `${target_name}.json`
    const storage_out = `${target_name}_storage.json`
    const contract_compiled = `${target_name}/step_000_cont_0_contract.json`
    const storage_compiled = `${target_name}/step_000_cont_0_storage.json`

    fs.copyFileSync(`${tmp_out_dir}/${contract_compiled}`, `./build/${contract_out}`)
    fs.copyFileSync(`${tmp_out_dir}/${storage_compiled}`, `./build/${storage_out}`)

    console.log(kleur.green(`Michelson contract written to ${contract_out}`))
    console.log(kleur.green(`Michelson storage written to ${storage_out}`))
}