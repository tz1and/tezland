from os import environ
import smartpy as sp


#
# Environment utilities, for tests, etc.
#

def viewExceptionOrUnit(message):
    """Returns `message` if compiling tests, sp.unit otherwise."""
    if environ.get("SMARTPY_NODE_DEV") == "test":
        #print(f"In test scenario, failing with {message}")
        return message

    #print(f"In test scenario, failing with sp.unit")
    return sp.unit