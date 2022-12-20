import * as fs from 'fs';
import { ipfs_client, uploadToIpfs } from './storage';
import { File } from 'nft.storage';
import { concat } from 'uint8arrays/concat'
import assert from 'assert';


export async function upload_place_metadata(metadata: PlaceMetadata, localIpfs: boolean): Promise<string> {
    const result = await uploadToIpfs(createPlaceTokenMetadata(metadata), false, localIpfs);

    return result.metdata_uri;
}

export async function upload_item_metadata(minter_address: string, model_path: string, polygonCount: number, localIpfs: boolean): Promise<string> {
    const data: Buffer = fs.readFileSync(model_path);

    const result = await uploadToIpfs(createItemTokenMetadata({
        name: "My awesome item",
        description: "A nice item",
        minter: minter_address,
        modelBlob: new File([data], "model.glb", {type: "model/gltf-binary"}),
        polygonCount: polygonCount,
        formats: [
            {
                uri: new File([data], "model.glb", {type: "model/gltf-binary"}),
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

export async function upload_metadata(metadata: any, localIpfs: boolean): Promise<string> {
    const result = await uploadToIpfs(metadata, true, localIpfs, true);

    console.log(`${metadata.name} metadata: ${result.metdata_uri}`);

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
        shouldPreferSymbol: false,
        symbol: 'tz1and Place',
        //artifactUri: cid,
        decimals: 0,
        placeType: metadata.placeType
    }

    // TODO: do interiors have different geometry?
    //if (metadata.placeType === "exterior") {
        assert(metadata.borderCoordinates);
        assert(metadata.centerCoordinates);
        assert(metadata.buildHeight);
        full_metadata.centerCoordinates = metadata.centerCoordinates;
        full_metadata.borderCoordinates = metadata.borderCoordinates;
        full_metadata.buildHeight = metadata.buildHeight;
    //}
    
    return full_metadata;
}

interface ItemMetadata {
    description: string;
    minter: string;
    name: string;
    modelBlob: typeof File;
    formats: object[];
    polygonCount: number
}

function createItemTokenMetadata(metadata: ItemMetadata): any {
    return {
        name: metadata.name,
        description: metadata.description,
        minter: metadata.minter,
        isTransferable: true,
        isBooleanAmount: false,
        shouldPreferSymbol: false,
        symbol: 'tz1and Item',
        artifactUri: metadata.modelBlob,
        tags: ["default", "development", "mint"],
        decimals: 0,
        formats: metadata.formats,
        polygonCount: metadata.polygonCount,
        baseScale: 1
    };
}

export async function downloadFile(file_url: string) {
    // TODO: does cat() return chunks?
    const chunks: Uint8Array[] = []
    for await (const chunk of ipfs_client.cat(file_url.replace("ipfs://", '')))
        chunks.push(chunk);

    return concat(chunks);
}