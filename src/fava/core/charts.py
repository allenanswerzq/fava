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
    def linechanges(
        self, filtered: FilteredLedger, account_name: str, conversion: str
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
            c = change.to_string().split(' ')[0].split('(')[1]
            assert len(c)
            yield DateAndBalance(entry.date, {"CNY" : Decimal(c)})


    @listify
    def linechart(
        self, filtered: FilteredLedger, account_name: str, conversion: str
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
    def sankey_account(
        self, filtered: FilteredLedger, interval: Interval, conversion: str
    ) -> Generator[DateAndBalance, None, None]:
        import csv
        file = "/Users/zqjxw73/guava/temp/budget.csv" # todo
        mp = {}
        with open(file) as f:
            for index, row in enumerate(csv.DictReader(f)):
                if row["First"] != '':
                    cur = ""
                    for i, k in enumerate(row.values()):
                        if len(k) == 0: break
                        if i > 0: cur += ":"
                        cur += k
                        if cur not in mp: mp[cur] = 0
                        mp[cur] += 1

        root = "Account"
        nodes = set()
        links = []
        nodes.add(root)
        for k, v in mp.items():
            t = k.split(":")
            if len(t) == 1:
                nodes.add(t[0])
                links.append([root, k, str(v)])
                # print(f"Account [{v}] {t[0]}")
            else:
                # print(f"{t[-2]} [{v}] {t[-1]}")
                nodes.add(k)
                links.append([":".join(x for x in t[:-1]), k, str(v)])

        import json

        json_node = json.dumps(list(nodes))
        json_link = json.dumps(links)
        yield {"nodes_ss": json_node, "links_ss": json_link}

    @listify
    def two_sides(self, filtered: FilteredLedger, interval: Interval, conversion: str) -> Generator[DateAndBalance, None, None]:
        transactions = (
            entry
            for entry in filtered.entries
            if (
                isinstance(entry, Transaction)
                and entry.flag != FLAG_UNREALIZED
            )
        )

        root = realization.realize(transactions)
        children = realization.iter_children(root)
        balance_map = {}
        for child in children:
            t = realization.compute_balance(child)
            balance_map[child.account] = abs(t.get_currency_units("CNY").number)

        assets = []
        others = []
        for k, v in balance_map.items():
            if v <= 0: continue
            if "Income" in k: continue
            if "Expenses" in k: continue
            if "-Balance" in k: continue

            if "Assets" in k:
                if len(k.split(":")) == 2:
                    assets.append({"account":k, "value" : str(v)})
            else:
                print(k)
                assert "Income" not in k, "{}".format(k)
                if len(k.split(":")) == 2:
                    others.append({"account":k, "value" : str(v)})

        # print(assets)
        # print("\n\n\n")
        # print(others)

        import json
        assets_ss = json.dumps(assets)
        others_ss = json.dumps(others)
        yield {"assets_ss": assets_ss, "others_ss": others_ss}


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

        assets_stat = dict()
        liabilities_stat = dict()
        def prune(edge: SankeyTreeEdge):
            # For income statement
            if len(edge.u) == 0:
                # prune out edge not from root -> income/expenses
                return edge.v not in ("Assets", "Liabilities")

            # Add weight prune to avoid too many branches
            u, v = edge.u, edge.v
            if "Assets" in edge.u:
                # "assets" -> "assets:a:b"
                # "liabilities" -> "liabilities:a:b"
                u, v = v, u

            level = len(v.split(":"))
            if "Assets" in v:
                level_max = max(edge.weight, assets_stat.get(level, 0))
                assets_stat[level] = level_max
            else:
                level_max = max(edge.weight, liabilities_stat.get(level, 0))
                liabilities_stat[level] = level_max

            ratio = edge.weight / level_max
            # print(u, v, level, ratio)

            if "Liabilities" in v and ratio < 0.04:
                return True

            if "Assets" in v and ratio < 0.004:
                return True

            return False

        def collapse(edge: SankeyTreeEdge):
            if "Investment" in edge.v and len(edge.v.split(":")) >= 4:
                return True

            if "Liabilities" in edge.v and len(edge.v.split(":")) >= 3:
                return True

            return False

        def finalize(tree: SankeyTree):
            assets = tree.encode_name(tree.name_id_["Assets"], "Assets")
            liabilities = tree.encode_name(tree.name_id_["Liabilities"], "Liabilities")
            tree.links_.append([assets, liabilities, str(tree.balance_map_["Liabilities"])])

            for x in tree.links_:
                print(x)

            return (tree.nodes_, tree.links_)

        tree = SankeyTree(txn_entries, finalize=finalize, prune=prune, collapse=collapse)
        (nodes, links) = tree.run()

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

        income_stat = dict()
        expenses_stat = dict()
        total_prune_income = 0
        total_prune_expenses = 0
        def prune(edge: SankeyTreeEdge):
            # For income statement
            if len(edge.u) == 0:
                # prune out edge not from root -> income/expenses
                return edge.v not in ("Income", "Expenses")

            if "-Balance" in edge.v: return True
            if "Company" in edge.v: return True
            if "Hospital:" in edge.v: return True

            # Add weight prune to avoid too many branches
            u, v = edge.u, edge.v
            if "Income" in edge.u:
                # "income" -> "income:a:b"
                # "expense" -> "expense:a:b"
                u, v = v, u

            level = len(v.split(":"))
            if "Income" in v:
                level_max = max(edge.weight, income_stat.get(level, 0))
                income_stat[level] = level_max
            else:
                level_max = max(edge.weight, expenses_stat.get(level, 0))
                expenses_stat[level] = level_max

            ratio = edge.weight / level_max
            # print(u, v, level, ratio)

            if "Expenses" in v and level > 2 and ratio < 0.04:
                nonlocal total_prune_expenses
                total_prune_expenses += edge.weight
                return True

            if "Income" in v and ratio < 0.004:
                nonlocal total_prune_income
                total_prune_income += edge.weight
                return True


            return False


        def collapse(edge: SankeyTreeEdge):
            if "Transport" in edge.v and len(edge.v.split(":")) > 2:
                # Collapse Expense:Transport:* account
                return True

            if "Expenses" in edge.v and len(edge.v.split(":")) > 3:
                return True

            if "Income" in edge.u and len(edge.u.split(":")) >= 2:
                return True

            return False

        def finalize(tree: SankeyTree):
            income = tree.encode_name(tree.name_id_["Income"], "Income")
            expense = tree.encode_name(tree.name_id_["Expenses"], "Expenses")
            tree.links_.append([income, expense, str(tree.balance_map_["Expenses"])])

            # for x in tree.links_:
            #     print(x)

            return (tree.nodes_, tree.links_)

        tree = SankeyTree(txn_entries, finalize=finalize, prune=prune, collapse=collapse)
        (nodes, links) = tree.run()

        import json
        json_node = json.dumps(list(nodes))
        json_link = json.dumps(links)
        yield {"nodes_ss": json_node, "links_ss": json_link}


    @listify
    def sankey_diagram(
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

        root = realization.realize(txn_entries)
        balance_map = {}
        balance_map["Income"] = 0
        balance_map["Expenses"] = 0
        balance_map["Savings"] = 0
        children = realization.iter_children(root)
        total_usd_inventory = None
        for child in children:
            t = realization.compute_balance(child)
            # if t.get_currency_units("USD").number != 0 and child.account == "Income":
            #     total_usd_inventory = t
            balance_map[child.account] = abs(t.get_currency_units("CNY").number)

        def get_dollor(inv):
            if inv is None: return (Decimal('0'), Decimal('0'))
            usd = inv.get_currency_units("USD").number
            before = inv.get_currency_units("CNY").number
            after = inv_to_dict(cost_or_value(inv, "CNY", self.ledger.price_map))["CNY"]
            return (abs(usd), abs(after - before))

        usd, cny = get_dollor(total_usd_inventory)
        realization.add_account_node(root, "Income", "USD", cny)

        realization.add_account_node(root, "Connector", "Expenses", balance_map["Expenses"])
        savings = (balance_map["Income"] - balance_map["Expenses"] + cny)
        if savings > 0:
            balance_map["Savings"] = savings
            realization.add_account_node(root, "", "Savings", 0)
            realization.add_account_node(root, "Connector", "Savings", savings)

        if balance_map["Income"] < 10:
            # Fake income to make rendering sankey graph work correct
            realization.add_account_node(root, "Income", "Fake", 1)

        children = realization.iter_children(root)
        for child in children:
            t = realization.compute_balance(child)
            balance_map[child.account] = abs(t.get_currency_units("CNY").number)

        def check_account(u, v):
            # Whether include this account in the sankey graph.
            types = (
                self.ledger.options["name_income"],
                self.ledger.options["name_expenses"],
                # "SocialSecurity",
                "Connector",
                "Savings"
            )
            if len(u) == 0: return (v in types)
            return (
                   ("-Balance" not in v) and
                   ("Company" not in v) and
                   ("Hospital:" not in v) and
                   (
                    ("Expenses" in v and len(v.split(":")) <= 3) or
                    (len(v.split(":")) <= 2)
                   )
            )

        id_map = {}
        nodes = set()
        links = []
        mx = 0
        small_income = 0
        def dfs(real_account, id=100, pre=None):
            # print("DFS", real_account.account, pre)
            nonlocal id_map
            nonlocal mx
            id_map[real_account.account] = id
            cur = []
            for _, real_child in sorted(real_account.items()):
                v = real_child.account
                if check_account(real_account.account, v):
                    if v in balance_map:
                        w = balance_map[v]
                    else:
                        w = balance_map[v.split(':')[1]]
                    mx = max(mx, w)
                    cur.append([v, w, real_child])

            cur.sort(key=lambda x: (x[1], x[0]), reverse=True)
            for i, x in enumerate(cur):
                u = str(id) + "_" + real_account.account
                v = str(id * 100 + i) + "_" + x[0]
                w = str(x[1])
                id_map[x[0]] = id * 100 + i
                if real_account.account.startswith("Income"):
                    u, v = (v, u)  # swap accounts

                # NOTE: Prune links that are less than a percent
                if mx > 0:
                    ratio = x[1] / mx
                    level = len(v.split(":"))

                    if "Expenses" in v and level > 2 and ratio < 0.004:
                        continue

                    if "Income" in v and ratio < 0.001:
                        if len(u.split(":")) == 2:
                            nonlocal small_income
                            small_income += x[1]
                        else:
                            print(f"Ignore very samll income {u}")
                        continue

                # Collapse Expense:Transport:* account
                if "Transport" in v and len(v.split(":")) > 2:
                    continue

                # u --> v
                if pre is not None and x[1] > 0:
                    if "Connector" not in u:
                        nodes.add(u)
                        nodes.add(v)

                    links.append([u, v, str(w)])

            # print(real_account.account, id_map)

            for x in cur:
                dfs(x[2], id=id_map[x[0]], pre=real_account.account)

        dfs(root)

        nodes.add("800020101_Income:SmallIncome")
        links.append(
            ["800020101_Income:SmallIncome",
              str(id_map["Income"]) + "_" + "Income", str(small_income)])

        # print(nodes)
        # for x in links:
        #     print(x)

        for x in links:
            if "Connector" in x[0] and "Income" in id_map:
                x[0] = str(id_map["Income"]) + "_" + "Income"
                r = ''.join(s for s in x[1].split(':')[1])
                x[1] = str(id_map[r]) + "_" + r
                nodes.add(x[1])

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
