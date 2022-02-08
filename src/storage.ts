// This file is more or less straight from the backend
// Should probably rather include it or something...

import { Blob, NFTStorage, Service, Token } from 'nft.storage'
import * as ipfs from 'ipfs-http-client';
import { performance } from 'perf_hooks';
import config from './user.config';


const ipfs_client = ipfs.create({ url: config.ipfs.localNodeUrl });


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

    static override async store(service: Service, metadata: any) {
        const { token, car } = await NFTStorageTZip.encodeNFT(metadata)
        await NFTStorageTZip.storeCar(service, car)
        return token
    }

    override store(token: any) {
        return NFTStorageTZip.store(this, token)
    }

    static override async storeBlob(service: Service, blob: Blob) {
        const { cid, car } = await NFTStorageTZip.encodeBlob(blob)
        await NFTStorage.storeCar(service, car)
        return cid.toString()
    }
}

// Upload to NFTStorage without validation. For contract metadata.
class NFTStorageNoValidation extends NFTStorage {
    static override async encodeNFT(input: any) {
        return Token.Token.encode(input)
    }

    static override async store(service: Service, metadata: any) {
        const { token, car } = await NFTStorageNoValidation.encodeNFT(metadata)
        await NFTStorageNoValidation.storeCar(service, car)
        return token
    }

    override store(token: any) {
        return NFTStorageNoValidation.store(this, token)
    }

    static override async storeBlob(service: Service, blob: Blob) {
        const { cid, car } = await NFTStorageNoValidation.encodeBlob(blob)
        await NFTStorage.storeCar(service, car)
        return cid.toString()
    }
}

// if it's a directory path, get the root file
// and use that to mint.
async function get_root_file_from_dir(cid: string): Promise<string> {
    console.log("get_root_file_from_dir: ", cid)
    try {
        for await(const entry of ipfs_client.ls(cid)) {
            //console.log(entry)
            if(entry.type === 'file') {
                return entry.cid.toString();
            }
        }
        throw new Error("Failed to get root file from dir");
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
    for (var property in data) {
        if(data[property] instanceof Blob) {
            const blob: Blob = data[property];

            // upload to ips
            const result = await ipfs_client.add(blob);
            const path = `ipfs://${result.cid.toV0().toString()}`;

            // and set the object to be the path
            data[property] = path;
        }
    }

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