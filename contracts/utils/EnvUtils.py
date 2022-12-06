from os import environ
import smartpy as sp


#
# Environment utilities, for tests, etc.
#

def viewExceptionOrUnit(message) -> sp.Expr:
    """Returns `message` if compiling tests, sp.unit otherwise."""
    if environ.get("SMARTPY_NODE_DEV") == "test":
        #print(f"In test scenario, failing with {message}")
        return message

    #print(f"In test scenario, failing with sp.unit")
    return sp.unit

def view_helper(func: sp.Expr):
    def view_helper_check_option(*args, **kwargs):
        res = func(*args, **kwargs)
        # TODO: some way to check if expression is option?
        assert isinstance(res, sp.Expr), "view_helper function does not return expression"
        return res
    return view_helper_check_option
