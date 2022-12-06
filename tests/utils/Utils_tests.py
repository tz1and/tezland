import smartpy as sp

from contracts.utils import Utils


class UtilsTest(sp.Contract):
    def __init__(self):
        self.init_storage()

    @sp.entry_point
    def testIsContract(self, address, expected):
        sp.verify(Utils.isContract(address) == expected)

    @sp.entry_point
    def testOnlyContract(self, address):
        Utils.onlyContract(address)

    @sp.entry_point
    def testOpenSomeOrDefault(self, option, default, expected):
        res = Utils.openSomeOrDefault(option, default)
        sp.verify(res == expected)

    @sp.entry_point
    def testIfSomeRun(self):
        Utils.ifSomeRun(sp.some(sp.nat(10)), lambda x: sp.verify(x == sp.nat(10)))
        Utils.ifSomeRun(sp.none, lambda x: sp.verify(False))

    @sp.entry_point
    def testValidateIpfsUri(self, uri):
        Utils.validateIpfsUri(uri)

    @sp.entry_point
    def testIsPowerOfTwoMinusOne(self, value, expected):
        sp.verify(Utils.isPowerOfTwoMinusOne(value) == expected)


@sp.add_test(name = "Utils_tests", profile = True)
def test():
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob   = sp.test_account("Robert")
    scenario = sp.test_scenario()

    scenario.h1("Fees contract")
    scenario.table_of_contents()

    # Let's display the accounts:
    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])

    scenario.h2("Test Fees")

    scenario.h3("Contract origination")
    utils = UtilsTest()
    scenario += utils

    scenario.h3("isContract")

    utils.testIsContract(address=bob.address, expected=False).run(sender=admin)
    utils.testIsContract(address=utils.address, expected=True).run(sender=admin)
    utils.testIsContract(address=sp.address("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU"), expected=False).run(sender=admin)
    utils.testIsContract(address=sp.address("tz28KEfLTo3wg2wGyJZMjC1MaDA1q68s6tz5"), expected=False).run(sender=admin)
    utils.testIsContract(address=sp.address("tz3LL3cfMfBV4fPaPZdcj9TjPa3XbvLiXw9V"), expected=False).run(sender=admin)
    utils.testIsContract(address=sp.address("KT1WmMn55RjXwk5Xb4YE6asjy5BvMiEsB6nA"), expected=True).run(sender=admin)

    scenario.h3("onlyContract")

    utils.testOnlyContract(bob.address).run(sender=admin, valid=False, exception="NOT_CONTRACT")
    utils.testOnlyContract(utils.address).run(sender=admin)
    utils.testOnlyContract(sp.address("tz1Ke2h7sDdakHJQh8WX4Z372du1KChsksyU")).run(sender=admin, valid=False, exception="NOT_CONTRACT")
    utils.testOnlyContract(sp.address("tz28KEfLTo3wg2wGyJZMjC1MaDA1q68s6tz5")).run(sender=admin, valid=False, exception="NOT_CONTRACT")
    utils.testOnlyContract(sp.address("tz3LL3cfMfBV4fPaPZdcj9TjPa3XbvLiXw9V")).run(sender=admin, valid=False, exception="NOT_CONTRACT")
    #utils.testOnlyContract(sp.address("tz4aL3Z372duFfPawg2wG9TjPa3XbvLiXw9V")).run(sender=admin, valid=False, exception="NOT_CONTRACT") # Some day....
    utils.testOnlyContract(sp.address("KT1WmMn55RjXwk5Xb4YE6asjy5BvMiEsB6nA")).run(sender=admin)

    scenario.h3("testOpenSomeOrDefault")

    utils.testOpenSomeOrDefault(option=sp.some(sp.nat(10)), default=sp.nat(2), expected=sp.nat(10)).run(sender=admin)
    utils.testOpenSomeOrDefault(option=sp.none, default=sp.nat(2), expected=sp.nat(2)).run(sender=admin)

    scenario.h3("testIfSomeRun")

    utils.testIfSomeRun().run(sender=admin)

    scenario.h3("testValidateIpfsUri")

    utils.testValidateIpfsUri(sp.utils.bytes_of_string("")).run(sender=admin, valid=False, exception="INVALID_METADATA")
    utils.testValidateIpfsUri(sp.utils.bytes_of_string("https://newtoken.com")).run(sender=admin, valid=False, exception="INVALID_METADATA")
    utils.testValidateIpfsUri(sp.utils.bytes_of_string("ipfs://newtoken.com")).run(sender=admin, valid=False, exception="INVALID_METADATA")
    utils.testValidateIpfsUri(sp.utils.bytes_of_string("ipfs://QmbWqxBEKC3P8tqsKc98xmWNzrzDtRLMiMPL8wBuTGsMn")).run(sender=admin, valid=False, exception="INVALID_METADATA")
    utils.testValidateIpfsUri(sp.utils.bytes_of_string("ipfs://QmbWqxBEKC3P8tqsKc98xmWNzrzDtRLMiMPL8wBuTGsMnR")).run(sender=admin)
    utils.testValidateIpfsUri(sp.utils.bytes_of_string("ipfs://bafkreicce3xlhin5oyconwqyqxp2pf7fzxf27i77iuh4xiwebvtf3ffqym")).run(sender=admin)
    utils.testValidateIpfsUri(sp.utils.bytes_of_string("ipfs://bafkreibunhe5632xyodlx7r52kzf7aleeh3ttfrodjpowxnjbrxnsgy36u/metadata.json")).run(sender=admin)

    scenario.h3("testIsPowerOfTwoMinusOne")

    utils.testIsPowerOfTwoMinusOne(value=sp.nat(10), expected=False).run(sender=admin)
    utils.testIsPowerOfTwoMinusOne(value=sp.nat(8), expected=False).run(sender=admin)
    utils.testIsPowerOfTwoMinusOne(value=sp.nat(16), expected=False).run(sender=admin)
    utils.testIsPowerOfTwoMinusOne(value=sp.nat(1048576), expected=False).run(sender=admin)
    utils.testIsPowerOfTwoMinusOne(value=sp.nat(3), expected=True).run(sender=admin)
    utils.testIsPowerOfTwoMinusOne(value=sp.nat(7), expected=True).run(sender=admin)
    utils.testIsPowerOfTwoMinusOne(value=sp.nat(63), expected=True).run(sender=admin)
    utils.testIsPowerOfTwoMinusOne(value=sp.nat(127), expected=True).run(sender=admin)
    utils.testIsPowerOfTwoMinusOne(value=sp.nat(1048575), expected=True).run(sender=admin)

    # TODO: sendIfValue