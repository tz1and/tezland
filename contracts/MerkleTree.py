# Utility to compute the root of a merkle tree in logarithmic time using a proof-path array

import smartpy as sp

class MerkleTree:
    MerkleProofType = sp.TRecord(proof=sp.TList(sp.TBytes), leaf=sp.TBytes).layout(("proof", "leaf"))

    def __init__(self, leafDataType: sp.TType):
        self.LeafDataType = leafDataType

    def compute_merkle_root(proof, leaf):
        computed_hash = sp.local("computed_hash", sp.sha256(leaf))

        with sp.for_("proof_element", proof) as proof_element:
            with sp.if_(computed_hash.value < proof_element):
                computed_hash.value = sp.sha256(computed_hash.value + proof_element)
            with sp.else_():
                computed_hash.value = sp.sha256(proof_element + computed_hash.value)
            
        return computed_hash.value