import * as fs from 'fs';
import assert = require('assert');
import { uploadToIpfs } from './storage';
import { File } from 'nft.storage';


export async function upload_place_metadata(metadata: PlaceMetadata, localIpfs: boolean): Promise<string> {
    const result = await uploadToIpfs(createPlaceTokenMetadata(metadata), false, localIpfs);

    return result.metdata_uri;
}

export async function upload_item_metadata(minter_address: string, model_path: string, localIpfs: boolean): Promise<string> {
    const data: Buffer = fs.readFileSync(model_path);

    const result = await uploadToIpfs(createItemTokenMetadata({
        name: "My awesome item",
        description: "A nice item",
        minter: minter_address,
        modelBlob: new File([data], "model.glb", {type: "model/gltf-binary"}),
        formats: [
            {
                mimeType: "model/gltf-binary", // model/gltf+json, model/gltf-binary
                fileSize: data.length
            }
        ],
    }), false, localIpfs);

    return result.metdata_uri;
}

export interface ContractMetadata {
    description: string;
    interfaces: string[],
    name: string;
    version: string;
}

// TODO: add to some config or so.
const metaRepository = 'https://github.com/tz1and';
const metaHomepage = 'https://www.tz1and.com';
const metaAcknowledgement = "\n\nBased on Seb Mondet's FA2 implementation: https://gitlab.com/smondet/fa2-smartpy.git"
const metaAuthors = ['852Kerfunke <https://github.com/852Kerfunkle>'];
const metaLicense = { name: "MIT" };

function createContractMetadata(metadata: ContractMetadata, is_fa2: boolean): any {

    const description = is_fa2 ? metadata.description + metaAcknowledgement : metadata.description;
    const authors = is_fa2 ? metaAuthors.concat('Seb Mondet <https://seb.mondet.org>') : metaAuthors;

    return {
        name: metadata.name,
        description: description,
        authors: authors,
        homepage: metaHomepage,
        repository: metaRepository,
        license: metaLicense,
        interfaces: metadata.interfaces,
        version: metadata.version
    };
}

export async function upload_contract_metadata(metadata: ContractMetadata, localIpfs: boolean, is_fa2: boolean = false): Promise<string> {
    const result = await uploadToIpfs(createContractMetadata(metadata, is_fa2), true, localIpfs);

    console.log(`${metadata.name} contract metadata: ${result.metdata_uri}`);

    return result.metdata_uri;
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

function createPlaceTokenMetadata(metadata: PlaceMetadata): any {
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
    
    return full_metadata;
}

interface ItemMetadata {
    description: string;
    minter: string;
    name: string;
    modelBlob: typeof File;
    formats: object[];
}

function createItemTokenMetadata(metadata: ItemMetadata): any {
    return {
        name: metadata.name,
        description: metadata.description,
        minter: metadata.minter,
        isTransferable: true,
        isBooleanAmount: false,
        shouldPreferSymbol: false,
        symbol: 'Item',
        artifactUri: metadata.modelBlob,
        decimals: 0,
        formats: metadata.formats
    };
}