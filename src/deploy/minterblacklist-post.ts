import PostDeployBase, { PostDeployContracts } from "../commands/PostDeployBase";


export default class MinterBlacklistPostDeploy extends PostDeployBase {
    // TODO: should really use the deployments registry!
    protected override printContracts(contracts: PostDeployContracts): void { }
}