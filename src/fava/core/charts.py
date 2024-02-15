"""Provide data suitable for Fava's charts. """
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import fields
from dataclasses import is_dataclass
from datetime import date
from datetime import timedelta
from typing import Any
from typing import Generator
from typing import Pattern
from typing import TYPE_CHECKING

from beancount.core import realization
from beancount.core.amount import Amount
from beancount.core.data import Booking
from beancount.core.data import iter_entry_dates
from beancount.core.data import Transaction
from beancount.core.display_context import DisplayContext
from beancount.core.inventory import Inventory
from beancount.core.number import Decimal
from beancount.core.position import Position
from beancount.core.position import from_string
from simplejson import JSONEncoder
from simplejson import loads

from fava.core._compat import FLAG_UNREALIZED
from fava.core.conversion import cost_or_value
from fava.core.conversion import units
from fava.core.conversion import get_market_value
from fava.core.module_base import FavaModule
from fava.core.tree import SerialisedTreeNode
from fava.core.tree import Tree
from fava.helpers import FavaAPIException
from fava.util import listify
from fava.util import pairwise
from fava.util.date import Interval

from fava.core.sankey import SankeyTreeEdge, SankeyTree

try:
    from flask.json.provider import JSONProvider
except ImportError:
    pass

if TYPE_CHECKING:  # pragma: no cover
    from flask import Flask
    from fava.core import FilteredLedger


ONE_DAY = timedelta(days=1)


def inv_to_dict(inventory: Inventory) -> dict[str, Decimal]:
    """Convert an inventory to a simple cost->number dict."""
    return {
        pos.units.currency: pos.units.number
        for pos in inventory
        if pos.units.number is not None
    }


Inventory.for_json = inv_to_dict  # type: ignore


class FavaJSONEncoder(JSONEncoder):
    """Allow encoding some Beancount date structures."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Allow use of a `for_json` method to serialise dict subclasses.
        kwargs["for_json"] = True
        # Sort dict keys (Flask also does this by default).
        kwargs["sort_keys"] = True
        super().__init__(*args, **kwargs)

    def default(self, o: Any) -> Any:
        # pylint: disable=too-many-return-statements
        if isinstance(o, (date, Amount, Booking, DisplayContext, Position)):
            return str(o)
        if isinstance(o, (set, frozenset)):
            return list(o)
        if isinstance(o, Pattern):
            return o.pattern
        if is_dataclass(o):
            return {field.name: getattr(o, field.name) for field in fields(o)}
        return JSONEncoder.default(self, o)


ENCODER = FavaJSONEncoder()
PRETTY_ENCODER = FavaJSONEncoder(indent=True)


def setup_json_for_app(app: Flask) -> None:
    """Use custom JSON encoder."""
    if hasattr(app, "json_provider_class"):  # Flask >=2.2

        class FavaJSONProvider(JSONProvider):
            """Use custom JSON encoder and decoder."""

            def dumps(
                self, obj: Any, *, _option: Any = None, **_kwargs: Any
            ) -> Any:
                return ENCODER.encode(obj)

            def loads(self, s: str | bytes, **_kwargs: Any) -> Any:
                return loads(s)

        app.json = FavaJSONProvider(app)

    else:  # pragma: no cover
        app.json_encoder = FavaJSONEncoder  # type: ignore


@dataclass
class DateAndBalance:
    """Balance at a date."""

    date: date
    balance: dict[str, Decimal] | Inventory


@dataclass
class DateAndBalanceWithBudget:
    """Balance at a date with a budget."""

    date: date
    balance: Inventory
    account_balances: dict[str, Inventory]
    budgets: dict[str, Decimal]


class ChartModule(FavaModule):
    """Return data for the various charts in Fava."""

    def hierarchy(
        self,
        filtered: FilteredLedger,
        account_name: str,
        conversion: str,
        begin: date | None = None,
        end: date | None = None,
    ) -> SerialisedTreeNode:
        """An account tree."""
        if begin is not None and end is not None:
            tree = Tree(iter_entry_dates(filtered.entries, begin, end))
        else:
            tree = filtered.root_tree
        return tree.get(account_name).serialise(
            conversion, self.ledger.price_map, end - ONE_DAY if end else None
        )

    @listify
    def prices(
        self, filtered: FilteredLedger
    ) -> Generator[tuple[str, str, list[tuple[date, Decimal]]], None, None]:
        """The prices for all commodity pairs.

        Returns:
            A list of tuples (base, quote, prices) where prices
            is a list of prices.
        """
        for base, quote in self.ledger.commodity_pairs():
            prices = filtered.prices(base, quote)
            if prices:
                yield base, quote, prices

    @listify
    def interval_budget(
        self,
        filtered: FilteredLedger,
        interval: Interval,
        extension,
        conversion: str = None,
        invert: bool = False,
    ) -> Generator[DateAndBalanceWithBudget, None, None]:
        """Renders totals for account (or accounts) in the intervals.

        Args:
            interval: An interval.
            accounts: A single account (str) or a tuple of accounts.
            conversion: The conversion to use.
            invert: invert all numbers.
        """
        ans = extension.get_budget_tree().interval_budget(filtered)
        assert ans
        for x in ans:
            (begin, balance, account_balances, _) = x
            yield DateAndBalanceWithBudget( begin, balance, account_balances, {})


    @listify
    def interval_totals(
        self,
        filtered: FilteredLedger,
        interval: Interval,
        accounts: str | tuple[str],
        conversion: str,
        invert: bool = False,
        compute_assets: bool = False,
    ) -> Generator[DateAndBalanceWithBudget, None, None]:
        """Renders totals for account (or accounts) in the intervals.

        Args:
            interval: An interval.
            accounts: A single account (str) or a tuple of accounts.
            conversion: The conversion to use.
            invert: invert all numbers.
        """
        # pylint: disable=too-many-locals
        price_map = self.ledger.price_map
        today = date.today()
        if compute_assets:
            min_accounts = [
                account
                for account in self.ledger.accounts.keys()
                if account.startswith("Assets:")
            ]
            for begin, end in pairwise(filtered.interval_ends(interval)):
                if begin > today:
                    break
                entries = list(iter_entry_dates(self.ledger.all_entries, date.min, end))
                root = realization.realize(entries, min_accounts=min_accounts, compute_balance=True)
                children = realization.iter_children(root)
                for child in children:
                    child.balance = realization.compute_balance(child)
                total_assets = root.get("Assets")
                assert not total_assets.balance.is_empty()
                account_balances = {}
                for name in ["CurrentInvests", "CurrentAssets", "NonCurrentAssets"]:
                    account_balances["Assets:" + name] = total_assets.get(name).balance
                yield DateAndBalanceWithBudget(begin, total_assets.balance, account_balances, {})

        empty_count = 0
        for begin, end in pairwise(filtered.interval_ends(interval)):
            inventory = Inventory()
            entries = iter_entry_dates(filtered.entries, begin, end)
            account_inventories = {}
            for entry in (e for e in entries if isinstance(e, Transaction)):
                for posting in entry.postings:
                    if posting.account.startswith(accounts):
                        if posting.account not in account_inventories:
                            account_inventories[posting.account] = Inventory()
                        account_inventories[posting.account].add_position(
                            posting
                        )
                        inventory.add_position(posting)
            balance = cost_or_value(
                inventory, conversion, price_map, end - ONE_DAY
            )

            if balance.is_empty() and begin > today:
                empty_count += 1
                if empty_count > 3:
                    return

            account_balances = {}
            for account, acct_value in account_inventories.items():
                account_balances[account] = cost_or_value(
                    acct_value,
                    conversion,
                    price_map,
                    end - ONE_DAY,
                )
            budgets = {}
            if isinstance(accounts, str):
                budgets = self.ledger.budgets.calculate_children(
                    accounts, begin, end
                )

            if invert:
                # pylint: disable=invalid-unary-operand-type
                balance = -balance
                budgets = {k: -v for k, v in budgets.items()}
                account_balances = {k: -v for k, v in account_balances.items()}

            yield DateAndBalanceWithBudget(
                begin,
                balance,
                account_balances,
                budgets,
            )

    @listify
    def linechart(
        self, filtered: FilteredLedger, accounts_name: str, conversion: str
    ) -> Generator[DateAndBalance, None, None]:
        """The balance of an account.

        Args:
            account_name: A string.
            conversion: The conversion to use.

        Returns:
            A list of dicts for all dates on which the balance of the given
            account has changed containing the balance (in units) of the
            account at that date.
        """
        if isinstance(accounts_name, str):
            accounts_name = [accounts_name]
        for account_name in accounts_name:
            real_account = realization.get_or_create(
                filtered.root_account, account_name
            )
            postings = realization.get_postings(real_account)
            journal = realization.iterate_with_balance(postings)

            # When the balance for a commodity just went to zero, it will be
            # missing from the 'balance' so keep track of currencies that last had
            # a balance.
            last_currencies = None

            price_map = self.ledger.price_map
            for entry, _, change, balance_inventory in journal:
                if change.is_empty():
                    continue

                balance = inv_to_dict(
                    cost_or_value(
                        balance_inventory, conversion, price_map, entry.date
                    )
                )

                currencies = set(balance.keys())
                if last_currencies:
                    for currency in last_currencies - currencies:
                        balance[currency] = 0
                last_currencies = currencies

                yield DateAndBalance(entry.date, balance)

    @listify
    def net_worth(
        self, filtered: FilteredLedger, interval: Interval, conversion: str
    ) -> Generator[DateAndBalance, None, None]:
        """Compute net worth.

        Args:
            interval: A string for the interval.
            conversion: The conversion to use.

        Returns:
            A list of dicts for all ends of the given interval containing the
            net worth (Assets + Liabilities) separately converted to all
            operating currencies.
        """
        transactions = (
            entry
            for entry in filtered.entries
            if (
                isinstance(entry, Transaction)
                and entry.flag != FLAG_UNREALIZED
            )
        )

        types = (
            self.ledger.options["name_assets"],
            self.ledger.options["name_liabilities"],
        )

        txn = next(transactions, None)
        inventory = Inventory()

        price_map = self.ledger.price_map
        for end_date in filtered.interval_ends(interval):
            while txn and txn.date < end_date:
                for posting in txn.postings:
                    if posting.account.startswith(types):
                        inventory.add_position(posting)
                txn = next(transactions, None)
            yield DateAndBalance(
                end_date,
                cost_or_value(
                    inventory, conversion, price_map, end_date - ONE_DAY
                ),
            )

    @listify
    def sankey_budget(
        self, filtered: FilteredLedger, interval: Interval, conversion: str,
        extension, node=None
    ) -> Generator[DateAndBalance, None, None]:
        """Compute the money flow.

        Args:
            interval: A string for the interval.
            conversion: The conversion to use.

        Returns:
            A list of dicts for all ends of the given interval containing the
            net worth (Assets + Liabilities) separately converted to all
            operating currencies.
        """
        import json
        (nodes, links) = extension.get_budget_tree().sankey_budget(filtered, node=node)
        # print(nodes)
        # for x in links:
        #     print(x)

        json_node = json.dumps(list(nodes))
        json_link = json.dumps(links)
        yield {"nodes_ss": json_node, "links_ss": json_link}

    @listify
    def sankey_balance_sheet(
        self, filtered: FilteredLedger, interval: Interval, conversion: str
    ) -> Generator[DateAndBalance, None, None]:
        """Compute the money flow.

        Args:
            interval: A string for the interval.
            conversion: The conversion to use.

        Returns:
            A list of dicts for all ends of the given interval containing the
            net worth (Assets + Liabilities) separately converted to all
            operating currencies.
        """
        transactions = (
            entry
            for entry in filtered.entries
            if (
                isinstance(entry, Transaction)
                and entry.flag != FLAG_UNREALIZED
            )
        )
        txn = next(transactions, None)
        txn_entries = []
        for end_date in filtered.interval_ends(interval):
            while txn and txn.date < end_date:
                txn_entries.append(txn)
                txn = next(transactions, None)

        def prune(edge: SankeyTreeEdge):
            if len(edge.u) == 0:
                # prune out edge not from root -> income/expenses
                return edge.v not in ("Assets", "Liabilities")

            # if "-Balance" in edge.v: return True

            return False

        assets_stat = dict()
        liabilities_stat = dict()
        equity_stat = dict()
        def collapse(edge: SankeyTreeEdge):
            if "Assets" == edge.v:
                return edge
            
            if "Assets" in edge.u and len(edge.u.split(":")) >= 3:
                return edge._replace(collapsed=True)

            if "Liabilities" in edge.v and len(edge.v.split(":")) >= 4:
                return edge._replace(collapsed=True)

            if "Equity" in edge.v and len(edge.v.split(":")) >= 3:
                return edge._replace(collapsed=True)
            
            if "Liabilities" in edge.u:
                edge = edge._replace(weight=-edge.weight)
            
            # Add weight prune to avoid too many branches
            u, v, weight = edge.u, edge.v, abs(edge.weight)
            if "Assets" in edge.u:
                # "assets" -> "assets:a:b"
                # "liabilities" -> "liabilities:a:b"
                u, v = v, u

            level = len(v.split(":"))
            if "Assets" in v:
                level_max = max(weight, assets_stat.get(level, 1))
                assets_stat[level] = level_max
            elif "Equity" in v:
                level_max = max(weight, equity_stat.get(level, 1))
                equity_stat[level] = level_max
            else:
                level_max = max(weight, liabilities_stat.get(level, 1))
                liabilities_stat[level] = level_max

            ratio = weight / level_max
            # print(u, v, level, ratio)

            if "Liabilities" in v and ratio < 0.04:
                return edge._replace(collapsed=True)

            if "Assets" in v and ratio < 0.01:
                return edge._replace(collapsed=True)

            if "Equity" in v and ratio < 0.01:
                return edge._replace(collapsed=True)

            return edge

        def finalize(tree: SankeyTree):
            assets = tree.encode_name(tree.name_id_.get("Assets", 0), "Assets")
            # liabilities = tree.encode_name(tree.name_id_.get("Liabilities", 0), "Liabilities")
            # equity = tree.encode_name(tree.name_id_.get("Equity", 0), "Equity")
            # tree.links_.append([assets, liabilities, str(tree.balance_map_.get("Liabilities", 0))])
            # tree.links_.append([assets, equity, str(tree.balance_map_.get("Equity", 0))])
            # liabilities = tree.encode_name(tree.name_id_.get("Liabilities", 0), "Liabilities")
            current = tree.encode_name(tree.name_id_.get("Liabilities:Current", 0), "Liabilities:Current")
            tree.links_.append([assets, current, str(abs(tree.balance_map_.get("Liabilities:Current", 0)))])

            noncurrent = tree.encode_name(tree.name_id_.get("Liabilities:NonCurrent", 0), "Liabilities:NonCurrent")
            noncurrent_val = abs(tree.balance_map_.get("Liabilities:NonCurrent", 0))
            if noncurrent_val > 0:
                tree.links_.append([assets, noncurrent, str(noncurrent_val)])
            else:
                if noncurrent in tree.nodes_:
                    tree.nodes_.remove(noncurrent)

            for x in tree.links_:
                print(x)

            return (tree.nodes_, tree.links_)

        tree = SankeyTree(txn_entries, finalize=finalize, prune=prune, collapse=collapse, 
                          conversion=conversion, price_map=self.ledger.price_map)
        (nodes, links) = tree.run()

        for x in links:
            # NOTE: reverse the direction
            x[1], x[0] = x[0], x[1]
            # print(x)
        
        import json
        json_node = json.dumps(list(nodes))
        json_link = json.dumps(links)
        yield {"nodes_ss": json_node, "links_ss": json_link}

    @listify
    def sankey_income_statement(
        self, filtered: FilteredLedger, interval: Interval, conversion: str
    ) -> Generator[DateAndBalance, None, None]:
        """Compute the money flow.

        Args:
            interval: A string for the interval.
            conversion: The conversion to use.

        Returns:
            A list of dicts for all ends of the given interval containing the
            net worth (Assets + Liabilities) separately converted to all
            operating currencies.
        """
        transactions = (
            entry
            for entry in filtered.entries
            if (
                isinstance(entry, Transaction)
                and entry.flag != FLAG_UNREALIZED
            )
        )
        txn = next(transactions, None)
        txn_entries = []
        for end_date in filtered.interval_ends(interval):
            while txn and txn.date < end_date:
                txn_entries.append(txn)
                txn = next(transactions, None)

        def prune(edge: SankeyTreeEdge):
            # For income statement
            if len(edge.u) == 0:
                # prune out edge not from root -> income/expenses
                return edge.v not in ("Income", "Expenses")

            if "-Balance" in edge.v: return True
            if "Company" in edge.v: return True
            if "Hospital:" in edge.v: return True

            return False


        income_stat = dict()
        expenses_stat = dict()
        def collapse(edge: SankeyTreeEdge):
            # if "Transport" in edge.v and len(edge.v.split(":")) > 2:
            #     # Collapse Expense:Transport:* account
            #     return edge._replace(collapsed=True)

            if "Income" in edge.u:
                edge = edge._replace(weight=-edge.weight)

            if "Expenses" in edge.v and len(edge.v.split(":")) > 3:
                return edge._replace(collapsed=True)

            if "Income" in edge.u and len(edge.u.split(":")) >= 2:
                return edge._replace(collapsed=True)

            # Add weight prune to avoid too many branches
            u, v, weight = edge.u, edge.v, abs(edge.weight)
            if "Income" in edge.u:
                # "income" -> "income:a:b"
                # "expense" -> "expense:a:b"
                u, v = v, u

            level = len(v.split(":"))
            if "Income" in v:
                level_max = max(weight, income_stat.get(level, 1))
                income_stat[level] = level_max
            else:
                level_max = max(weight, expenses_stat.get(level, 1))
                expenses_stat[level] = level_max
            
            ratio = float(weight) / max(float(level_max), 1)

            if "Expenses" in v and level > 2 and ratio < 0.04:
                return edge._replace(collapsed=True)

            if "Income" in v and ratio < 0.001:
                return edge._replace(collapsed=True)

            return edge

        def finalize(tree: SankeyTree):
            income_value = tree.balance_map_.get("Income", 0)
            expense_value = tree.balance_map_.get("Expenses", 0)

            if income_value == 0:
                tree.add_fake_income()

            if expense_value == 0:
                tree.add_fake_expenses()

            if income_value == 0 and expense_value == 0:
                return ([], [])

            income = tree.encode_name(tree.name_id_.get("Income", 0), "Income")
            expense = tree.encode_name(tree.name_id_.get("Expenses", 0), "Expenses")
            tree.links_.append([income, expense, str(tree.balance_map_.get("Expenses", 0))])

            if income_value < 0:
                profit_value = -income_value - expense_value
                if income_value < 0 and expense_value > 0 and profit_value > 0:
                    profit = tree.encode_name(801000000, "Profit")
                    tree.nodes_.add(profit)
                    tree.links_.append([income, profit, str(profit_value)])
            else:
                profit_value = income_value + expense_value
                if income_value > 0 and expense_value > 0 and profit_value > 0:
                    profit = tree.encode_name(801000000, "Profit")
                    tree.nodes_.add(profit)
                    tree.links_.append([income, profit, str(profit_value)])

            # for x in tree.links_:
            #     print(x)

            return (tree.nodes_, tree.links_)

        tree = SankeyTree(txn_entries, finalize=finalize, prune=prune, collapse=collapse, 
                          conversion=conversion, price_map=self.ledger.price_map)
        (nodes, links) = tree.run()

        import json
        json_node = json.dumps(list(nodes))
        json_link = json.dumps(links)
        yield {"nodes_ss": json_node, "links_ss": json_link}


    @staticmethod
    def can_plot_query(types: list[tuple[str, Any]]) -> bool:
        """Whether we can plot the given query.

        Args:
            types: The list of types returned by the BQL query.
        """
        return (
            len(types) == 2
            and types[0][1] in {str, date}
            and types[1][1] is Inventory
        )

    def query(
        self, types: list[tuple[str, Any]], rows: list[tuple[Any, ...]]
    ) -> Any:
        """Chart for a query.

        Args:
            types: The list of result row types.
            rows: The result rows.
        """

        if not self.can_plot_query(types):
            raise FavaAPIException("Can not plot the given chart.")
        if types[0][1] is date:
            return [
                {"date": date, "balance": units(inv)} for date, inv in rows
            ]
        return [{"group": group, "balance": units(inv)} for group, inv in rows]
