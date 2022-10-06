// This file is more or less straight from the backend
// Should probably rather include it or something...

import { Blob, NFTStorage, Service, Token } from 'nft.storage'
import * as ipfs from 'ipfs-http-client';
import { TimeoutError } from 'ipfs-utils/src/http'
import { performance } from 'perf_hooks';
import config from './user.config';
//import { Blockstore } from 'nft.storage/dist/src/platform';


const ipfs_client = ipfs.create({ url: config.ipfs.localNodeUrl, timeout: 10000 });


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

// extend NFTStorage to allow us to supply our own validation while keeping
// the simplicity of the store() function.
class NFTStorageTZip extends NFTStorage {
    static override async encodeNFT(input: any) {
        validateTZip12(input)
        return Token.Token.encode(input)
    }

    static override async store(service: Service, metadata: any, options?: any) {
        const { token, car } = await NFTStorageTZip.encodeNFT(metadata)
        await NFTStorageTZip.storeCar(service, car, options)
        return token
    }

    override store(token: any, options?: any) {
        return NFTStorageTZip.store(this, token, options)
    }
}

// Upload to NFTStorage without validation. For contract metadata.
class NFTStorageNoValidation extends NFTStorage {
    static override async encodeNFT(input: any) {
        return Token.Token.encode(input)
    }

    static override async store(service: Service, metadata: any, options?: any) {
        const { token, car } = await NFTStorageNoValidation.encodeNFT(metadata)
        await NFTStorageNoValidation.storeCar(service, car, options)
        return token
    }

    override store(token: any, options?: any) {
        return NFTStorageNoValidation.store(this, token, options)
    }
}

// if it's a directory path, get the root file
// and use that to mint.
async function get_root_file_from_dir(cid: string): Promise<string> {
    console.log("get_root_file_from_dir: ", cid)
    try {
        const max_num_retries = 5;
        let num_retries = 0;
        while(num_retries < max_num_retries) {
            try {
                for await (const entry of ipfs_client.ls(cid)) {
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
// Upload handlers
//

type ResultType = {
    metdata_uri: string,
    cid: string,
}

type handlerFunction = (data: any, is_contract: boolean) => Promise<ResultType>;

const uploadToNFTStorage: handlerFunction = async (data: any, is_contract: boolean): Promise<ResultType> => {
    const start_time = performance.now();
    const client = is_contract ? new NFTStorageNoValidation({ token: config.ipfs.nftStorageApiKey }) : new NFTStorageTZip({ token: config.ipfs.nftStorageApiKey })

    const metadata = await client.store(data);
    const file_cid = await get_root_file_from_dir(metadata.ipnft);
    console.log("uploadToNFTStorage took " + (performance.now() - start_time).toFixed(2) + "ms");

    return { metdata_uri: `ipfs://${file_cid}`, cid: file_cid };
}

const uploadToLocal: handlerFunction = async (data: any, is_contract: boolean): Promise<ResultType> => {
    const start_time = performance.now()

    // first we upload every blob in the object
    const traverse = async (jsonObj: any) => {
        if( jsonObj !== null && typeof jsonObj == "object" ) {
            // key is either an array index or object key
            for (const [key, value] of Object.entries(jsonObj)) {
                // if it's a File, upload it.
                if(value instanceof Blob) {
                    const file: Blob = value as Blob;
        
                    // upload to ips
                    const result = await ipfs_client.add(file);
                    const path = `ipfs://${result.cid.toV0().toString()}`;
        
                    // and set the object to be the path
                    jsonObj[key] = path;
                }
                else await traverse(value);
            };
        }
        else {
            // jsonObj is a number or string
        }
    }
    await traverse(data);

    // now upload the metadata:
    const metadata = JSON.stringify(data);

    const result = await ipfs_client.add(metadata);
    console.log("uploadToLocal took " + (performance.now() - start_time).toFixed(2) + "ms");

    const CIDstr = result.cid.toV0().toString();

    return { metdata_uri: `ipfs://${CIDstr}`, cid: CIDstr };
}

export const uploadToIpfs = (metadata: any, is_contract: boolean, localIpfs: boolean): Promise<ResultType> => {
    const handler: handlerFunction = localIpfs ? uploadToLocal : uploadToNFTStorage;
    return handler(metadata, is_contract);
}