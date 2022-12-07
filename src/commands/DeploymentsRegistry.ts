import assert from 'assert';
import fs from 'fs';


type DeploymentsFlag = boolean | number | string

export default class DeploymentsRegistry {
    private version: number;
    private flags: Map<string, DeploymentsFlag>;
    private contracts: Map<string, string>;

    private path: string;

    constructor(path: string) {
        this.version = 2;
        this.flags = new Map();
        this.contracts = new Map();

        this.path = path;
    }

    public getContract(contract_name: string): string | undefined {
        return this.contracts.get(contract_name);
    }

    public getFlag(flag_name: string): DeploymentsFlag | undefined {
        return this.flags.get(flag_name);
    }

    public addContract(contract_name: string, address: string, write_reg: boolean = true) {
        this.contracts.set(contract_name, address);

        // Do this here instead of at the end, otherwise things will be lost on error.
        if (write_reg) this.writeToDisk();
    }

    public addFlag(flag_name: string, value: DeploymentsFlag, write_reg: boolean = true) {
        this.flags.set(flag_name, value);

        // Do this here instead of at the end, otherwise things will be lost on error.
        if (write_reg) this.writeToDisk();
    }

    private writeToDisk() {
        fs.writeFileSync(this.path, JSON.stringify({
            version: this.version,
            flags: Array.from(this.flags.entries()),
            contracts: Array.from(this.contracts.entries())
        }), { encoding: 'utf-8' })
    }

    public readFromDisk() {
        // Parse deployments registry
        if (fs.existsSync(this.path)) {
            const parsed_registry = JSON.parse(fs.readFileSync(this.path, { encoding: 'utf-8' }));

            if (parsed_registry.version && parsed_registry.version === 2)
                this.parseVersion2(parsed_registry);
            else
                this.parseVersion1(parsed_registry);
        }
    }

    private parseVersion1(contracts: any) {
        console.log("Upgrading deployments registry to version 2.");

        // Add contracts, but don't write to disk.
        for (const [key, value] of Object.entries(contracts)) {
            this.addContract(key, (value as any).contract, false);
        }
    }

    private parseVersion2(parsed_registry: any) {
        assert(parsed_registry.version === 2);
        assert(parsed_registry.flags instanceof Array);
        assert(parsed_registry.contracts instanceof Array);

        this.flags = new Map(parsed_registry.flags);
        this.contracts = new Map(parsed_registry.contracts);
    }
}