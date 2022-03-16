import * as child from 'child_process';
import * as kleur from 'kleur';
import * as fs from 'fs';

// Expected location of SmartPy CLI.
const SMART_PY_CLI = "./bin/smartpy/SmartPy.sh"
const test_out_dir = "./tests/test_output"


export function test(contract_names: string[]) {
    if(contract_names.length > 0)
        contract_names.forEach(contract_name => test_single(contract_name));
    else {
        const test_dir = './tests/';
        fs.readdirSync(test_dir).forEach(file => {
            if(fs.lstatSync(test_dir + file).isFile() && file.endsWith('_tests.py'))
                test_single(file.slice(0, -9));
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
        console.log(kleur.red(`Tests for '${contract_name}' failed: ${err}`))
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
${file_name}_contract = sp.io.import_script_from_url("file:contracts/${file_name}.py")
sp.add_compilation_target("${target_name}", ${file_name}_contract.${contract_name}(
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
