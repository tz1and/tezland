# TODO: Replace all occurences in current contracts/tests of these errors with these functions.
# TODO: only_owner/not_owner are synonymous

def make_error_msg(prefix: str, message: str):
    return (prefix + message)

# Mostly world related
def no_permission(prefix=""):    return make_error_msg(prefix, "NO_PERMISSION")
def not_owner(prefix=""):        return make_error_msg(prefix, "NOT_OWNER")
def parameter_error(prefix=""):  return make_error_msg(prefix, "PARAM_ERROR")
def data_length(prefix=""):      return make_error_msg(prefix, "DATA_LEN")
def chunk_limit(prefix=""):      return make_error_msg(prefix, "CHUNK_LIMIT")
def chunk_item_limit(prefix=""): return make_error_msg(prefix, "CHUNK_ITEM_LIMIT")
def not_for_sale(prefix=""):     return make_error_msg(prefix, "NOT_FOR_SALE")
def no_amount(prefix=""):        return make_error_msg(prefix, "NO_AMOUNT")
def wrong_amount(prefix=""):     return make_error_msg(prefix, "WRONG_AMOUNT")
def wrong_item_type(prefix=""):  return make_error_msg(prefix, "WRONG_ITEM_TYPE")
def royalties_error(prefix=""):  return make_error_msg(prefix, "ROYALTIES_ERROR")

# Migration related
def migration_place_not_emptry(prefix=""):  return make_error_msg(prefix, "MIGRATION_PLACE_NOT_EMPTY")

# Minter/registry related
def not_public(prefix=""):                return make_error_msg(prefix, "NOT_PUBLIC")
def not_private(prefix=""):               return make_error_msg(prefix, "NOT_PRIVATE")
def only_owner(prefix=""):                return make_error_msg(prefix, "ONLY_OWNER")
def invalid_collection(prefix=""):        return make_error_msg(prefix, "INVALID_COLLECTION")
def collection_exists(prefix=""):         return make_error_msg(prefix, "COLLECTION_EXISTS")
def not_proposed_owner(prefix=""):        return make_error_msg(prefix, "NOT_PROPOSED_OWNER")
def not_owner_or_collaborator(prefix=""): return make_error_msg(prefix, "NOT_OWNER_OR_COLLABORATOR")

# Legacy royalites related
def unknown_royalties(prefix=""):   return make_error_msg(prefix, "UNKNOWN_ROYALTIES")