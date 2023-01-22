import PostDeployBase, { PostDeployContracts } from "../commands/PostDeployBase";


export default class PostMarketplace extends PostDeployBase {
    protected printContracts(contracts: PostDeployContracts): void {
        console.log("VITE_ITEM_V1_CONTRACT=" + contracts.get("items_FA2_contract")!.address);
        console.log("VITE_ITEM_CONTRACT=" + contracts.get("items_v2_FA2_contract")!.address);
        console.log("VITE_PLACE_V1_CONTRACT=" + contracts.get("places_FA2_contract")!.address);
        console.log("VITE_PLACE_CONTRACT=" + contracts.get("places_v2_FA2_contract")!.address);
        console.log("VITE_INTERIOR_CONTRACT=" + contracts.get("interiors_FA2_contract")!.address);
        console.log("VITE_DAO_CONTRACT=" + contracts.get("dao_FA2_contract")!.address);
        console.log("VITE_WORLD_CONTRACT=" + contracts.get("World_v2_contract")!.address);
        console.log("VITE_MINTER_CONTRACT=" + contracts.get("Minter_v2_contract")!.address);
        console.log("VITE_DUTCH_AUCTION_CONTRACT=" + contracts.get("Dutch_v2_contract")!.address);
        console.log("VITE_FACTORY_CONTRACT=" + contracts.get("Factory_contract")!.address);
        console.log("VITE_REGISTRY_CONTRACT=" + contracts.get("Registry_contract")!.address);
        console.log()
        console.log(`contracts:
  tezlandItems:
    address: ${contracts.get("items_FA2_contract")!.address}
    typename: tezlandFA2Fungible

  tezlandItemsV2:
    address: ${contracts.get("items_v2_FA2_contract")!.address}
    typename: tezlandFA2FungibleV2

  tezlandPlaces:
    address: ${contracts.get("places_FA2_contract")!.address}
    typename: tezlandFA2NFT

  tezlandPlacesV2:
    address: ${contracts.get("places_v2_FA2_contract")!.address}
    typename: tezlandFA2NFTV2NonstandardTransfer

  tezlandInteriors:
    address: ${contracts.get("interiors_FA2_contract")!.address}
    typename: tezlandFA2NFTV2NonstandardTransfer

  tezlandDAO:
    address: ${contracts.get("dao_FA2_contract")!.address}
    typename: tezlandDAO

  tezlandWorld:
    address: ${contracts.get("World_contract")!.address}
    typename: tezlandWorld

  tezlandWorldV2:
    address: ${contracts.get("World_v2_contract")!.address}
    typename: tezlandWorldV2
    
  tezlandMinter:
    address: ${contracts.get("Minter_contract")!.address}
    typename: tezlandMinter

  tezlandMinterV2:
    address: ${contracts.get("Minter_v2_contract")!.address}
    typename: tezlandMinterV2

  tezlandDutchAuctions:
    address: ${contracts.get("Dutch_contract")!.address}
    typename: tezlandDutchAuctions

  tezlandDutchAuctionsV2:
    address: ${contracts.get("Dutch_v2_contract")!.address}
    typename: tezlandDutchAuctionsV2
    
  tezlandFactory:
    address: ${contracts.get("Factory_contract")!.address}
    typename: tezlandFactory
    
  tezlandRegistry:
    address: ${contracts.get("Registry_contract")!.address}
    typename: tezlandRegistry

  tezlandItemsCollection:
    code_hash: -767789104
    typename: tezlandItemsCollection\n`);
    }

    
}