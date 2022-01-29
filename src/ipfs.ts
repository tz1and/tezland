import * as ipfs from 'ipfs-http-client'
import * as fs from 'fs';
import config from './user.config';
import assert = require('assert');

const ipfs_client = ipfs.create({ url: config.ipfsUrl });

// TODO: use nft.storage!
export async function upload_place_metadata(metadata: PlaceMetadata): Promise<string> {
    const result = await ipfs_client.add(createPlaceTokenMetadata(metadata));

    return `ipfs://${result.path}`;
}

// TODO: use nft.storage!
export async function upload_item_metadata(minter_address: string, model_url: string, mesh_size: number): Promise<string> {
    const result = await ipfs_client.add(createItemTokenMetadata({
        name: "My awesome item",
        description: "A nice item",
        minter: minter_address,
        modelUrl: model_url,
        formats: [
            {
                mimeType: "model/gltf-binary", // model/gltf+json, model/gltf-binary
                fileSize: mesh_size
            }
        ],
    }));

    return `ipfs://${result.path}`;
}

export async function upload_item_model(file: string): Promise<{mesh_url: string, mesh_size: number}> {
    const data: Buffer = fs.readFileSync(file);

    const result = await ipfs_client.add(data);

    return { mesh_url: `ipfs://${result.path}`, mesh_size: data.length };
}

export interface ContractMetadata {
    description: string;
    interfaces: string[],
    name: string;
    version: string;
}

// TODO: add to some config or so.
const metaRepository = 'https://github.com/tz1aND';
const metaHomepage = 'www.tz1and.com';
const metaAcknowledgement = "\n\nBased on Seb Mondet's FA2 implementation: https://gitlab.com/smondet/fa2-smartpy.git"
const metaAuthors = ['852Kerfunke <https://github.com/852Kerfunkle>'];
const metaLicense = { name: "MIT" };

function createContractMetadata(metadata: ContractMetadata, is_fa2: boolean) {

    const description = is_fa2 ? metadata.description + metaAcknowledgement : metadata.description;
    const authors = is_fa2 ? metaAuthors.concat('Seb Mondet <https://seb.mondet.org>') : metaAuthors;

    return Buffer.from(
        JSON.stringify({
            name: metadata.name,
            description: description,
            authors: authors,
            homepage: metaHomepage,
            repository: metaRepository,
            license: metaLicense,
            interfaces: metadata.interfaces,
            version: metadata.version
        })
    )
}

// TODO: use nft.storage!
export async function upload_contract_metadata(metadata: ContractMetadata, is_fa2: boolean = false): Promise<string> {
    const result = await ipfs_client.add(createContractMetadata(metadata, is_fa2));

    console.log(`${metadata.name} contract metadata: ipfs://${result.path}`);

    return `ipfs://${result.path}`;
}

interface PlaceMetadata {
    centerCoordinates?: number[];
    borderCoordinates?: number[][];
    buildHeight?: number;
    description: string;
    minter: string;
    name: string;
    placeType: "exterior" | "interior";
}

function createPlaceTokenMetadata(metadata: PlaceMetadata) {
    const full_metadata: any = {
        name: metadata.name,
        description: metadata.description,
        minter: metadata.minter,
        isTransferable: true,
        isBooleanAmount: true,
        shouldPreferSymbol: true,
        symbol: 'Place',
        //artifactUri: cid,
        decimals: 0,
        placeType: metadata.placeType
    }

    if (metadata.placeType === "exterior") {
        assert(metadata.borderCoordinates);
        assert(metadata.centerCoordinates);
        assert(metadata.buildHeight);
        full_metadata.centerCoordinates = metadata.centerCoordinates;
        full_metadata.borderCoordinates = metadata.borderCoordinates;
        full_metadata.buildHeight = metadata.buildHeight;
    }
    
    return JSON.stringify(full_metadata);
}

interface ItemMetadata {
    description: string;
    minter: string;
    name: string;
    modelUrl: string;
    formats: object[];
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
            decimals: 0,
            formats: metadata.formats
        })
    )
}