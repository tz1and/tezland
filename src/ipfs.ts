import * as ipfs from 'ipfs-http-client'
import * as fs from 'fs';

export async function upload_place_metadata(minter_address: string, center: number[], border: number[][]): Promise<string> {
    if (!process.env.IPFS_URL) throw Error("IPFS_URL not set");

    const ipfs_client = ipfs.create({ url: process.env.IPFS_URL });

    const result = await ipfs_client.add(createPlaceTokenMetadata({
        identifier: "some-uuid",
        description: "A nice place",
        minter: minter_address,
        center_coordinates: center,
        border_coordinates: border
    }));

    return `ipfs://${result.path}`;
}

export async function upload_item_metadata(minter_address: string, model_url: string): Promise<string> {
    if (!process.env.IPFS_URL) throw Error("IPFS_URL not set");

    const ipfs_client = ipfs.create({ url: process.env.IPFS_URL });

    const result = await ipfs_client.add(createItemTokenMetadata({
        name: "My awesome item",
        description: "A nice item",
        minter: minter_address,
        modelUrl: model_url
    }));

    return `ipfs://${result.path}`;
}

export async function upload_item_model(file: string): Promise<string> {
    if (!process.env.IPFS_URL) throw Error("IPFS_URL not set");

    const ipfs_client = ipfs.create({ url: process.env.IPFS_URL });

    const data: Buffer = fs.readFileSync(file);

    const result = await ipfs_client.add(data);

    return `ipfs://${result.path}`;
}

export interface FA2Metadata {
    authors: string[];
    description: string;
    homepage: string;
    repository: string;
    name: string;
    version: string;
}

export async function upload_FA2_metadata(metadata: FA2Metadata): Promise<string> {
    if (!process.env.IPFS_URL) throw Error("IPFS_URL not set");

    const ipfs_client = ipfs.create({ url: process.env.IPFS_URL });

    const result = await ipfs_client.add(Buffer.from(JSON.stringify(metadata)));

    return `ipfs://${result.path}`;
}

interface PlaceMetadata {
    center_coordinates: number[];
    border_coordinates: number[][];
    description: string;
    minter: string;
    identifier: string;
}

function createPlaceTokenMetadata(metadata: PlaceMetadata) {
    return Buffer.from(
        JSON.stringify({
            identifier: metadata.identifier,
            description: metadata.description,
            minter: metadata.minter,
            isTransferable: true,
            isBooleanAmount: true,
            shouldPreferSymbol: true,
            symbol: 'Place',
            //artifactUri: cid,
            decimals: 0,
            center_coordinates: metadata.center_coordinates,
            border_coordinates: metadata.border_coordinates
        })
    )
}

interface ItemMetadata {
    description: string;
    minter: string;
    name: string;
    modelUrl: string;
}

function createItemTokenMetadata(metadata: ItemMetadata) {
    return Buffer.from(
        JSON.stringify({
            name: metadata.name,
            description: metadata.description,
            minter: metadata.minter,
            isTransferable: true,
            isBooleanAmount: false,
            shouldPreferSymbol: false,
            symbol: 'Item',
            artifactUri: metadata.modelUrl,
            decimals: 0
        })
    )
}