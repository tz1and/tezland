import smartpy as sp


#
# Generic (lazy) map for convenience.
#

class GenericMap:
    """Generic map/bigmap."""
    def __init__(self, key_type, value_type, default_value=None, get_error=None, big_map=True) -> None:
        self.key_type = key_type
        self.value_type = value_type
        self.default_value = default_value
        self.get_error = get_error
        self.big_map = big_map

    def make(self, defaults={}):
        if self.big_map:
            return sp.big_map(l=defaults, tkey=self.key_type, tvalue=self.value_type)
        else:
            return sp.map(l=defaults, tkey=self.key_type, tvalue=self.value_type)

    def add(self, map, key, value = None):
        if value is None:
            if self.default_value is not None:
                map[key] = self.default_value
            else:
                raise Exception("NO_DEFAULT_VALUE")
        else:
            map[key] = value

    def remove(self, map, key):
        del map[key]

    def contains(self, map, key):
        return map.contains(key)

    def get(self, map, key, message=None):
        return map.get(key, message=(message if (message is not None) else self.get_error))

class AddressSet(GenericMap):
    """Lazy set of addresses."""
    def __init__(self):
        super().__init__(sp.TAddress, sp.TUnit, sp.unit)