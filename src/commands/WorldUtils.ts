import { MichelsonMap } from '@taquito/taquito';
import * as ipfs from '../ipfs'

namespace WorldUtils {
    export async function prepareNewPlace(id: number, center: number[], border: number[][], minter: string, is_sandbox_net: boolean, buildHeight: number = 10): Promise<any> {
        const place_metadata_url = await ipfs.upload_place_metadata({
            name: `Place #${id}`,
            description: `A nice place with the number ${id}`,
            minter: minter,
            centerCoordinates: center,
            borderCoordinates: border,
            buildHeight: buildHeight,
            placeType: "exterior"
        }, is_sandbox_net);
        console.log(`place token metadata: ${place_metadata_url}`);

        const metadata_map = new MichelsonMap<string,string>({ prim: "map", args: [{prim: "string"}, {prim: "bytes"}]});
        metadata_map.set('', Buffer.from(place_metadata_url, 'utf8').toString('hex'));
        return {
            to_: minter,
            metadata: metadata_map
        }
    }

    export async function prepareNewInteriorPlace(id: number, center: number[], border: number[][], minter: string, is_sandbox_net: boolean, buildHeight: number = 10): Promise<any> {
        const place_metadata_url = await ipfs.upload_place_metadata({
            name: `Interior #${id}`,
            description: `A nice interior with the number ${id}`,
            minter: minter,
            centerCoordinates: center,
            borderCoordinates: border,
            buildHeight: buildHeight,
            placeType: "interior"
        }, is_sandbox_net);
        console.log(`interior place token metadata: ${place_metadata_url}`);

        const metadata_map = new MichelsonMap<string,string>({ prim: "map", args: [{prim: "string"}, {prim: "bytes"}]});
        metadata_map.set('', Buffer.from(place_metadata_url, 'utf8').toString('hex'));
        return {
            to_: minter,
            metadata: metadata_map
        }
    }
}

export default WorldUtils;