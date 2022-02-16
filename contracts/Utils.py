import smartpy as sp

#
# Lazy set of permitted FA2 tokens for 'other' type.
class Address_set:
    def make(self, fa2_map={}):
        return sp.big_map(l=fa2_map, tkey=sp.TAddress, tvalue=sp.TUnit)
    def add(self, set, fa2):
        set[fa2] = sp.unit
    def remove(self, set, fa2):
        del set[fa2]
    def contains(self, set, fa2):
        return set.contains(fa2)

def isPowerOfTwoMinusOne(x):
    return ((x + 1) & x) == sp.nat(0)
