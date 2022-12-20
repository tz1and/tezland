// This file is more or less straight from the backend
// Should probably rather include it or something...

import { CarReader, NFTStorage, Token } from 'nft.storage'
import { TreewalkCarJoiner } from 'carbites/treewalk'
import * as ipfs from 'ipfs-http-client';
import pkg from 'ipfs-utils/src/http';
const { TimeoutError } = pkg;
import { performance } from 'perf_hooks';
import config from './user.config';
import assert from 'assert';
//import { Blockstore } from 'nft.storage/dist/src/platform';


export const ipfs_client = ipfs.create({ url: config.ipfs.localNodeUrl, timeout: 30000 });


const validateTZip12 = ({ name, description, decimals }: { name: string, description: string, decimals: number}) => {
    // Just validate that expected fields are present
    if (typeof name !== 'string') {
      throw new TypeError(
        'string property `name` identifying the asset is required'
      )
    }
    if (typeof description !== 'string') {
      throw new TypeError(
        'string property `description` describing asset is required'
      )
    }
    if (typeof decimals !== 'undefined' && typeof decimals !== 'number') {
      throw new TypeError('property `decimals` must be an integer value')
    }
}

const noValidation = ({}) => {}

class IPFSUpload {
    private static encodeNFT(input: any) {
        return Token.Token.encode(input)
    }

    private static async storeNFTStorage(client: NFTStorage, car: CarReader, options?: any) {
        const start_time = performance.now();
        await NFTStorage.storeCar(client, car, options)
        console.log(`upload to NFTStorage took ${(performance.now() - start_time).toFixed(2)} ms`);
    }

    private static async storeLocalNode(local_client: ipfs.IPFSHTTPClient, token: Token.Token<any>, car: CarReader) {
        const start_time = performance.now();
        // Import car into local node.
        // TODO: figure out if I need to pin roots.
        const joiner = new TreewalkCarJoiner([car]);
        for await (const local_upload of local_client.dag.import(joiner.car(), { pinRoots: false })) {
            // NOTE: this won't run unless pinning is enabled.
            console.log("uploaded and pinned");
            assert(local_upload.root.cid.toString() == token.ipnft);
        }
        console.log(`upload to local ipfs took ${(performance.now() - start_time).toFixed(2)} ms`);
    }

    static async store(metadata: any, validator: (metadata: any) => void, local_client: ipfs.IPFSHTTPClient, client?: NFTStorage, options?: any) {
        // Validate token.
        validator(metadata);

        // Encode nft
        const { token, car } = await IPFSUpload.encodeNFT(metadata);

        // Upload to local node (for immediate availability).
        await IPFSUpload.storeLocalNode(local_client, token, car);

        // upload same car to NFT storage.
        if (client) await IPFSUpload.storeNFTStorage(client, car, options);

        // return token hash.
        return token;
    }
}

//
// Get root file from dag using ls.
//
async function get_root_file_from_dir(local_client: ipfs.IPFSHTTPClient, cid: string): Promise<string> {
    console.log("get_root_file_from_dir: ", cid)
    try {
        const max_num_retries = 10;
        let num_retries = 0;
        while(num_retries < max_num_retries) {
            try {
                for await (const entry of local_client.ls(cid)) {
                    //console.log(entry)
                    if (entry.type === 'file') {
                        return entry.cid.toString();
                    }
                }
                throw new Error("Failed to get root file from dir");
            } catch (e) {
                if (e instanceof TimeoutError) {
                    num_retries++
                    console.log("retrying ipfs.ls");
                } else {
                    throw e; // let others bubble up
                }
            }
        }
        throw new Error("Failed to get root file from dir. Retries = " + max_num_retries);
    } catch(e: any) {
        throw new Error("Failed to get root file from dir: " + e.message);
    }
}

//
// Resolve path to CID using dag.resolve.
//
async function resolve_path_to_cid(local_client: ipfs.IPFSHTTPClient, path: string): Promise<string> {
    console.log("resolve_path_to_cid: ", path)
    try {
        const max_num_retries = 10;
        let num_retries = 0;
        while(num_retries < max_num_retries) {
            try {
                const resolve_result = await local_client.dag.resolve(path);

                // If there's a remainder path, something probably went wrong.
                if (resolve_result.remainderPath && resolve_result.remainderPath.length > 0)
                    throw new Error("Remainder path: " + resolve_result.remainderPath);

                return resolve_result.cid.toString();
            } catch (e) {
                if (e instanceof TimeoutError) {
                    num_retries++
                    console.log("retrying ipfs.dag.resolve");
                } else {
                    throw e; // let others bubble up
                }
            }
        }
        throw new Error("Retries = " + max_num_retries);
    } catch(e: any) {
        throw new Error("Failed to resolve path: " + e.message);
    }
}

//
// Upload handlers
//

type ResultType = {
    metdata_uri: string,
    cid: string,
}

// TODO: this is kind of a nasty workaround, but it will probably work for now :)
var request_counter: number = 0;
const nft_storage_clients: NFTStorage[] = [];
for (const key of config.ipfs.nftStorageApiKeys) {
    nft_storage_clients.push(new NFTStorage({ token: key }));
}

export const uploadToIpfs = async (data: any, is_contract: boolean, localIpfs: boolean, verbose: boolean = false): Promise<ResultType> => {
    const client = localIpfs ? undefined : (() => {
        // Get client id and increase counter.
        const client_id = request_counter % nft_storage_clients.length;
        ++request_counter;
        return nft_storage_clients[client_id];
    })()

    const validator = is_contract ? noValidation : validateTZip12;

    // Upload to local and maybe NFT storage.
    const metadata = await IPFSUpload.store(data, validator, ipfs_client, client);

    // Get cid of metadata file.
    const file_cid = await resolve_path_to_cid(ipfs_client, `${metadata.ipnft}/metadata.json`);

    return { metdata_uri: `ipfs://${file_cid}`, cid: file_cid };
}
