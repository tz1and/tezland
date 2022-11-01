# Utility to compute the root of a merkle tree in logarithmic time using a proof-path array
# Based on: https://github.com/AnshuJalan/token-drop-template/blob/master/contracts/utils/merkle_tree.py

import smartpy as sp

FA2 = sp.io.import_script_from_url("file:contracts/FA2.py")


class MerkleTree:
    MerkleProofType = sp.TRecord(proof=sp.TList(sp.TBytes), leaf=sp.TBytes).layout(("proof", "leaf"))

    def __init__(self, leafDataType: sp.TType):
        self.LeafDataType = leafDataType

    def compute_merkle_root(self, proof, leaf):
        sp.set_type(proof, self.MerkleProofType.proof)
        sp.set_type(leaf, self.MerkleProofType.leaf)
        computed_hash = sp.local("computed_hash", sp.sha256(leaf))

        with sp.for_("proof_element", proof) as proof_element:
            with sp.if_(computed_hash.value < proof_element):
                computed_hash.value = sp.sha256(computed_hash.value + proof_element)
            with sp.else_():
                computed_hash.value = sp.sha256(proof_element + computed_hash.value)

        return computed_hash.value

    def validate_merkle_root(self, proof, leaf, root):
        sp.set_type(proof, self.MerkleProofType.proof)
        sp.set_type(leaf, self.MerkleProofType.leaf)
        sp.set_type(root, sp.TBytes)
        return self.compute_merkle_root(proof, leaf) == root

    def unpack_leaf(self, leaf):
        sp.set_type(leaf, self.MerkleProofType.leaf)
        return sp.unpack(leaf, self.LeafDataType).open_some("INVALID_LEAF")

# Leaf types
t_royalties_merkle_leaf = sp.TRecord(
    fa2 = sp.TAddress,
    token_id = sp.TNat,
    token_royalties = FA2.t_royalties_v2
).layout(("fa2", ("token_id", "token_royalties")))

# Tree classes
royalties = MerkleTree(t_royalties_merkle_leaf)
collections = MerkleTree(sp.TAddress)

# Other related types.
t_fa2_with_merkle_proof = sp.TRecord(
    fa2 = sp.TAddress,
    merkle_proof = sp.TOption(collections.MerkleProofType)
).layout(("fa2", "merkle_proof"))