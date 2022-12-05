"""
FA2 standard: https://gitlab.com/tezos/tzip/-/blob/master/proposals/tzip-12/tzip-12.md. <br/>
Documentation: [FA2 lib](/docs/guides/FA/FA2_lib).

Multiple mixins and several standard [policies](https://gitlab.com/tezos/tzip/-/blob/master/proposals/tzip-12/permissions-policy.md#operator-permission-behavior) are supported.
"""

import smartpy as sp
import types


#########
# Types #
#########


t_operator_permission = sp.TRecord(
    owner=sp.TAddress, operator=sp.TAddress, token_id=sp.TNat
).layout(("owner", ("operator", "token_id")))

t_update_operators_params = sp.TList(
    sp.TVariant(
        add_operator=t_operator_permission, remove_operator=t_operator_permission
    )
)

t_transfer_tx = sp.TRecord(
    to_=sp.TAddress,
    token_id=sp.TNat,
    amount=sp.TNat,
).layout(("to_", ("token_id", "amount")))

t_transfer_batch = sp.TRecord(
    from_=sp.TAddress,
    txs=sp.TList(t_transfer_tx),
).layout(("from_", "txs"))

t_transfer_params = sp.TList(t_transfer_batch)

t_balance_of_request = sp.TRecord(owner=sp.TAddress, token_id=sp.TNat).layout(
    ("owner", "token_id")
)

t_balance_of_response = sp.TRecord(
    request=t_balance_of_request, balance=sp.TNat
).layout(("request", "balance"))

t_balance_of_params = sp.TRecord(
    callback=sp.TContract(sp.TList(t_balance_of_response)),
    requests=sp.TList(t_balance_of_request),
).layout(("requests", "callback"))

# mint types

t_mint_nft_batch = sp.TList(sp.TRecord(
    to_=sp.TAddress,
    metadata=sp.TMap(sp.TString, sp.TBytes)
).layout(("to_", "metadata")))

t_mint_fungible_batch = sp.TList(sp.TRecord(
    to_=sp.TAddress,
    amount=sp.TNat,
    token=sp.TVariant(
        new=sp.TRecord(
            metadata=sp.TMap(sp.TString, sp.TBytes)
        ),
        existing=sp.TNat
    ).layout(("new", "existing"))
).layout(("to_", ("amount", "token"))))

# burn types

t_burn_batch = sp.TList(sp.TRecord(
    from_=sp.TAddress,
    amount=sp.TNat,
    token_id=sp.TNat
).layout(("from_", ("amount", "token_id"))))

# adhoc operator types

t_adhoc_operator_permission = sp.TRecord(
    operator=sp.TAddress, token_id=sp.TNat
).layout(("operator", "token_id"))

t_adhoc_operator_params = sp.TVariant(
    add_adhoc_operators = sp.TSet(t_adhoc_operator_permission),
    clear_adhoc_operators = sp.TUnit
).layout(("add_adhoc_operators", "clear_adhoc_operators"))

# royalties

# royalties, per contributor. Must add up to less or eqaual
# total shares - and maybe not be more than some % of shares.
t_royalties_shares = sp.TMap(sp.TAddress, sp.TNat)

# Interop royalties are based on new FA2 royalties, with total shares.
t_royalties_interop = sp.TRecord(
    # Total shares. Because calculating powers of 10 is lame.
    total = sp.TNat,
    shares = t_royalties_shares
).layout(("total", "shares"))

# mint with royalties

t_mint_nft_royalties_batch = sp.TList(sp.TRecord(
    to_=sp.TAddress,
    metadata=sp.TMap(sp.TString, sp.TBytes),
    royalties=t_royalties_shares
).layout(("to_", ("metadata", "royalties"))))

t_mint_fungible_royalties_batch = sp.TList(sp.TRecord(
    to_=sp.TAddress,
    amount=sp.TNat,
    token=sp.TVariant(
        new=sp.TRecord(
            metadata=sp.TMap(sp.TString, sp.TBytes),
            royalties=t_royalties_shares
        ).layout(("metadata", "royalties")),
        existing=sp.TNat
    ).layout(("new", "existing"))
).layout(("to_", ("amount", "token"))))

# token_extra

t_token_extra_royalties_supply = sp.TRecord(
    supply=sp.TNat,
    royalty_info=t_royalties_shares
).layout(("supply", "royalty_info"))

t_token_extra_royalties = sp.TRecord(
    royalty_info=t_royalties_shares
)

t_token_extra_supply = sp.TRecord(
    supply=sp.TNat
)


############
# Policies #
############


class NoTransfer:
    """(Transfer Policy) No transfer allowed."""

    def init_policy(self, contract):
        self.name = "no-transfer"
        self.supports_transfer = False
        self.supports_operator = False

    def check_tx_transfer_permissions(self, contract, from_, to_, token_id):
        pass

    def check_operator_add_permissions(self, contract, operator_permission):
        pass

    def check_operator_delete_permissions(self, contract, operator_permission):
        pass

    def is_operator(self, contract, operator_permission):
        return False


class OwnerTransfer:
    """(Transfer Policy) Only owner can transfer tokens, no operator
    allowed."""

    def init_policy(self, contract):
        self.name = "owner-transfer"
        self.supports_transfer = True
        self.supports_operator = False

    def check_tx_transfer_permissions(self, contract, from_, to_, token_id):
        sp.verify(sp.sender == from_, "FA2_NOT_OWNER")

    def check_operator_add_permissions(self, contract, operator_permission):
        pass

    def check_operator_delete_permissions(self, contract, operator_permission):
        pass

    def is_operator(self, contract, operator_permission):
        return False


class OwnerOrOperatorTransfer:
    """(Transfer Policy) Only owner and operators can transfer tokens.

    Operators allowed.
    """

    # Controls whether operators can delete their own operator permissions.
    allow_operator_delete_own = True

    def init_policy(self, contract):
        self.name = "owner-or-operator-transfer"
        self.supports_transfer = True
        self.supports_operator = True
        contract.update_initial_storage(
            operators=sp.big_map(tkey=t_operator_permission, tvalue=sp.TUnit)
        )

    def check_tx_transfer_permissions(self, contract, from_, to_, token_id):
        sp.verify(
            (sp.sender == from_)
            | contract.data.operators.contains(
                sp.record(owner=from_, operator=sp.sender, token_id=token_id)
            ),
            message="FA2_NOT_OPERATOR",
        )

    def check_operator_add_permissions(self, contract, operator_permission):
        sp.verify(operator_permission.owner == sp.sender, "FA2_NOT_OWNER")

    def check_operator_delete_permissions(self, contract, operator_permission):
        if self.allow_operator_delete_own:
            sp.verify((operator_permission.owner == sp.sender) | (operator_permission.operator == sp.sender), "FA2_NOT_OWNER_OR_OPERATOR")
        else:
            sp.verify(operator_permission.owner == sp.sender, "FA2_NOT_OWNER")

    def is_operator(self, contract, operator_permission):
        return contract.data.operators.contains(operator_permission)


class OwnerOrOperatorAdhocTransfer:
    """(Transfer Policy) Only owner and operators can transfer tokens.

    Adds a `update_adhoc_operators` entrypoint. Checks both operators
    and adhoc operators.

    Provides adhoc, temporary operators. Cheap and storage efficient.
    They are supposed to apply only to the current operation group.
    They are only valid in the current block level.

    By default, adhoc operators aren't checked in the is_operator view.

    For long-lasting operators, use standard operators.

    You've seen it here first :)
    """

    # Controls whether adhoc operators are checked in the is_operator view.
    check_adhoc_in_operator_view = False
    # Controls whether operators can delete their own operator permissions.
    allow_operator_delete_own = True

    def init_policy(self, contract):
        self.name = "owner-or-operator-transfer"
        self.supports_transfer = True
        self.supports_operator = True
        contract.update_initial_storage(
            operators=sp.big_map(tkey=t_operator_permission, tvalue=sp.TUnit),
            adhoc_operators = sp.set(t = sp.TBytes)
        )

        # Add make_adhoc_operator_key to contract.
        def make_adhoc_operator_key(self, owner, operator, token_id):
            t_adhoc_operator_record = sp.TRecord(
                owner=sp.TAddress,
                operator=sp.TAddress,
                token_id=sp.TNat,
                level=sp.TNat
            ).layout(("owner", ("operator", ("token_id", "level"))))

            return sp.sha3(sp.pack(sp.set_type_expr(sp.record(
                owner=owner,
                operator=operator,
                token_id=token_id,
                level=sp.level
            ), t_adhoc_operator_record)))

        contract.make_adhoc_operator_key = types.MethodType(make_adhoc_operator_key, contract)

        # Add update_adhoc_operators entrypoint to contract.
        def update_adhoc_operators(self, params):
            # Supports add_adhoc_operators, and clear_adhoc_operators.
            sp.set_type(params, t_adhoc_operator_params)

            with params.match_cases() as arg:
                with arg.match("add_adhoc_operators") as updates:
                    num_additions = sp.compute(sp.len(updates))
                    sp.verify(num_additions <= 100, "ADHOC_LIMIT")

                    # Remove as many adhoc operators as we added.
                    # We do this to make sure the storage diffs aren't lost
                    # on minting tokens. And to make sure the set doesn't grow larger
                    # than the adhoc operator limit.
                    counter = sp.local("counter", sp.nat(0))
                    with sp.for_("op", self.data.adhoc_operators.elements()) as op:
                        with sp.if_(counter.value < num_additions):
                            self.data.adhoc_operators.remove(op)
                            counter.value += 1

                    # Add adhoc ops from temp set.
                    with sp.for_("upd", updates.elements()) as upd:
                        self.data.adhoc_operators.add(self.make_adhoc_operator_key(
                            sp.sender, # Sender must be the owner
                            upd.operator,
                            upd.token_id))

                with arg.match("clear_adhoc_operators"):
                    # Only admin is allowed to do this.
                    # Otherwise someone could sneakily get storage diffs at
                    # the cost of everyone else.
                    self.onlyAdministrator()
                    # Clear adhoc operators.
                    self.data.adhoc_operators = sp.set(t = sp.TBytes)

        contract.update_adhoc_operators = sp.entry_point(update_adhoc_operators)

    def check_tx_transfer_permissions(self, contract, from_, to_, token_id):
        sp.verify(
            (sp.sender == from_)
            | contract.data.adhoc_operators.contains(
                contract.make_adhoc_operator_key(from_, sp.sender, token_id)
            )
            | contract.data.operators.contains(
                sp.record(owner=from_, operator=sp.sender, token_id=token_id)
            ),
            message="FA2_NOT_OPERATOR",
        )

    def check_operator_add_permissions(self, contract, operator_permission):
        sp.verify(operator_permission.owner == sp.sender, "FA2_NOT_OWNER")

    def check_operator_delete_permissions(self, contract, operator_permission):
        if self.allow_operator_delete_own:
            sp.verify((operator_permission.owner == sp.sender) | (operator_permission.operator == sp.sender), "FA2_NOT_OWNER_OR_OPERATOR")
        else:
            sp.verify(operator_permission.owner == sp.sender, "FA2_NOT_OWNER")

    def is_operator(self, contract, operator_permission):
        if self.check_adhoc_in_operator_view:
            adhoc_key = contract.make_adhoc_operator_key(operator_permission.owner, operator_permission.operator, operator_permission.token_id)
            return contract.data.adhoc_operators.contains(adhoc_key) | contract.data.operators.contains(operator_permission)
        else:
            return contract.data.operators.contains(operator_permission)


class PauseTransfer:
    """(Transfer Policy) Decorate any policy to add a pause mechanism.

    Adds a `set_pause` entrypoint. Checks that contract.data.paused is
    `False` before accepting transfers and operator updates.

    Needs the `Administrable` mixin in order to work.
    """

    def __init__(self, policy=None):
        if policy is None:
            self.policy = OwnerOrOperatorTransfer()
        else:
            self.policy = policy

    def init_policy(self, contract):
        self.policy.init_policy(contract)
        self.name = "pauseable-" + self.policy.name
        self.supports_transfer = self.policy.supports_transfer
        self.supports_operator = self.policy.supports_operator
        contract.update_initial_storage(paused=False)

        # Add a set_pause entrypoint
        def set_pause(self, params):
            sp.set_type(params, sp.TBool)
            self.onlyAdministrator()
            self.data.paused = params

        contract.set_pause = sp.entry_point(set_pause)

    def check_tx_transfer_permissions(self, contract, from_, to_, token_id):
        sp.verify(~contract.data.paused, message=sp.pair("FA2_TX_DENIED", "FA2_PAUSED"))
        self.policy.check_tx_transfer_permissions(contract, from_, to_, token_id)

    def check_operator_add_permissions(self, contract, operator_param):
        sp.verify(
            ~contract.data.paused,
            message=sp.pair("FA2_OPERATORS_UNSUPPORTED", "FA2_PAUSED"),
        )
        self.policy.check_operator_add_permissions(contract, operator_param)

    def check_operator_delete_permissions(self, contract, operator_param):
        sp.verify(
            ~contract.data.paused,
            message=sp.pair("FA2_OPERATORS_UNSUPPORTED", "FA2_PAUSED"),
        )
        self.policy.check_operator_delete_permissions(contract, operator_param)

    def is_operator(self, contract, operator_param):
        return self.policy.is_operator(contract, operator_param)


# TODO: test blacklist transfer!

class BlacklistTransfer:
    """(Transfer Policy) Decorate any policy to add a blacklist mechanism.

    Optionally adds a `set_blacklist` entrypoint. Checks that a to/from
    address is not blacklisted before doing a transfer.

    Needs the `Administrable` mixin in order to work if ep is generated.
    """

    def __init__(self, blacklist_address, policy = None, set_blacklist_ep: bool = False):
        if policy is None:
            self.policy = OwnerOrOperatorTransfer()
        else:
            self.policy = policy
        self.blacklist_address = blacklist_address
        self.set_blacklist_ep = set_blacklist_ep

    def init_policy(self, contract):
        self.policy.init_policy(contract)
        self.name = "blacklist-" + self.policy.name
        self.supports_transfer = self.policy.supports_transfer
        self.supports_operator = self.policy.supports_operator
        contract.update_initial_storage(blacklist=sp.set_type_expr(self.blacklist_address, sp.TAddress))

        # Optionally, add a set_blacklist entrypoint
        if self.set_blacklist_ep:
            def set_blacklist(self, params):
                sp.set_type(params, sp.TAddress)
                self.onlyAdministrator()
                self.data.blacklist = params

            contract.set_blacklist = sp.entry_point(set_blacklist)

    # TODO: this isn't really optimal: calls view for every tx in the transfer. optimise!
    # + maybe add a check_tx_transfer_permissions_batch or so?
    def check_tx_transfer_permissions(self, contract, from_, to_, token_id):
        # Call view to check blacklist. Fails if blacklisted.
        sp.compute(sp.view("check_blacklisted", contract.data.blacklist,
            sp.set_type_expr(sp.set([from_, to_]), sp.TSet(sp.TAddress)),
            t = sp.TUnit).open_some())
        sp.trace("Checked blacklist!")
        self.policy.check_tx_transfer_permissions(contract, from_, to_, token_id)

    def check_operator_add_permissions(self, contract, operator_param):
        # Blacklisted addresses can set operators if they want
        self.policy.check_operator_add_permissions(contract, operator_param)

    def check_operator_delete_permissions(self, contract, operator_param):
        # Blacklisted addresses can set operators if they want
        self.policy.check_operator_delete_permissions(contract, operator_param)

    def is_operator(self, contract, operator_param):
        return self.policy.is_operator(contract, operator_param)


##########
# Common #
##########


class Common(sp.Contract):
    """Common logic between Fa2Nft, Fa2Fungible and Fa2SingleAsset."""

    def __init__(self, name, description, policy=None, metadata_base=None, token_metadata={}):
        self.add_flag("exceptions", "default-line")
        self.add_flag("erase-comments")

        if policy is None:
            self.policy = OwnerOrOperatorTransfer()
        else:
            self.policy = policy
        self.update_initial_storage(
            token_metadata=sp.big_map(
                token_metadata,
                tkey=sp.TNat,
                tvalue=sp.TRecord(
                    token_id=sp.TNat, token_info=sp.TMap(sp.TString, sp.TBytes)
                ).layout(("token_id", "token_info")),
            )
        )
        self.policy.init_policy(self)
        self.generate_contract_metadata(name, description, "metadata_base", metadata_base)

    def is_defined(self, token_id):
        return self.data.token_metadata.contains(token_id)

    def generate_contract_metadata(self, name, description, filename, metadata_base=None):
        """Generate a metadata json file with all the contract's offchain views
        and standard TZIP-126 and TZIP-016 key/values."""
        if metadata_base is None:
            metadata_base = {
                "name": name,
                "version": "1.0.0",
                "description": (
                    description + "\n\nBased on the SmartPy FA2 implementation."
                ),
                "interfaces": ["TZIP-012", "TZIP-016"],
                "authors": [
                    "852Kerfunkle <https://github.com/852Kerfunkle>",
                    "SmartPy <https://smartpy.io/#contact>"
                ],
                "homepage": "https://www.tz1and.com",
                "source": {
                    "tools": ["SmartPy"],
                    "location": "https://github.com/tz1and",
                },
                "license": { "name": "MIT" },
                "permissions": {"receiver": "owner-no-hook", "sender": "owner-no-hook"},
            }
        offchain_views = []
        for f in dir(self):
            attr = getattr(self, f)
            if isinstance(attr, sp.OnOffchainView):
                # Change: include onchain views as tip 16 offchain views
                offchain_views.append(attr)
        metadata_base["views"] = offchain_views
        metadata_base["permissions"]["operator"] = self.policy.name
        self.init_metadata(filename, metadata_base)

    def balance_of_batch(self, requests):
        """Mapping of balances."""
        sp.set_type(requests, sp.TList(t_balance_of_request))

        def f_process_request(req):
            sp.result(
                sp.record(
                    request=req,
                    balance=self.balance_(req.owner, req.token_id),
                )
            )

        return requests.map(f_process_request)

    # Entry points

    @sp.entry_point
    def update_operators(self, batch):
        """Accept a list of variants to add or remove operators who can perform
        transfers on behalf of the owner."""
        sp.set_type(batch, t_update_operators_params)
        if self.policy.supports_operator:
            with sp.for_("action", batch) as action:
                with action.match_cases() as arg:
                    with arg.match("add_operator") as operator:
                        self.policy.check_operator_add_permissions(self, operator)
                        self.data.operators[operator] = sp.unit
                    with arg.match("remove_operator") as operator:
                        self.policy.check_operator_delete_permissions(self, operator)
                        del self.data.operators[operator]
        else:
            sp.failwith("FA2_OPERATORS_UNSUPPORTED")

    @sp.entry_point
    def balance_of(self, params):
        """Send the balance of multiple account / token pairs to a callback
        address.

        `balance_of_batch` must be defined in the child class.
        """
        sp.set_type(params, t_balance_of_params)
        sp.transfer(
            self.balance_of_batch(params.requests), sp.mutez(0), params.callback
        )

    @sp.entry_point
    def transfer(self, batch):
        """Accept a list of transfer operations between a source and multiple
        destinations.

        `transfer_tx_` must be defined in the child class.
        """
        sp.set_type(batch, t_transfer_params)
        if self.policy.supports_transfer:
            with sp.for_("transfer", batch) as transfer:
                with sp.for_("tx", transfer.txs) as tx:
                    # The ordering of sp.verify is important: 1) token_undefined, 2) transfer permission 3) balance
                    sp.verify(self.is_defined(tx.token_id), "FA2_TOKEN_UNDEFINED")
                    self.policy.check_tx_transfer_permissions(
                        self, transfer.from_, tx.to_, tx.token_id
                    )
                    with sp.if_(tx.amount > 0):
                        self.transfer_tx_(transfer.from_, tx)
        else:
            sp.failwith("FA2_TX_DENIED")

    # Onchain views

    @sp.offchain_view(pure=True)
    def all_tokens(self):
        """OffchainView: Return the list of all the token IDs known to the contract."""
        sp.result(sp.range(0, self.data.last_token_id))

    @sp.onchain_view(pure=True)
    def is_operator(self, params):
        """Return whether `operator` is allowed to transfer `token_id` tokens
        owned by `owner`."""
        sp.set_type(params, t_operator_permission)
        sp.result(self.policy.is_operator(self, params))

    @sp.onchain_view(pure=True)
    def get_balance(self, params):
        """Return the balance of an address for the specified `token_id`."""
        sp.set_type(
            params,
            sp.TRecord(owner=sp.TAddress, token_id=sp.TNat).layout(
                ("owner", "token_id")
            ),
        )
        sp.result(self.balance_(params.owner, params.token_id))

    @sp.onchain_view(pure=True)
    def total_supply(self, params):
        """Return the total number of tokens for the given `token_id`."""
        sp.result(sp.set_type_expr(self.supply_(params.token_id), sp.TNat))


################
# Base classes #
################


class Fa2Nft(Common):
    """Base class for a FA2 NFT contract.

    Respects the FA2 standard.
    """

    ledger_type = "NFT"

    def __init__(
        self, metadata, name="FA2", description="A NFT FA2 implementation.",
        token_metadata=[], ledger={}, policy=None, metadata_base=None, has_royalties=False
    ):
        metadata = sp.set_type_expr(metadata, sp.TBigMap(sp.TString, sp.TBytes))
        self.has_royalties = has_royalties
        ledger, token_extra, token_metadata = self.initial_mint(token_metadata, ledger, has_royalties)
        self.init(
            ledger=sp.big_map(ledger, tkey=sp.TNat, tvalue=sp.TAddress),
            metadata=metadata,
            last_token_id=sp.nat(len(token_metadata))
        )
        if has_royalties:
            self.update_initial_storage(
                token_extra=sp.big_map(token_extra, tkey=sp.TNat, tvalue=t_token_extra_royalties)
            )
            self.token_extra_default = sp.record(
                royalty_info={}
            )
        Common.__init__(
            self,
            name,
            description,
            policy=policy,
            metadata_base=metadata_base,
            token_metadata=token_metadata,
        )

    def initial_mint(self, token_metadata=[], ledger={}, has_royalties=False):
        """Perform a mint before the origination.

        Returns `ledger`, `token_extra` and `token_metadata`.
        """
        token_metadata_dict = {}
        token_extra_dict = {}
        for token_id, metadata in enumerate(token_metadata):
            token_metadata_dict[token_id] = sp.record(
                token_id=token_id, token_info=metadata
            )
            token_extra_dict[token_id] = sp.record(
                royalty_info={}
            )
        for token_id, address in ledger.items():
            if token_id not in token_metadata_dict:
                raise Exception(
                    "Ledger contains token_id with no corresponding metadata"
                )
        return (ledger, token_extra_dict, token_metadata_dict)

    def balance_(self, owner, token_id):
        return sp.eif(
            self.data.ledger.get(token_id, message = "FA2_TOKEN_UNDEFINED") == owner,
            sp.nat(1), sp.nat(0))

    def supply_(self, token_id):
        sp.verify(self.is_defined(token_id), "FA2_TOKEN_UNDEFINED")
        return sp.nat(1)

    def transfer_tx_(self, from_, tx):
        sp.verify(
            (tx.amount == 1) & (self.data.ledger[tx.token_id] == from_),
            message="FA2_INSUFFICIENT_BALANCE",
        )
        # Do the transfer
        self.data.ledger[tx.token_id] = tx.to_

    @sp.onchain_view(pure=True)
    def get_owner(self, token_id):
        """Non-standard onchain view allowing direct retrieval of
        owner for Nft type ledgers.
        
        Return the owner for the given `token_id`."""
        sp.result(sp.set_type_expr(
            self.data.ledger.get(token_id, message = "FA2_TOKEN_UNDEFINED"),
            sp.TAddress))


# TODO: test allow_mint_existing=False
class Fa2Fungible(Common):
    """Base class for a FA2 fungible contract.

    Respects the FA2 standard.
    """

    ledger_type = "Fungible"

    def __init__(
        self, metadata, name="FA2", description="A Fungible FA2 implementation.",
        token_metadata=[], ledger={}, policy=None, metadata_base=None, has_royalties=False, allow_mint_existing=True
    ):
        metadata = sp.set_type_expr(metadata, sp.TBigMap(sp.TString, sp.TBytes))
        self.has_royalties = has_royalties
        self.allow_mint_existing = allow_mint_existing
        ledger, token_extra, token_metadata = self.initial_mint(token_metadata, ledger, has_royalties)
        self.init(
            ledger=sp.big_map(
                ledger, tkey=sp.TPair(sp.TAddress, sp.TNat), tvalue=sp.TNat
            ),
            metadata=metadata,
            last_token_id=sp.nat(len(token_metadata))
        )
        if has_royalties:
            self.update_initial_storage(
                token_extra=sp.big_map(token_extra, tkey=sp.TNat, tvalue=t_token_extra_royalties_supply)
            )
            self.token_extra_default = sp.record(
                supply=sp.nat(0),
                royalty_info={}
            )
        else:
            self.update_initial_storage(
                token_extra=sp.big_map(token_extra, tkey=sp.TNat, tvalue=t_token_extra_supply)
            )
            self.token_extra_default = sp.record(supply=sp.nat(0))
        Common.__init__(
            self,
            name,
            description,
            policy=policy,
            metadata_base=metadata_base,
            token_metadata=token_metadata,
        )

    def initial_mint(self, token_metadata=[], ledger={}, has_royalties=False):
        """Perform a mint before the origination.

        Returns `ledger`, `token_extra` and `token_metadata`.
        """
        token_metadata_dict = {}
        token_extra_dict = {}
        for token_id, metadata in enumerate(token_metadata):
            metadata = sp.record(token_id=token_id, token_info=metadata)
            token_metadata_dict[token_id] = metadata
            # Token that are in token_metadata and not in ledger exist with supply = 0
            if has_royalties:
                token_extra_dict[token_id] = sp.record(
                    supply=sp.nat(0),
                    royalty_info={}
                )
            else:
                token_extra_dict[token_id] = sp.record(supply=sp.nat(0))
        for (address, token_id), amount in ledger.items():
            if token_id not in token_metadata_dict:
                raise Exception("Ledger contains a token_id with no metadata")
            token_extra_dict[token_id].supply += amount
        return (ledger, token_extra_dict, token_metadata_dict)

    def balance_(self, owner, token_id):
        sp.verify(self.is_defined(token_id), "FA2_TOKEN_UNDEFINED")
        return self.data.ledger.get((owner, token_id), sp.nat(0))

    def supply_(self, token_id):
        return self.data.token_extra.get(token_id, message = "FA2_TOKEN_UNDEFINED").supply

    def transfer_tx_(self, from_, tx):
        from_ = sp.compute((from_, tx.token_id))
        from_balance = sp.compute(sp.as_nat(
            self.data.ledger.get(from_, 0) - tx.amount,
            message="FA2_INSUFFICIENT_BALANCE",
        ))
        with sp.if_(from_balance == 0):
            del self.data.ledger[from_]
        with sp.else_():
            self.data.ledger[from_] = from_balance

        # Do the transfer
        to_ = sp.compute((tx.to_, tx.token_id))
        self.data.ledger[to_] = self.data.ledger.get(to_, 0) + tx.amount


class Fa2SingleAsset(Common):
    """Base class for a FA2 single asset contract.

    Respects the FA2 standard.
    """

    ledger_type = "SingleAsset"

    def __init__(
        self, metadata, name="FA2", description="A Single Asset FA2 implementation.",
        token_metadata=[], ledger={}, policy=None, metadata_base=None
    ):
        metadata = sp.set_type_expr(metadata, sp.TBigMap(sp.TString, sp.TBytes))
        ledger, supply, token_metadata = self.initial_mint(token_metadata, ledger)
        self.init(
            ledger=sp.big_map(
                ledger, tkey=sp.TAddress, tvalue=sp.TNat
            ),
            metadata=metadata,
            last_token_id=sp.nat(len(token_metadata)),
            supply=supply,
        )
        Common.__init__(
            self,
            name,
            description,
            policy=policy,
            metadata_base=metadata_base,
            token_metadata=token_metadata,
        )

    def initial_mint(self, token_metadata=[], ledger={}):
        """Perform a mint before the origination.

        Returns `ledger`, `supply` and `token_metadata`.
        """
        if len(token_metadata) > 1:
            raise Exception("Single asset can only contain one token")
        token_metadata_dict = {}
        supply = sp.nat(0)
        for token_id, metadata in enumerate(token_metadata):
            metadata = sp.record(token_id=token_id, token_info=metadata)
            token_metadata_dict[token_id] = metadata
        for address, amount in ledger.items():
            if token_id not in token_metadata_dict:
                raise Exception("Ledger contains a token_id with no metadata")
            supply += amount
        return (ledger, supply, token_metadata_dict)

    # Overload is_defined to make sure token_id is always 0
    def is_defined(self, token_id):
        return token_id == 0

    def balance_(self, owner, token_id):
        sp.verify(self.is_defined(token_id), "FA2_TOKEN_UNDEFINED")
        return self.data.ledger.get(owner, sp.nat(0))

    def transfer_tx_(self, from_, tx):
        from_balance = sp.compute(sp.as_nat(
            self.data.ledger.get(from_, sp.nat(0)) - tx.amount,
            message="FA2_INSUFFICIENT_BALANCE",
        ))
        with sp.if_(from_balance == 0):
            del self.data.ledger[from_]
        with sp.else_():
            self.data.ledger[from_] = from_balance

        # Do the transfer
        to_ = tx.to_
        self.data.ledger[to_] = self.data.ledger.get(to_, sp.nat(0)) + tx.amount

    def supply_(self, token_id):
        sp.verify(self.is_defined(token_id), "FA2_TOKEN_UNDEFINED")
        return self.data.supply


##########
# Mixins #
##########


class ChangeMetadata:
    """(Mixin) Provide an entrypoint to change contract metadata.

    Requires the `Administrable` mixin.
    """

    @sp.entry_point
    def set_metadata(self, metadata):
        """(Admin only) Set the contract metadata."""
        sp.set_type(metadata, sp.TBigMap(sp.TString, sp.TBytes))
        self.onlyAdministrator()
        self.data.metadata = metadata


class WithdrawMutez:
    """(Mixin) Provide an entrypoint to withdraw mutez that are in the
    contract's balance.

    Requires the `Administrable` mixin.
    """

    @sp.entry_point
    def withdraw_mutez(self, destination, amount):
        """(Admin only) Transfer `amount` mutez to `destination`."""
        sp.set_type(destination, sp.TAddress)
        sp.set_type(amount, sp.TMutez)
        self.onlyAdministrator()
        sp.send(destination, amount)


class OffchainviewTokenMetadata:
    """(Mixin) If present indexers use it to retrieve the token's metadata.

    Warning: If someone can change the contract's metadata he can change how
    indexers see every token metadata.
    """

    @sp.offchain_view(pure=True)
    def token_metadata(self, token_id):
        """Returns the token-metadata URI for the given token."""
        sp.set_type(token_id, sp.TNat)
        sp.result(self.data.token_metadata[token_id])


class OffchainviewBalanceOf:
    """(Mixin) Non-standard offchain view equivalent to `balance_of`.

    Before onchain views were introduced in Michelson, the standard way
    of getting value from a contract was through a callback. Now that
    views are here we can create a view for the old style one.
    """

    @sp.offchain_view(pure=True)
    def get_balance_of(self, requests):
        """Onchain view equivalent to the `balance_of` entrypoint."""
        sp.set_type(requests, sp.TList(t_balance_of_request))
        sp.result(
            sp.set_type_expr(
                self.balance_of_batch(requests), sp.TList(t_balance_of_response)
            )
        )


#################
# Mixins - Mint #
#################


class MintNft:
    """(Mixin) Non-standard `mint` entrypoint for FA2Nft with incrementing id.

    Requires the `Administrable` mixin.
    """

    @sp.entry_point
    def mint(self, batch):
        """Admin can mint new or existing tokens."""
        if self.has_royalties:
            sp.set_type(batch, t_mint_nft_royalties_batch)
        else:
            sp.set_type(batch, t_mint_nft_batch)
        self.onlyAdministrator()
        with sp.for_("action", batch) as action:
            token_id = sp.compute(self.data.last_token_id)
            metadata = sp.record(token_id=token_id, token_info=action.metadata)
            self.data.token_metadata[token_id] = metadata
            self.data.ledger[token_id] = action.to_
            if self.has_royalties:
                self.data.token_extra[token_id] = sp.record(royalty_info=action.royalties)
            self.data.last_token_id += 1


class MintFungible:
    """(Mixin) Non-standard `mint` entrypoint for FA2Fungible with incrementing
    id.

    Requires the `Administrable` mixin.
    """

    @sp.entry_point
    def mint(self, batch):
        """Admin can mint tokens."""
        if self.has_royalties:
            sp.set_type(batch, t_mint_fungible_royalties_batch)
        else:
            sp.set_type(batch, t_mint_fungible_batch)
        self.onlyAdministrator()
        with sp.for_("action", batch) as action:
            with action.token.match_cases() as arg:
                with arg.match("new") as new:
                    token_id = sp.compute(self.data.last_token_id)
                    self.data.token_metadata[token_id] = sp.record(
                        token_id=token_id, token_info=new.metadata
                    )
                    if self.has_royalties:
                        self.data.token_extra[token_id] = sp.record(
                            supply=action.amount,
                            royalty_info=new.royalties
                        )
                    else:
                        self.data.token_extra[token_id] = sp.record(
                            supply=action.amount
                        )
                    self.data.ledger[(action.to_, token_id)] = action.amount
                    self.data.last_token_id += 1
                with arg.match("existing") as token_id:
                    if self.allow_mint_existing:
                        sp.verify(self.is_defined(token_id), "FA2_TOKEN_UNDEFINED")
                        self.data.token_extra[token_id].supply += action.amount
                        from_ = sp.compute((action.to_, token_id))
                        self.data.ledger[from_] = (
                            self.data.ledger.get(from_, sp.nat(0)) + action.amount
                        )
                    else:
                        sp.failwith("FA2_TX_DENIED")


class MintSingleAsset:
    """(Mixin) Non-standard `mint` entrypoint for FA2SingleAsset assuring only
    one token can be minted.

    Requires the `Administrable` mixin.
    """

    @sp.entry_point
    def mint(self, batch):
        """Admin can mint tokens."""
        sp.set_type(batch, t_mint_fungible_batch)
        self.onlyAdministrator()
        with sp.for_("action", batch) as action:
            with action.token.match_cases() as arg:
                with arg.match("new") as new:
                    token_id = sp.nat(0)
                    sp.verify(~ self.data.token_metadata.contains(token_id), "FA2_TOKEN_DEFINED") # TODO: change this message?
                    self.data.token_metadata[token_id] = sp.record(
                        token_id=token_id, token_info=new.metadata
                    )
                    self.data.supply = action.amount
                    self.data.ledger[action.to_] = action.amount
                    self.data.last_token_id += 1
                with arg.match("existing") as token_id:
                    sp.verify(self.is_defined(token_id), "FA2_TOKEN_UNDEFINED")
                    self.data.supply += action.amount
                    from_ = action.to_
                    self.data.ledger[from_] = (
                        self.data.ledger.get(from_, sp.nat(0)) + action.amount
                    )


#################
# Mixins - Burn #
#################


class BurnNft:
    """(Mixin) Non-standard `burn` entrypoint for FA2Nft that uses the transfer
    policy permission."""

    @sp.entry_point
    def burn(self, batch):
        """Users can burn tokens if they have the transfer policy permission.

        Burning an nft destroys its metadata.
        """
        sp.set_type(batch, t_burn_batch)
        sp.verify(self.policy.supports_transfer, "FA2_TX_DENIED")
        with sp.for_("action", batch) as action:
            sp.verify(self.is_defined(action.token_id), "FA2_TOKEN_UNDEFINED")
            self.policy.check_tx_transfer_permissions(
                self, action.from_, action.from_, action.token_id
            )
            with sp.if_(action.amount > 0):
                sp.verify(
                    (action.amount == sp.nat(1))
                    & (self.data.ledger[action.token_id] == action.from_),
                    message="FA2_INSUFFICIENT_BALANCE",
                )
                # Burn the token
                del self.data.ledger[action.token_id]
                del self.data.token_metadata[action.token_id]
                if self.has_royalties:
                    del self.data.token_extra[action.token_id]


# TODO: test ledger, metadata, extra removal.
class BurnFungible:
    """(Mixin) Non-standard `burn` entrypoint for FA2Fungible that uses the
    transfer policy permission."""

    @sp.entry_point
    def burn(self, batch):
        """Users can burn tokens if they have the transfer policy
        permission."""
        sp.set_type(batch, t_burn_batch)
        sp.verify(self.policy.supports_transfer, "FA2_TX_DENIED")
        with sp.for_("action", batch) as action:
            sp.verify(self.is_defined(action.token_id), "FA2_TOKEN_UNDEFINED")
            self.policy.check_tx_transfer_permissions(
                self, action.from_, action.from_, action.token_id
            )
            from_ = sp.compute((action.from_, action.token_id))
            # Burn from.
            from_balance = sp.compute(sp.as_nat(
                self.data.ledger.get(from_, sp.nat(0)) - action.amount,
                message="FA2_INSUFFICIENT_BALANCE",
            ))
            with sp.if_(from_balance == 0):
                del self.data.ledger[from_]
            with sp.else_():
                self.data.ledger[from_] = from_balance

            # Decrease supply or delete of it becomes 0.
            extra = sp.local("extra", self.data.token_extra.get(action.token_id, self.token_extra_default))
            supply = sp.compute(sp.is_nat(extra.value.supply - action.amount))
            with supply.match_cases() as arg:
                with arg.match("Some") as nat_supply:
                    if self.allow_mint_existing:
                        extra.value.supply = nat_supply
                        self.data.token_extra[action.token_id] = extra.value
                    # NOTE: if existing tokens can't be minted again, delete on 0.
                    else:
                        with sp.if_(nat_supply == 0):
                            del self.data.token_extra[action.token_id]
                            del self.data.token_metadata[action.token_id]
                        with sp.else_():
                            extra.value.supply = nat_supply
                            self.data.token_extra[action.token_id] = extra.value
                with arg.match("None"):
                    # NOTE: this is a failure case, but we give up instead
                    # of allowing a catstrophic failiure.
                    extra.value.supply = sp.nat(0)
                    self.data.token_extra[action.token_id] = extra.value


class BurnSingleAsset:
    """(Mixin) Non-standard `burn` entrypoint for FA2SingleAsset that uses the
    transfer policy permission."""

    @sp.entry_point
    def burn(self, batch):
        """Users can burn tokens if they have the transfer policy
        permission."""
        sp.set_type(batch, t_burn_batch)
        sp.verify(self.policy.supports_transfer, "FA2_TX_DENIED")
        with sp.for_("action", batch) as action:
            sp.verify(self.is_defined(action.token_id), "FA2_TOKEN_UNDEFINED")
            self.policy.check_tx_transfer_permissions(
                self, action.from_, action.from_, action.token_id
            )
            # Burn the tokens
            from_balance = sp.compute(sp.as_nat(
                self.data.ledger.get(action.from_, sp.nat(0)) - action.amount,
                message="FA2_INSUFFICIENT_BALANCE",
            ))
            with sp.if_(from_balance == 0):
                del self.data.ledger[action.from_]
            with sp.else_():
                self.data.ledger[action.from_] = from_balance

            # Decrease supply.
            supply = sp.compute(sp.is_nat(self.data.supply - action.amount))
            with supply.match_cases() as arg:
                with arg.match("Some") as nat_supply:
                    self.data.supply = nat_supply
                with arg.match("None"):
                    self.data.supply = sp.nat(0)


class Royalties:
    """(Mixin) Non-standard royalties for nft and fungible.
    Requires has_royalties=True on base.
    
    I admit, not very elegant, but I want to save that bigmap."""

    def __init__(self):
        if self.ledger_type == "SingleAsset":
            raise Exception("Royalties not supported on SingleAsset")
        if self.has_royalties != True:
            raise Exception("Royalties not enabled on base")

    @sp.onchain_view(pure=True)
    def get_royalties(self, token_id):
        """Returns the token royalties information, including total shares."""
        sp.set_type(token_id, sp.TNat)

        with sp.set_result_type(t_royalties_interop):
            sp.result(sp.record(
                total=1000,
                shares=self.data.token_extra.get(token_id, self.token_extra_default).royalty_info))


class OnchainviewCountTokens:
    """(Mixin) Adds count_tokens onchain view."""
    
    @sp.onchain_view(pure=True)
    def count_tokens(self):
        """Returns the number of tokens in the FA2 contract."""
        sp.result(self.data.last_token_id)


#########
# Utils #
#########

# Getting royalties
def getRoyalties(fa2, token_id, message = None):
    return sp.view("get_royalties", fa2,
        sp.set_type_expr(token_id, sp.TNat),
        t = t_royalties_interop).open_some(message)

# Get owner
def fa2_nft_get_owner(fa2, token_id):
    return sp.view("get_owner", fa2,
        sp.set_type_expr(
            token_id,
            sp.TNat),
        t = sp.TAddress).open_some()

# Validating royalties
def validateRoyalties(royalties, max_royalties, max_contributors):
    """Inline function to validate royalties."""
    sp.set_type(royalties, t_royalties_shares)
    sp.set_type(max_royalties, sp.TNat)
    sp.set_type(max_contributors, sp.TNat)
    
    # Add splits to make sure shares don't exceed the maximum.
    total_absolute_shares = sp.local("total_absolute", sp.nat(0))
    with sp.for_("share", royalties.values()) as share:
        total_absolute_shares.value += share

    # Make sure absolute royalties and splits are in valid range.
    sp.verify((total_absolute_shares.value <= max_royalties)
        & (sp.len(royalties) <= max_contributors), message="FA2_INV_ROYALTIES")

# Minting with royalties
def fa2_nft_royalties_mint(batch, contract):
    sp.set_type(batch, t_mint_nft_royalties_batch)
    sp.set_type(contract, sp.TAddress)
    c = sp.contract(
        t_mint_nft_royalties_batch,
        contract,
        entry_point='mint').open_some()
    sp.transfer(batch, sp.mutez(0), c)

def fa2_fungible_royalties_mint(batch, contract):
    sp.set_type(batch, t_mint_fungible_royalties_batch)
    sp.set_type(contract, sp.TAddress)
    c = sp.contract(
        t_mint_fungible_royalties_batch,
        contract,
        entry_point='mint').open_some()
    sp.transfer(batch, sp.mutez(0), c)