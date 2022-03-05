#
# ## Introduction
#
# See the FA2 standard definition:
# <https://gitlab.com/tzip/tzip/-/blob/master/proposals/tzip-12/>
#
# See more examples/documentation at
# <https://gitlab.com/smondet/fa2-smartpy/> and
# <https://assets.tqtezos.com/docs/token-contracts/fa2/1-fa2-smartpy/>.
#
# TODO: bring up to date with latest FA2: https://gitlab.com/SmartPy/smartpy/-/issues/28
# TODO: test ledger, metadata, extra removal.
import smartpy as sp

pausable_contract = sp.io.import_script_from_url("file:contracts/Pausable.py")
fa2_royalties = sp.io.import_script_from_url("file:contracts/FA2_Royalties.py")

#
# ## Meta-Programming Configuration
#
# The `FA2_config` class holds the meta-programming configuration.
#
class FA2_config:
    def __init__(self,
                 single_asset                       = False,
                 non_fungible                       = False,
                 add_mutez_transfer                 = False,
                 store_total_supply                 = True,
                 lazy_entry_points                  = False,
                 use_token_metadata_offchain_view   = False,
                 allow_burn_tokens                  = False,
                 operator_burn                      = False,
                 add_distribute                     = False,
                 royalties                          = False,
                 metadata_name                      = "FA2",
                 metadata_description               = "An FA2 implementation.",
                 ):

        self.metadata_name = metadata_name
        self.metadata_description = metadata_description
        # Name and description

        self.allow_burn_tokens = allow_burn_tokens
        # Add an entry point that allows to burn tokens.

        self.operator_burn = operator_burn
        # If operators are allowed to burn tokens.

        self.add_distribute = add_distribute
        # Add an entry point for the administrator to transfer mint tokens
        # to a list of recipients

        # TODO: disallow royalties in some cases.
        self.royalties = royalties
        # Add token royalties mixin

        self.use_token_metadata_offchain_view = use_token_metadata_offchain_view
        # Include offchain view for accessing the token metadata (requires TZIP-016 contract metadata)

        self.single_asset = single_asset
        # This makes the contract save some gas and storage by
        # working only for the token-id `0`.

        self.non_fungible = non_fungible
        # Enforce the non-fungibility of the tokens, i.e. the fact
        # that total supply has to be 1.

        self.store_total_supply = store_total_supply
        # Whether to store the total-supply for each token (next to
        # the token-metadata).

        self.add_mutez_transfer = add_mutez_transfer
        # Add an entry point for the administrator to transfer tez potentially
        # in the contract's balance.

        self.lazy_entry_points = lazy_entry_points
        #
        # Those are “compilation” options of SmartPy into Michelson.
        #

        # add_distribute can only be used with single_asset
        if self.add_distribute and not (self.single_asset and not self.non_fungible):
            raise Exception('add_distribute can only be used with single_asset && !non_fungible')

        # royalties can't be used with single asset
        if self.royalties and self.single_asset:
            raise Exception('royalties can not be used with single_asset')

        name = "FA2"
        if single_asset:
            name += "-single_asset"
        if non_fungible:
            name += "-nft"
        if add_mutez_transfer:
            name += "-mutez"
        if not store_total_supply:
            name += "-no_totsup"
        if lazy_entry_points:
            name += "-lep"
        if allow_burn_tokens:
            name += "-burn"
            if operator_burn:
                name += "-op_burn"
        if add_distribute:
            name += "-distribute"
        if royalties:
            name += "-royalties"
        self.name = name

## ## Auxiliary Classes and Values
##
## The definitions below implement SmartML-types and functions for various
## important types.
##
token_id_type = sp.TNat

class Error_message:
    def __init__(self, config):
        self.config = config
        self.prefix = "FA2_"
    def make(self, s): return (self.prefix + s)
    def token_undefined(self):       return self.make("TOKEN_UNDEFINED")
    def insufficient_balance(self):  return self.make("INSUFFICIENT_BALANCE")
    def not_operator(self):          return self.make("NOT_OPERATOR")
    def adhoc_operator_limit(self):  return self.make("ADHOC_OPERATOR_LIMIT")
    def not_owner(self):             return self.make("NOT_OWNER")
    def not_admin(self):             return self.make("NOT_ADMIN")
    def paused(self):                return self.make("PAUSED")

## The current type for a batched transfer in the specification is as
## follows:
##
## ```ocaml
## type transfer = {
##   from_ : address;
##   txs: {
##     to_ : address;
##     token_id : token_id;
##     amount : nat;
##   } list
## } list
## ```
##
## This class provides helpers to create and force the type of such elements.
## It uses the `FA2_config` to decide whether to set the right-comb layouts.
class Batch_transfer:
    def __init__(self, config):
        self.config = config
    def get_transfer_type(self):
        tx_type = sp.TRecord(to_ = sp.TAddress,
                             token_id = token_id_type,
                             amount = sp.TNat
        ).layout(("to_", ("token_id", "amount")))
        transfer_type = sp.TRecord(from_ = sp.TAddress,
                                   txs = sp.TList(tx_type)).layout(
                                       ("from_", "txs"))
        return transfer_type
    def get_type(self):
        return sp.TList(self.get_transfer_type())
    def item(self, from_, txs):
        v = sp.record(from_ = from_, txs = txs)
        return sp.set_type_expr(v, self.get_transfer_type())
##
## `Operator_param` defines type types for the `%update_operators` entry-point.
class Operator_param:
    def __init__(self, config):
        self.config = config
    def get_type(self):
        return sp.TRecord(
            owner = sp.TAddress,
            operator = sp.TAddress,
            token_id = token_id_type
        ).layout(("owner", ("operator", "token_id")))
    def make(self, owner, operator, token_id):
        r = sp.record(owner = owner,
                      operator = operator,
                      token_id = token_id)
        return sp.set_type_expr(r, self.get_type())

## The class `Ledger_key` defines the key type for the main ledger (big-)map:
##
## - In *“Babylon mode”* we also have to call `sp.pack`.
## - In *“single-asset mode”* we can just use the user's address.
class Ledger_key:
    def __init__(self, config):
        self.config = config
    def get_type(self):
        if self.config.single_asset:
            return sp.TAddress
        else:
            return sp.TPair(sp.TAddress, sp.TNat)
    def make(self, user, token):
        user = sp.set_type_expr(user, sp.TAddress)
        token = sp.set_type_expr(token, token_id_type)
        if self.config.single_asset:
            result = sp.set_type_expr(user, self.get_type())
        else:
            result = sp.set_type_expr(sp.pair(user, token), self.get_type())
        return result

## The link between operators and the addresses they operate is kept
## in a *lazy set* of `(owner × operator × token-id)` values.
##
## A lazy set is a big-map whose keys are the elements of the set and
## values are all `Unit`.
class Operator_set:
    def __init__(self, config):
        self.config = config

    def key_type(self):
        return sp.TRecord(owner = sp.TAddress,
                          operator = sp.TAddress,
                          token_id = token_id_type
                          ).layout(("owner", ("operator", "token_id")))

    def make(self):
        return sp.big_map(tkey = self.key_type(), tvalue = sp.TUnit)

    def make_key(self, owner, operator, token_id):
        metakey = sp.record(owner = owner,
                            operator = operator,
                            token_id = token_id)
        metakey = sp.set_type_expr(metakey, self.key_type())
        return metakey

    def add(self, set, owner, operator, token_id):
        set[self.make_key(owner, operator, token_id)] = sp.unit
    def remove(self, set, owner, operator, token_id):
        del set[self.make_key(owner, operator, token_id)]
    def is_member(self, set, owner, operator, token_id):
        return set.contains(self.make_key(owner, operator, token_id))

##
## `AdhocOperator_param` defines type types for the `%add_adhoc_operators` entry-point.
## Owner is always assumed to be sender.
class AdhocOperator_param:
    def __init__(self, config):
        self.config = config
    def get_type(self):
        return sp.TRecord(
            operator = sp.TAddress,
            token_id = token_id_type
        ).layout(("operator", "token_id"))
    def make(self, operator, token_id):
        r = sp.record(operator = operator, token_id = token_id)
        return sp.set_type_expr(r, self.get_type())

## Adhoc, temporary operators. Cheap and storage efficient.
## They are supposed to apply only to the current operation group.
## They are only valid in the current block level. You may take
## care to clear them after use, but for most uses, it's probably
## not required.
## For long-lasting operators, use standard operators.
##
## You've seen it here first :)
class AdhocOperator_set:
    def __init__(self, config):
        self.config = config

    def key_type(self):
        return sp.TBytes

    def make(self):
        return sp.set(t = self.key_type())

    def make_key(self, owner, operator, token_id):
        metakey = sp.sha3(sp.pack(sp.record(owner = owner,
                            operator = operator,
                            token_id = token_id,
                            level = sp.level)))
        metakey = sp.set_type_expr(metakey, self.key_type())
        return metakey

    def add(self, set, owner, operator, token_id):
        set.add(self.make_key(owner, operator, token_id))

    def is_member(self, set, owner, operator, token_id):
        return set.contains(self.make_key(owner, operator, token_id))

class Balance_of:
    def request_type():
        return sp.TRecord(
            owner = sp.TAddress,
            token_id = token_id_type).layout(("owner", "token_id"))
    def response_type():
        return sp.TList(
            sp.TRecord(
                request = Balance_of.request_type(),
                balance = sp.TNat).layout(("request", "balance")))
    def entry_point_type():
        return sp.TRecord(
            callback = sp.TContract(Balance_of.response_type()),
            requests = sp.TList(Balance_of.request_type())
        ).layout(("requests", "callback"))

class Token_meta_data:
    def __init__(self, config):
        self.config = config

    def get_type(self):
        return sp.TRecord(
            token_id = sp.TNat,
            token_info = sp.TMap(sp.TString, sp.TBytes)
        ).layout(("token_id", "token_info"))

class Token_extra_data:
    def __init__(self, config):
        self.config = config

    def get_type(self):
        if self.config.royalties and self.config.store_total_supply:
            return sp.TRecord(
                total_supply = sp.TNat,
                royalty_info = fa2_royalties.FA2_Royalties.ROYALTIES_TYPE
            ).layout(("total_supply", "royalty_info"))
        elif self.config.royalties:
            return sp.TRecord(
                royalty_info = fa2_royalties.FA2_Royalties.ROYALTIES_TYPE
            )
        else:
            return sp.TRecord(
                total_supply = sp.TNat,
            )

    def get_default(self):
        if self.config.royalties and self.config.store_total_supply:
            return sp.record(
                total_supply = sp.nat(0),
                royalty_info = sp.record(royalties=sp.nat(0), contributors={})
            )
        elif self.config.royalties:
            return sp.record(
                royalty_info = sp.record(royalties=sp.nat(0), contributors={})
            )
        else:
            return sp.record(total_supply = sp.nat(0))

## The set of all tokens is represented by a `nat` if we assume that token-ids
## are consecutive, or by an actual `(set nat)` if not.
##
## - Knowing the set of tokens is useful for throwing accurate error messages.
## - Previous versions of the specification required this set for functional
##   behavior (operators interface had to deal with “all tokens”).
class Token_id_set:
    def __init__(self, config):
        self.config = config
    def empty(self):
        return sp.nat(0)
    def add(self, totalTokens, tokenID):
        sp.verify(totalTokens == tokenID, message = "Token-IDs should be consecutive")
        totalTokens.set(tokenID + 1)
    def contains(self, totalTokens, tokenID):
        return (tokenID < totalTokens)
    def cardinal(self, totalTokens):
        return totalTokens

##
## ## Implementation of the Contract
##
## `mutez_transfer` is an optional entry-point, hence we define it “outside” the
## class:
def mutez_transfer(contract, params):
    sp.verify(sp.sender == contract.data.administrator)
    sp.set_type(params.destination, sp.TAddress)
    sp.set_type(params.amount, sp.TMutez)
    sp.send(params.destination, params.amount)

##
## The `FA2` class builds a contract according to an `FA2_config` and an
## administrator address.
## It is inheriting from `FA2_core` which implements the strict
## standard and a few other classes to add other common features.
##
## - We see the use of
##   [`sp.entry_point`](https://smartpy.io/docs/introduction/entry_points)
##   as a function instead of using annotations in order to allow
##   optional entry points.
## - The storage field `metadata_string` is a placeholder, the build
##   system replaces the field annotation with a specific version-string, such
##   as `"version_20200602_tzip_b916f32"`: the version of FA2-smartpy and
##   the git commit in the TZIP [repository](https://gitlab.com/tzip/tzip) that
##   the contract should obey.
class FA2_core(sp.Contract):
    def __init__(self, config, metadata, **extra_storage):
        self.config = config
        self.error_message = Error_message(self.config)
        self.operator_set = Operator_set(self.config)
        self.operator_param = Operator_param(self.config)
        self.adhoc_operator_set = AdhocOperator_set(self.config)
        self.adhoc_operator_param = AdhocOperator_param(self.config)
        self.token_id_set = Token_id_set(self.config)
        self.ledger_key = Ledger_key(self.config)
        self.token_meta_data = Token_meta_data(self.config)
        self.batch_transfer = Batch_transfer(self.config)
        if self.config.add_mutez_transfer:
            self.transfer_mutez = sp.entry_point(mutez_transfer)
        if self.config.lazy_entry_points:
            self.add_flag("lazy-entry-points")
        self.add_flag("initial-cast")
        self.exception_optimization_level = "default-line"
        self.init(
            ledger = sp.big_map(tkey = self.ledger_key.get_type(), tvalue = sp.TNat),
            token_metadata = sp.big_map(tkey = sp.TNat, tvalue = self.token_meta_data.get_type()),
            operators = self.operator_set.make(),
            adhoc_operators = self.adhoc_operator_set.make(),
            all_tokens = self.token_id_set.empty(),
            metadata = metadata,
            **extra_storage
        )

        if self.config.store_total_supply or self.config.royalties:
            self.token_extra_data = Token_extra_data(self.config)
            self.update_initial_storage(
                token_extra = sp.big_map(tkey = sp.TNat, tvalue = self.token_extra_data.get_type()),
            )

    @sp.entry_point
    def transfer(self, params):
        sp.verify( ~self.isPaused(), message = self.error_message.paused() )
        sp.set_type(params, self.batch_transfer.get_type())
        sp.for transfer in params:
           current_from = transfer.from_
           sp.for tx in transfer.txs:
                # Check token type constraints.
                if self.config.single_asset:
                    sp.verify(tx.token_id == 0, message = "single-asset: token-id <> 0")

                # Check owner and operator.
                sender_verify = (current_from == sp.sender)
                message = self.error_message.not_operator()
                sender_verify |= (self.adhoc_operator_set.is_member(self.data.adhoc_operators, current_from, sp.sender, tx.token_id) |
                    self.operator_set.is_member(self.data.operators, current_from, sp.sender, tx.token_id))
                sp.verify(sender_verify, message = message)

                # Check token exists.
                sp.verify(self.data.token_metadata.contains(tx.token_id),
                    message = self.error_message.token_undefined())

                # Ignore 0 transfers.
                sp.if (tx.amount > 0):
                    from_user = sp.compute(self.ledger_key.make(current_from, tx.token_id))
                    from_user_balance = sp.compute(self.data.ledger[from_user])

                    # Make sure from_user has sufficient balance.
                    sp.verify(from_user_balance >= tx.amount,
                        message = self.error_message.insufficient_balance())
                    
                    # Update from_user balance, or remove from ledger.
                    from_user_new_balance = sp.compute(sp.as_nat(from_user_balance - tx.amount))
                    sp.if from_user_new_balance > 0:
                        self.data.ledger[from_user] = from_user_new_balance
                    sp.else:
                        del self.data.ledger[from_user]
                    
                    # Update to_user balance or add to ledger.
                    to_user = sp.compute(self.ledger_key.make(tx.to_, tx.token_id))
                    sp.if self.data.ledger.contains(to_user):
                        self.data.ledger[to_user] += tx.amount
                    sp.else:
                         self.data.ledger[to_user] = tx.amount
                sp.else:
                    pass

    @sp.entry_point
    def balance_of(self, params):
        # paused may mean that balances are meaningless:
        sp.verify( ~self.isPaused(), message = self.error_message.paused())
        sp.set_type(params, Balance_of.entry_point_type())
        def f_process_request(req):
            user = sp.compute(self.ledger_key.make(req.owner, req.token_id))
            sp.verify(self.data.token_metadata.contains(req.token_id), message = self.error_message.token_undefined())
            sp.if self.data.ledger.contains(user):
                balance = self.data.ledger[user]
                sp.result(
                    sp.record(
                        request = sp.record(
                            owner = sp.set_type_expr(req.owner, sp.TAddress),
                            token_id = sp.set_type_expr(req.token_id, sp.TNat)),
                        balance = balance))
            sp.else:
                sp.result(
                    sp.record(
                        request = sp.record(
                            owner = sp.set_type_expr(req.owner, sp.TAddress),
                            token_id = sp.set_type_expr(req.token_id, sp.TNat)),
                        balance = 0))
        res = sp.local("responses", params.requests.map(f_process_request))
        destination = sp.set_type_expr(params.callback, sp.TContract(Balance_of.response_type()))
        sp.transfer(res.value, sp.mutez(0), destination)

    @sp.entry_point
    def update_operators(self, params):
        sp.set_type(params, sp.TList(
            sp.TVariant(
                add_operator = self.operator_param.get_type(),
                remove_operator = self.operator_param.get_type()
            )
        ))
        sp.for update in params:
            with update.match_cases() as arg:
                with arg.match("add_operator") as upd:
                    # Sender must be the owner
                    sp.verify(upd.owner == sp.sender, message = self.error_message.not_owner())
                    # Add operator
                    self.operator_set.add(self.data.operators,
                                          upd.owner,
                                          upd.operator,
                                          upd.token_id)
                with arg.match("remove_operator") as upd:
                    # Sender must be the owner
                    sp.verify(upd.owner == sp.sender, message = self.error_message.not_owner())
                    # Remove operator
                    self.operator_set.remove(self.data.operators,
                                             upd.owner,
                                             upd.operator,
                                             upd.token_id)

    @sp.entry_point
    def update_adhoc_operators(self, params):
        # Supports add_adhoc_operators, and clear_adhoc_operators.
        sp.set_type(params, sp.TVariant(
            add_adhoc_operators = sp.TList(self.adhoc_operator_param.get_type()),
            clear_adhoc_operators = sp.TUnit
        ))

        with params.match_cases() as arg:
            with arg.match("add_adhoc_operators") as updates:
                # Check adhoc operator limit. To prevent potential gaslock.
                sp.verify(sp.len(updates) <= 100, message = self.error_message.adhoc_operator_limit())

                # Clear adhoc operators. In case they weren't.
                self.data.adhoc_operators = self.adhoc_operator_set.make()

                # Add adhoc operators.
                sp.for upd in updates:
                    self.adhoc_operator_set.add(self.data.adhoc_operators,
                        sp.sender, # Sender must be the owner
                        upd.operator,
                        upd.token_id)
            with arg.match("clear_adhoc_operators"):
                # Clear adhoc operators.
                self.data.adhoc_operators = self.adhoc_operator_set.make()

class FA2_change_metadata(FA2_core):
    @sp.entry_point
    def set_metadata(self, k, v):
        sp.verify(self.isAdministrator(sp.sender), message = self.error_message.not_admin())
        self.data.metadata[k] = v

class FA2_mint(FA2_core):
    @sp.entry_point
    def mint(self, params):
        mint_param_t = sp.TRecord(
            address = sp.TAddress,
            amount = sp.TNat,
            token_id = sp.TNat,
            metadata = sp.TMap(sp.TString, sp.TBytes)
        ).layout(("address", ("amount", ("token_id", "metadata"))))
        if self.config.royalties:
            mint_param_t = mint_param_t.with_fields(
                royalties = fa2_royalties.FA2_Royalties.ROYALTIES_TYPE
            ).layout(("address", ("amount", ("token_id", ("metadata", "royalties")))))
        sp.set_type(params, mint_param_t)

        sp.verify(self.isAdministrator(sp.sender), message = self.error_message.not_admin())
        # We don't check for pauseness because we're the admin.

        # Check token type constraints.
        if self.config.single_asset:
            sp.verify(params.token_id == 0, message = "single-asset: token-id <> 0")
        if self.config.non_fungible:
            sp.verify(params.amount == 1, message = "NFT-asset: amount <> 1")
            sp.verify(~ self.token_id_set.contains(self.data.all_tokens, params.token_id),
                message = "NFT-asset: cannot mint twice same token")

        # Validate royalties.
        if self.config.royalties:
            self.validateRoyalties(params.royalties)

        # Update balance
        user = sp.compute(self.ledger_key.make(params.address, params.token_id))
        sp.if self.data.ledger.contains(user):
            self.data.ledger[user] += params.amount
        sp.else:
            self.data.ledger[user] = params.amount
        
        # Add token metadata, if it doesn't exist.
        sp.if ~ self.token_id_set.contains(self.data.all_tokens, params.token_id):
            self.token_id_set.add(self.data.all_tokens, params.token_id)
            self.data.token_metadata[params.token_id] = sp.record(
                token_id    = params.token_id,
                token_info  = params.metadata
            )

        # Royalties, total supply.
        if self.config.store_total_supply or self.config.royalties:
            token_extra = sp.compute(self.data.token_extra.get(params.token_id, default_value = self.token_extra_data.get_default()))
            if self.config.store_total_supply:
                token_extra.total_supply += params.amount
            if self.config.royalties:
                token_extra.royalty_info = params.royalties
            self.data.token_extra[params.token_id] = token_extra

class FA2_token_metadata(FA2_core):
    def set_token_metadata_view(self):
        def token_metadata(self, tok):
            """
            Return the token-metadata URI for the given token.

            For a reference implementation, dynamic-views seem to be the
            most flexible choice.
            """
            sp.set_type(tok, sp.TNat)
            sp.result(self.data.token_metadata[tok])

        self.token_metadata = sp.onchain_view(pure = True, doc = "Get Token Metadata")(token_metadata)

    # make_metadataThis is what we want to modify for the token metadata. HEN puts it all on IPFS.
    def make_metadata(symbol, name, decimals):
        "Helper function to build metadata JSON bytes values."
        return (sp.map(l = {
            # Remember that michelson wants map already in ordered
            "decimals" : sp.utils.bytes_of_string("%d" % decimals),
            "name" : sp.utils.bytes_of_string(name),
            "symbol" : sp.utils.bytes_of_string(symbol)
        }))

##
## Change: add distribute
## FA2_distribute can be added with extend_instance
class FA2_distribute(FA2_core):
    @sp.entry_point
    def distribute(self, recipients):
        sp.set_type(recipients, sp.TList(sp.TRecord(
            to_=sp.TAddress, amount=sp.TNat
        ).layout(("to_", "amount"))))
        sp.verify(self.data.all_tokens != 0, 'Token must have been minted') 
        sp.for rec in recipients:
            # this effectively includes the mint function here.
            self.mint.f(self, sp.record(address = rec.to_,
                amount = rec.amount,
                metadata = {}, # If token 0 has been minted, this isn't used.
                token_id = 0))

##
## Change: add burn
## FA2_burn can be added with extend_instance
class FA2_burn(FA2_core):
    @sp.entry_point
    def burn(self, params):
        sp.set_type(params, sp.TRecord(
            token_id=sp.TNat, address=sp.TAddress, amount=sp.TNat
        ).layout(("address", ("amount", "token_id"))))

        sp.verify(~self.isPaused(), message = self.error_message.paused())
        
        # check ownership and operators
        sender_verify = (params.address == sp.sender)
        message = self.error_message.not_owner()
        if self.config.operator_burn:
            message = self.error_message.not_operator()
            sender_verify |= (self.adhoc_operator_set.is_member(self.data.adhoc_operators, params.address, sp.sender, params.token_id) |
                self.operator_set.is_member(self.data.operators, params.address, sp.sender, params.token_id))
        sp.verify(sender_verify, message = message)

        # Fail if token doesn't exist.
        # TODO: check token_metadata instead?
        sp.if ~ self.token_id_set.contains(self.data.all_tokens, params.token_id):
            sp.failwith(self.error_message.token_undefined())

        # Update balance
        user = sp.compute(self.ledger_key.make(params.address, params.token_id))
        sp.if self.data.ledger.contains(user):
            # Check balance.
            balance = sp.compute(self.data.ledger[user])
            sp.verify((balance >= params.amount),
                message = self.error_message.insufficient_balance())
            
            # The user has sufficient banlance, subtract from it.
            new_balance = sp.compute(sp.as_nat(balance - params.amount))

            # If balance becomes 0, delete from ledger.
            sp.if new_balance > 0:
                self.data.ledger[user] = new_balance
            sp.else:
                del self.data.ledger[user]
        sp.else:
            # If the user doesn't have a balance, fail.
            sp.failwith(self.error_message.insufficient_balance())

        # Update total supply
        if self.config.store_total_supply:
            new_total_supply = sp.compute(sp.as_nat(self.data.token_extra[params.token_id].total_supply - params.amount))
            # Don't delete token_extra or token_metadata for single_asset
            if self.config.single_asset:
                self.data.token_extra[params.token_id].total_supply = new_total_supply
            else:
                # If total supply becomes 0, delete token_extra and token_metadata.
                sp.if new_total_supply > 0:
                    self.data.token_extra[params.token_id].total_supply = new_total_supply
                sp.else:
                    del self.data.token_extra[params.token_id]
                    del self.data.token_metadata[params.token_id]

# NOTE: pausable_contract.Pausable needs to come first. It also include Administrable.
class FA2_legacy(pausable_contract.Pausable, FA2_change_metadata, FA2_token_metadata, FA2_mint, FA2_core):
    @sp.onchain_view(pure=True)
    def get_balance(self, req):
        """This is the `get_balance` view defined in TZIP-12."""
        sp.set_type(
            req, sp.TRecord(
                owner = sp.TAddress,
                token_id = sp.TNat
            ).layout(("owner", "token_id")))
        user = self.ledger_key.make(req.owner, req.token_id)
        sp.verify(self.data.token_metadata.contains(req.token_id), message = self.error_message.token_undefined())
        # Change: use map.get with default value to prevent exception
        sp.result(self.data.ledger.get(user, sp.nat(0)))

    @sp.onchain_view(pure=True)
    def count_tokens(self):
        """Get how many tokens are in this FA2 contract."""
        sp.result(self.token_id_set.cardinal(self.data.all_tokens))

    @sp.onchain_view(pure=True)
    def does_token_exist(self, tok):
        """Ask whether a token ID is exists."""
        sp.set_type(tok, sp.TNat)
        sp.result(self.data.token_metadata.contains(tok))

    @sp.onchain_view(pure=True)
    def total_supply(self, tok):
        """Returns the total supply of a token."""
        sp.set_type(tok, sp.TNat)
        if self.config.store_total_supply:
            sp.result(self.data.token_extra[tok].total_supply)
        else:
            sp.result("total-supply not supported")

    @sp.onchain_view(pure=True)
    def is_operator(self, query):
        """Returns if address is operator of a token."""
        sp.set_type(query,
                    sp.TRecord(token_id = sp.TNat,
                               owner = sp.TAddress,
                               operator = sp.TAddress).layout(
                                   ("owner", ("operator", "token_id"))))
        sp.result(
            self.operator_set.is_member(self.data.operators,
                                        query.owner,
                                        query.operator,
                                        query.token_id)
        )

    def __init__(self, config, metadata, admin):
         # Add FA2 extension mixins
        if config.allow_burn_tokens:
            self.extend_instance(FA2_burn, False)
        if config.add_distribute:
            self.extend_instance(FA2_distribute, False)
        FA2_core.__init__(self, config, metadata)
        # Add pausable, administrable and mybe royalties
        pausable_contract.Pausable.__init__(self, administrator = admin)
        if config.royalties:
            self.extend_instance(fa2_royalties.FA2_Royalties, True)
        
        # Let's show off some meta-programming:
        list_of_views = [
            self.get_balance
            , self.does_token_exist
            , self.count_tokens
            , self.is_operator
        ]

        if config.store_total_supply:
            list_of_views = list_of_views + [self.total_supply]
        if config.use_token_metadata_offchain_view:
            self.set_token_metadata_view()
            list_of_views = list_of_views + [self.token_metadata]
        if config.royalties:
            list_of_views = list_of_views + [self.get_token_royalties]

        metadata_base = {
            "name": config.metadata_name
            , "version": "1.0.0"
            , "description" : (
                config.metadata_description + "\n\nBased on Seb Mondet's FA2 implementation: https://gitlab.com/smondet/fa2-smartpy.git"
            )
            , "interfaces": ["TZIP-012", "TZIP-016"]
            , "authors": [
                '852Kerfunke <https://github.com/852Kerfunkle>',
                "Seb Mondet <https://seb.mondet.org>"
            ]
            , "homepage": 'https://www.tz1and.com'
            , "views": list_of_views
            , "source": {
                "tools": ["SmartPy"]
                , "location": "https://github.com/tz1and"
            }
            , "permissions": {
                "operator":
                "owner-or-operator-transfer"
                , "receiver": "owner-no-hook"
                , "sender": "owner-no-hook"
            }
        }
        self.init_metadata("metadata_base", metadata_base)
    
    def extend_instance(self, cls, init, **kwargs):
        """Apply mixins to a class instance after creation"""
        base_cls = self.__class__
        base_cls_name = self.__class__.__name__
        self.__class__ = type(base_cls_name, (base_cls, cls),{})
        if init:
            cls.__init__(self, **kwargs)

## ## Tests
##
## ### Auxiliary Consumer Contract
##
## This contract is used by the tests to be on the receiver side of
## callback-based entry-points.
## It stores facts about the results in order to use `scenario.verify(...)`
## (cf.
##  [documentation](https://smartpy.io/docs/scenarios/testing)).
class View_consumer(sp.Contract):
    def __init__(self, contract):
        self.contract = contract
        self.init(last_sum = 0)

    @sp.entry_point
    def reinit(self):
        self.data.last_sum = 0
        # It's also nice to make this contract have more than one entry point.

    @sp.entry_point
    def receive_balances(self, params):
        sp.set_type(params, Balance_of.response_type())
        self.data.last_sum = 0
        sp.for resp in params:
            self.data.last_sum += resp.balance

## ### Generation of Test Scenarios
##
## Tests are also parametrized by the `FA2_config` object.
## The best way to visualize them is to use the online IDE
## (<https://www.smartpy.io/ide/>).
def add_test(config, is_default = True):
    @sp.add_test(name = config.name, is_default = is_default)
    def test():
        scenario = sp.test_scenario()
        scenario.h1("FA2 Contract Name: " + config.name)
        scenario.table_of_contents()
        # sp.test_account generates ED25519 key-pairs deterministically:
        admin  = sp.test_account("Administrator")
        alice  = sp.test_account("Alice")
        bob    = sp.test_account("Robert")
        carol  = sp.test_account("Carol")
        darryl = sp.test_account("Darryl")
        eve    = sp.test_account("Eve")
        # Let's display the accounts:
        scenario.h2("Accounts")
        scenario.show([admin, alice, bob])
        c1 = FA2_legacy(config = config,
                 metadata = sp.utils.metadata_of_url("https://example.com"),
                 admin = admin.address)
        scenario += c1
        if config.non_fungible:
            # TODO
            return
        if config.add_distribute:
            scenario.h2("distribute before mint")
            c1.distribute([
                sp.record(to_ = darryl.address, amount = 50 ),
                sp.record(to_ = eve.address, amount = 50 )
            ]).run(sender = admin, valid = False)
        scenario.h2("Initial Minting")
        scenario.p("The administrator mints 100 token-0's to Alice.")
        tok0_md = FA2_legacy.make_metadata(
            name = "The Token Zero",
            decimals = 2,
            symbol= "TK0" )
        c1.mint(address = alice.address,
                            amount = 50,
                            metadata = tok0_md,
                            **({"royalties": sp.record(
                                royalties=sp.nat(150),
                                contributors= sp.map({
                                    alice.address: sp.record(relative_royalties=sp.nat(1000), role="minter")
                            }))} if config.royalties else {}),
                            token_id = 0).run(sender = admin)
        # Mint a second time
        c1.mint(address = alice.address,
                            amount = 50,
                            metadata = tok0_md,
                            **({"royalties": sp.record(
                                royalties=sp.nat(150),
                                contributors= sp.map({
                                    alice.address: sp.record(relative_royalties=sp.nat(1000), role="minter")
                            }))} if config.royalties else {}),
                            token_id = 0).run(sender = admin)
        scenario.h2("Transfers Alice -> Bob")
        c1.transfer(
            [
                c1.batch_transfer.item(from_ = alice.address,
                                    txs = [
                                        sp.record(to_ = bob.address,
                                                  amount = 10,
                                                  token_id = 0)
                                    ])
            ]).run(sender = alice)
        scenario.verify(
            c1.data.ledger[c1.ledger_key.make(alice.address, 0)] == 90)
        scenario.verify(
            c1.data.ledger[c1.ledger_key.make(bob.address, 0)] == 10)
        c1.transfer(
            [
                c1.batch_transfer.item(from_ = alice.address,
                                    txs = [
                                        sp.record(to_ = bob.address,
                                                  amount = 10,
                                                  token_id = 0),
                                        sp.record(to_ = bob.address,
                                                  amount = 11,
                                                  token_id = 0)
                                    ])
            ]).run(sender = alice)
        scenario.verify(
            c1.data.ledger[c1.ledger_key.make(alice.address, 0)] == 90 - 10 - 11
        )
        scenario.verify(
            c1.data.ledger[c1.ledger_key.make(bob.address, 0)]
            == 10 + 10 + 11)
        # test distribute
        if config.add_distribute:
            scenario.h2("distribute")
            c1.distribute([
                sp.record(to_ = darryl.address, amount = 50 ),
                sp.record(to_ = eve.address, amount = 50 )
            ]).run(sender = admin)
            if config.store_total_supply:
                scenario.verify(c1.data.token_extra[0].total_supply == 200)
            scenario.verify(c1.data.ledger[c1.ledger_key.make(darryl.address, 0)] == 50)
            scenario.verify(c1.data.ledger[c1.ledger_key.make(eve.address, 0)] == 50)
            c1.distribute([
                sp.record(to_ = darryl.address, amount = 50 ),
                sp.record(to_ = eve.address, amount = 50 )
            ]).run(sender = bob, valid = False)
        if not config.allow_burn_tokens:
            # TODO
            return
        scenario.h2("Burning tokens")
        support_operator_burn = config.operator_burn
        if config.store_total_supply:
            supply_before = scenario.compute(c1.data.token_extra[0].total_supply)
        c1.burn(address = alice.address,
            amount = 10,
            token_id = 0).run(sender = admin, valid = False, exception = ("FA2_NOT_OPERATOR" if support_operator_burn else "FA2_NOT_OWNER"))
        c1.burn(address = bob.address,
            amount = 5,
            token_id = 0).run(sender = admin, valid = False, exception = ("FA2_NOT_OPERATOR" if support_operator_burn else "FA2_NOT_OWNER"))
        c1.burn(address = alice.address,
            amount = 10,
            token_id = 0).run(sender = alice)
        c1.burn(address = bob.address,
            amount = 5,
            token_id = 0).run(sender = bob)
        c1.burn(address = bob.address,
            amount = 10,
            token_id = 0).run(sender = alice, valid = False, exception = ("FA2_NOT_OPERATOR" if support_operator_burn else "FA2_NOT_OWNER"))
        c1.burn(address = alice.address,
            amount = 100,
            token_id = 0).run(sender = alice, valid = False, exception = "FA2_INSUFFICIENT_BALANCE")
        c1.burn(address = carol.address,
            amount = 1,
            token_id = 0).run(sender = carol, valid = False, exception = "FA2_INSUFFICIENT_BALANCE")
        c1.burn(address = alice.address,
            amount = 100,
            token_id = 1).run(sender = alice, valid = False, exception = "FA2_TOKEN_UNDEFINED")
        if config.store_total_supply:
            scenario.verify(supply_before == c1.data.token_extra[0].total_supply + 15)
        scenario.verify(
            c1.data.ledger[c1.ledger_key.make(alice.address, 0)] == 90 - 10 - 11 - 10
        )
        scenario.verify(
            c1.data.ledger[c1.ledger_key.make(bob.address, 0)] == 10 + 10 + 11 - 5)
        if config.single_asset:
            return
        scenario.h2("More Token Types")
        tok1_md = FA2_legacy.make_metadata(
            name = "The Second Token",
            decimals = 0,
            symbol= "TK1" )
        c1.mint(address = bob.address,
                            amount = 100,
                            metadata = tok1_md,
                            **({"royalties": sp.record(
                                royalties=sp.nat(150),
                                contributors= sp.map({
                                    bob.address: sp.record(relative_royalties=sp.nat(1000), role="minter")
                            }))} if config.royalties else {}),
                            token_id = 1).run(sender = admin)
        tok2_md = FA2_legacy.make_metadata(
            name = "The Token Number Three",
            decimals = 0,
            symbol= "TK2" )
        c1.mint(address = bob.address,
                            amount = 200,
                            metadata = tok2_md,
                            **({"royalties": sp.record(
                                royalties=sp.nat(150),
                                contributors= sp.map({
                                    bob.address: sp.record(relative_royalties=sp.nat(1000), role="minter")
                            }))} if config.royalties else {}),
                            token_id = 2).run(sender = admin)
        scenario.h3("Multi-token Transfer Bob -> Alice")
        c1.transfer(
            [
                c1.batch_transfer.item(from_ = bob.address,
                                    txs = [
                                        sp.record(to_ = alice.address,
                                                  amount = 10,
                                                  token_id = 0),
                                        sp.record(to_ = alice.address,
                                                  amount = 10,
                                                  token_id = 1)]),
                # We voluntarily test a different sub-batch:
                c1.batch_transfer.item(from_ = bob.address,
                                    txs = [
                                        sp.record(to_ = alice.address,
                                                  amount = 10,
                                                  token_id = 2)])
            ]).run(sender = bob)
        scenario.h2("Burning more token types")
        c1.burn(address = bob.address,
            amount = 10,
            token_id = 1).run(sender = admin, valid = False, exception = ("FA2_NOT_OPERATOR" if support_operator_burn else "FA2_NOT_OWNER"))
        c1.burn(address = bob.address,
            amount = 1,
            token_id = 1).run(sender = bob)
        c1.burn(address = bob.address,
            amount = 5,
            token_id = 2).run(sender = admin, valid = False, exception = ("FA2_NOT_OPERATOR" if support_operator_burn else "FA2_NOT_OWNER"))
        c1.burn(address = bob.address,
            amount = 1,
            token_id = 2).run(sender = bob)
        scenario.h2("Other Basic Permission Tests")
        scenario.h3("Bob cannot transfer Alice's tokens.")
        c1.transfer(
            [
                c1.batch_transfer.item(from_ = alice.address,
                                    txs = [
                                        sp.record(to_ = bob.address,
                                                  amount = 10,
                                                  token_id = 0),
                                        sp.record(to_ = bob.address,
                                                  amount = 1,
                                                  token_id = 0)])
            ]).run(sender = bob, valid = False)
        scenario.h3("Admin can't transfer anything.")
        c1.transfer(
            [
                c1.batch_transfer.item(from_ = alice.address,
                                    txs = [
                                        sp.record(to_ = bob.address,
                                                  amount = 10,
                                                  token_id = 0),
                                        sp.record(to_ = bob.address,
                                                  amount = 10,
                                                  token_id = 1)]),
                c1.batch_transfer.item(from_ = bob.address,
                                    txs = [
                                        sp.record(to_ = alice.address,
                                                  amount = 11,
                                                  token_id = 0)])
            ]).run(sender = admin, valid = False, exception = ("FA2_NOT_OPERATOR"))
        scenario.h3("Admin cannot transfer too much.")
        c1.transfer(
            [
                c1.batch_transfer.item(from_ = alice.address,
                                    txs = [
                                        sp.record(to_ = bob.address,
                                                  amount = 1000,
                                                  token_id = 0)])
            ]).run(sender = admin, valid = False)
        scenario.h3("Consumer Contract for Callback Calls.")
        consumer = View_consumer(c1)
        scenario += consumer
        scenario.p("Consumer virtual address: "
                   + consumer.address.export())
        scenario.h2("Balance-of.")
        def arguments_for_balance_of(receiver, reqs):
            return (sp.record(
                callback = sp.contract(
                    Balance_of.response_type(),
                    receiver.address,
                    entry_point = "receive_balances").open_some(),
                requests = reqs))
        c1.balance_of(arguments_for_balance_of(consumer, [
            sp.record(owner = alice.address, token_id = 0),
            sp.record(owner = alice.address, token_id = 1),
            sp.record(owner = alice.address, token_id = 2)
        ]))
        scenario.verify(consumer.data.last_sum == 89)
        scenario.h2("Operators")
        scenario.p("This version was compiled with operator support.")
        scenario.p("Calling 0 updates should work:")
        c1.update_operators([]).run()
        scenario.h3("Operator Accounts")
        op0 = sp.test_account("Operator0")
        op1 = sp.test_account("Operator1")
        op2 = sp.test_account("Operator2")
        scenario.show([op0, op1, op2])
        scenario.p("Admin can't change Alice's operator.")
        c1.update_operators([
            sp.variant("add_operator", c1.operator_param.make(
                owner = alice.address,
                operator = op1.address,
                token_id = 0)),
            sp.variant("add_operator", c1.operator_param.make(
                owner = alice.address,
                operator = op1.address,
                token_id = 2))
        ]).run(sender = admin, valid = False, exception = "FA2_NOT_OWNER")
        scenario.p("Only Alice can change Alice's operator.")
        c1.update_operators([
            sp.variant("add_operator", c1.operator_param.make(
                owner = alice.address,
                operator = op1.address,
                token_id = 0)),
            sp.variant("add_operator", c1.operator_param.make(
                owner = alice.address,
                operator = op1.address,
                token_id = 2))
        ]).run(sender = alice)
        scenario.p("Operator1 can now transfer Alice's tokens 0 and 2")
        c1.transfer(
            [
                c1.batch_transfer.item(from_ = alice.address,
                                    txs = [
                                        sp.record(to_ = bob.address,
                                                  amount = 2,
                                                  token_id = 0),
                                        sp.record(to_ = op1.address,
                                                  amount = 2,
                                                  token_id = 2)])
            ]).run(sender = op1)
        scenario.p("Operator1 can now burn Alice's tokens 0 and 2")
        c1.burn(address = alice.address,
            amount = 1,
            token_id = 2).run(sender = op1, valid = support_operator_burn)
        scenario.p("Operator1 cannot transfer Bob's tokens")
        c1.transfer(
            [
                c1.batch_transfer.item(from_ = bob.address,
                                    txs = [
                                        sp.record(to_ = op1.address,
                                                  amount = 2,
                                                  token_id = 1)])
            ]).run(sender = op1, valid = False)
        scenario.p("Operator1 cannot burn Bob's tokens")
        c1.burn(address = bob.address,
            amount = 10,
            token_id = 1).run(sender = op1, valid = False, exception = ("FA2_NOT_OPERATOR" if support_operator_burn else "FA2_NOT_OWNER"))
        scenario.p("Operator2 cannot transfer Alice's tokens")
        c1.transfer(
            [
                c1.batch_transfer.item(from_ = alice.address,
                                    txs = [
                                        sp.record(to_ = bob.address,
                                                  amount = 2,
                                                  token_id = 1)])
            ]).run(sender = op2, valid = False)
        scenario.p("Operator2 cannot burn Alice's tokens")
        c1.burn(address = alice.address,
            amount = 10,
            token_id = 1).run(sender = op2, valid = False, exception = ("FA2_NOT_OPERATOR" if support_operator_burn else "FA2_NOT_OWNER"))
        scenario.p("Alice can remove their operator")
        c1.update_operators([
            sp.variant("remove_operator", c1.operator_param.make(
                owner = alice.address,
                operator = op1.address,
                token_id = 0)),
            sp.variant("remove_operator", c1.operator_param.make(
                owner = alice.address,
                operator = op1.address,
                token_id = 0))
        ]).run(sender = alice)
        scenario.p("Operator1 cannot transfer Alice's tokens any more")
        c1.transfer(
            [
                c1.batch_transfer.item(from_ = alice.address,
                                    txs = [
                                        sp.record(to_ = op1.address,
                                                  amount = 2,
                                                  token_id = 1)])
            ]).run(sender = op1, valid = False)
        scenario.p("Bob can add Operator0.")
        c1.update_operators([
            sp.variant("add_operator", c1.operator_param.make(
                owner = bob.address,
                operator = op0.address,
                token_id = 0)),
            sp.variant("add_operator", c1.operator_param.make(
                owner = bob.address,
                operator = op0.address,
                token_id = 1))
        ]).run(sender = bob)
        scenario.p("Operator0 can transfer Bob's tokens '0' and '1'")
        c1.transfer(
            [
                c1.batch_transfer.item(from_ = bob.address,
                                    txs = [
                                        sp.record(to_ = alice.address,
                                                  amount = 1,
                                                  token_id = 0)]),
                c1.batch_transfer.item(from_ = bob.address,
                                    txs = [
                                        sp.record(to_ = alice.address,
                                                  amount = 1,
                                                  token_id = 1)])
            ]).run(sender = op0)
        scenario.p("Bob cannot add Operator0 for Alice's tokens.")
        c1.update_operators([
            sp.variant("add_operator", c1.operator_param.make(
                owner = alice.address,
                operator = op0.address,
                token_id = 0
            ))
        ]).run(sender = bob, valid = False)
        scenario.p("Alice can also add Operator0 for their tokens 0.")
        c1.update_operators([
            sp.variant("add_operator", c1.operator_param.make(
                owner = alice.address,
                operator = op0.address,
                token_id = 0
            ))
        ]).run(sender = alice, valid = True)
        scenario.p("Operator0 can now transfer Bob's and Alice's 0-tokens.")
        c1.transfer(
            [
                c1.batch_transfer.item(from_ = bob.address,
                                    txs = [
                                        sp.record(to_ = alice.address,
                                                  amount = 1,
                                                  token_id = 0)]),
                c1.batch_transfer.item(from_ = alice.address,
                                    txs = [
                                        sp.record(to_ = bob.address,
                                                  amount = 1,
                                                  token_id = 0)])
            ]).run(sender = op0)
        scenario.p("Bob adds Operator2 as second operator for 0-tokens.")
        c1.update_operators([
            sp.variant("add_operator", c1.operator_param.make(
                owner = bob.address,
                operator = op2.address,
                token_id = 0
            ))
        ]).run(sender = bob, valid = True)
        scenario.p("Operator0 and Operator2 can transfer Bob's 0-tokens.")
        c1.transfer(
            [
                c1.batch_transfer.item(from_ = bob.address,
                                    txs = [
                                        sp.record(to_ = alice.address,
                                                  amount = 1,
                                                  token_id = 0)])
            ]).run(sender = op0)
        c1.transfer(
            [
                c1.batch_transfer.item(from_ = bob.address,
                                    txs = [
                                        sp.record(to_ = alice.address,
                                                  amount = 1,
                                                  token_id = 0)])
            ]).run(sender = op2)
        scenario.table_of_contents()

##
## ## Global Environment Parameters
##
## The build system communicates with the python script through
## environment variables.
## The function `environment_config` creates an `FA2_config` given the
## presence and values of a few environment variables.
def global_parameter(env_var, default):
    try:
        if os.environ[env_var] == "true" :
            return True
        if os.environ[env_var] == "false" :
            return False
        return default
    except:
        return default


def items_config():
    # Items is a multi-asset, fungible token, (that doesn't stores the total supply) an allows burning.
    return FA2_config(
        metadata_name = "tz1and Items",
        metadata_description = "tz1and Item FA2 Tokens.",
        single_asset = global_parameter("single_asset", False),
        non_fungible = global_parameter("non_fungible", False),
        add_mutez_transfer = global_parameter("add_mutez_transfer", False),
        store_total_supply = global_parameter("store_total_supply", True),
        lazy_entry_points = global_parameter("lazy_entry_points", False),
        use_token_metadata_offchain_view = global_parameter("use_token_metadata_offchain_view", False),
        allow_burn_tokens = global_parameter("allow_burn_tokens", True),
        add_distribute = global_parameter("add_distribute", False),
        royalties = global_parameter("royalties", True)
    )

def places_config():
    # Places is a multi-asset, non-fungible token. No burning allowed.
    return FA2_config(
        metadata_name = "tz1and Places",
        metadata_description = "tz1and Places FA2 Tokens.",
        single_asset = global_parameter("single_asset", False),
        non_fungible = global_parameter("non_fungible", True),
        add_mutez_transfer = global_parameter("add_mutez_transfer", False),
        store_total_supply = global_parameter("store_total_supply", False),
        lazy_entry_points = global_parameter("lazy_entry_points", False),
        use_token_metadata_offchain_view = global_parameter("use_token_metadata_offchain_view", False),
        allow_burn_tokens = global_parameter("allow_burn_tokens", False),
        add_distribute = global_parameter("add_distribute", False),
        royalties = global_parameter("royalties", False)
    )

def dao_config():
    # Places is a multi-asset, non-fungible token. No burning allowed.
    return FA2_config(
        metadata_name = "tz1and DAO",
        metadata_description = "tz1and DAO FA2 Token.",
        single_asset = global_parameter("single_asset", True),
        non_fungible = global_parameter("non_fungible", False),
        add_mutez_transfer = global_parameter("add_mutez_transfer", False),
        store_total_supply = global_parameter("store_total_supply", True),
        lazy_entry_points = global_parameter("lazy_entry_points", False),
        use_token_metadata_offchain_view = global_parameter("use_token_metadata_offchain_view", False),
        allow_burn_tokens = global_parameter("allow_burn_tokens", False),
        add_distribute = global_parameter("add_distribute", True),
        royalties = global_parameter("royalties", False)
    )
