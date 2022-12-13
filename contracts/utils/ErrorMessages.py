# TODO: Replace all occurences in current contracts/tests of these errors with these functions.

def make_error_msg(prefix: str, message: str):
    return (prefix + message)

def no_permission(prefix=""):    return make_error_msg(prefix, "NO_PERMISSION")
def not_owner(prefix=""):        return make_error_msg(prefix, "NOT_OWNER")
def parameter_error(prefix=""):  return make_error_msg(prefix, "PARAM_ERROR")
def data_length(prefix=""):      return make_error_msg(prefix, "DATA_LEN")
def chunk_limit(prefix=""):      return make_error_msg(prefix, "CHUNK_LIMIT")
def chunk_item_limit(prefix=""): return make_error_msg(prefix, "CHUNK_ITEM_LIMIT")
def not_for_sale(prefix=""):     return make_error_msg(prefix, "NOT_FOR_SALE")
def wrong_amount(prefix=""):     return make_error_msg(prefix, "WRONG_AMOUNT")
def wrong_item_type(prefix=""):  return make_error_msg(prefix, "WRONG_ITEM_TYPE")
def royalties_error(prefix=""):  return make_error_msg(prefix, "ROYALTIES_ERROR")

def migration_place_not_emptry(prefix=""):  return make_error_msg(prefix, "MIGRATION_PLACE_NOT_EMPTY")