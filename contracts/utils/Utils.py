import smartpy as sp


#
# Utility functions
#

def isPowerOfTwoMinusOne(x):
    """Returns true if x is power of 2 - 1"""
    return ((x + 1) & x) == sp.nat(0)

def sendIfValue(to, amount):
    """Transfer `amount` to `to` if greater 0."""
    with sp.if_(amount > sp.tez(0)):
        sp.send(to, amount)

@sp.inline_result
def openSomeOrDefault(e: sp.TOption, default):
    """If option `e` is some, return it's value, else return `default`."""
    with e.match_cases() as arg:
        with arg.match("None"):
            sp.result(default)
        with arg.match("Some") as open:
            sp.result(open)

def ifSomeRun(e: sp.TOption, f):
    """If option `e` is some, execute function `f`."""
    with e.match("Some") as open: f(open)

THRESHOLD_ADDRESS = sp.address("tz3jfebmewtfXYD1Xef34TwrfMg2rrrw6oum")

def isContract(addr: sp.TAddress):
    """Throws if `addr` is a contract address."""
    sp.set_type(addr, sp.TAddress)
    sp.verify(addr > THRESHOLD_ADDRESS, "NOT_CONTRACT")

def validateIpfsUri(metadata_uri):
    """Validate IPFS Uri."""
    # Basic validation of the metadata, try to make sure it's a somewhat valid ipfs URI.
    # Ipfs cid v0 + proto is 53 chars.
    sp.verify((sp.slice(metadata_uri, 0, 7).open_some("INVALID_METADATA") == sp.utils.bytes_of_string("ipfs://"))
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