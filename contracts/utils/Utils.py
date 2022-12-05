from os import environ
import smartpy as sp


#
# Utility functions
#

def isPowerOfTwoMinusOne(x):
    """Returns expression that evaluates to true if x is power of 2 - 1"""
    return ((x + 1) & x) == sp.nat(0)

def sendIfValue(to, amount):
    """Transfer `amount` to `to` if greater 0."""
    with sp.if_(amount > sp.tez(0)):
        sp.send(to, amount)

@sp.inline_result
def openSomeOrDefault(e: sp.TOption, default):
    """If option `e` is some, return its value, else return `default`."""
    with e.match_cases() as arg:
        with arg.match("None"):
            sp.result(default)
        with arg.match("Some") as open:
            sp.result(open)

def ifSomeRun(e: sp.TOption, f):
    """If option `e` is some, execute function `f`."""
    with e.match("Some") as open: f(open)

#CONTRACT_ADDRESS_LOW = sp.address("KT18amZmM5W7qDWVt2pH6uj7sCEd3kbzLrHT")
#CONTRACT_ADDRESS_HIGH = sp.address("KT1XvNYseNDJJ6Kw27qhSEDF8ys8JhDopzfG")

def isContract(addr: sp.TAddress):
    """Returns expression that checks if `addr` is a contract address.

    In a packed address, the 7th byte is 0x01 for originated accounts
    and 0x00 for implicit accounts. The 8th byte is the curve. FYI."""
    #return (addr >= CONTRACT_ADDRESS_LOW) & (addr <= CONTRACT_ADDRESS_HIGH) # prob best not to.
    return sp.slice(sp.pack(sp.set_type_expr(addr, sp.TAddress)), 6, 1) == sp.some(sp.bytes("0x01"))

def onlyContract(addr: sp.TAddress):
    """Fails with NOT_CONTRACT if `addr` is not a contract address."""
    sp.verify(isContract(addr), "NOT_CONTRACT")

def validateIpfsUri(metadata_uri: sp.TBytes):
    """Validate IPFS Uri.

    Basic validation, try to make sure it's a somewhat valid ipfs URI.
    Ipfs cid v0 + proto is 53 chars."""
    sp.verify((sp.slice(metadata_uri, 0, 7) == sp.some(sp.utils.bytes_of_string("ipfs://")))
        & (sp.len(metadata_uri) >= sp.nat(53)), "INVALID_METADATA")

def contractSetMetadata(contract, metadata_uri):
    """ContractMetadata set_metadata."""
    sp.set_type(contract, sp.TAddress)
    sp.set_type(metadata_uri, sp.TBytes)
    set_metadata_handle = sp.contract(
        sp.TBigMap(sp.TString, sp.TBytes),
        contract,
        entry_point='set_metadata').open_some()
    sp.transfer(sp.big_map({"": metadata_uri}), sp.mutez(0), set_metadata_handle)

# Metaprogramming stuff
def viewExceptionOrUnit(message):
    """Returns `message` if compiling tests, sp.unit otherwise."""
    if environ.get("SMARTPY_NODE_DEV") == "test":
        #print(f"In test scenario, failing with {message}")
        return message

    #print(f"In test scenario, failing with sp.unit")
    return sp.unit