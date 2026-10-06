from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from fava.core import FavaLedger
from fava.core.conversion import AT_COST
from fava.core.inventory import SimpleCounterInventory
from fava.core.sankey import build_income_statement_sankey
from fava.core.tree import SerialisedTreeNode
from fava.util.date import Day
from fava.util.date import Month

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from .conftest import GetFavaLedger
    from .conftest import SnapshotFunc


def test_interval_totals(
    small_example_ledger: FavaLedger,
    snapshot: SnapshotFunc,
) -> None:
    filtered = small_example_ledger.get_filtered()
    for conversion in ["at_cost", "USD"]:
        data = small_example_ledger.charts.interval_totals(
            filtered,
            Month,
            "Expenses",
            conversion,
        )
        snapshot(data, json=True)


def test_interval_totals_inverted(
    small_example_ledger: FavaLedger,
    snapshot: SnapshotFunc,
) -> None:
    filtered = small_example_ledger.get_filtered()
    for conversion in ["at_cost", "USD"]:
        data = small_example_ledger.charts.interval_totals(
            filtered,
            Month,
            "Expenses",
            conversion,
            invert=True,
        )
        snapshot(data, json=True)


def test_linechart_data(
    example_ledger: FavaLedger,
    snapshot: SnapshotFunc,
) -> None:
    filtered = example_ledger.get_filtered()
    for conversion in ["at_cost", "units", "at_value", "USD"]:
        data = example_ledger.charts.linechart(
            filtered,
            "Assets:Testing:MultipleCommodities",
            conversion,
        )
        snapshot(data, json=True)

    assert not example_ledger.charts.linechart(
        filtered,
        "Assets:Testing:MultipleCommodities:NotAnAccount",
        "units",
    )


def test_net_worth(example_ledger: FavaLedger, snapshot: SnapshotFunc) -> None:
    filtered = example_ledger.get_filtered()
    data = example_ledger.charts.net_worth(filtered, Month, "USD")
    snapshot(data, json=True)


def test_net_worth_off_by_one(
    snapshot: SnapshotFunc,
    get_ledger: GetFavaLedger,
) -> None:
    off_by_one = get_ledger("off-by-one")
    off_by_one_filtered = off_by_one.get_filtered()
    assert not off_by_one.errors
    assert len(off_by_one_filtered.entries) == 9

    for interval in [Day, Month]:
        data = off_by_one.charts.net_worth(
            off_by_one_filtered,
            interval,
            "at_value",
        )
        assert len(data) == 4 if interval == Day else 1
        snapshot(data, json=True)


def test_hierarchy(example_ledger: FavaLedger) -> None:
    filtered = example_ledger.get_filtered()

    data = example_ledger.charts.hierarchy(filtered, "Assets", AT_COST)
    assert data.balance_children == {
        "IRAUSD": Decimal("7200.00"),
        "USD": Decimal("94320.27840"),
        "VACHR": Decimal(-82),
    }
    assert data.balance == {}
    etrade = data.children[1].children[2]
    assert etrade.account == "Assets:US:ETrade"
    assert etrade.balance_children == {"USD": Decimal("23137.54")}


def test_income_statement_sankey(example_ledger: FavaLedger) -> None:
    """Income statement Sankey data uses the filtered converted tree."""
    filtered = example_ledger.get_filtered()

    data = example_ledger.charts.income_statement_sankey(filtered, "USD")

    node_ids = {node.id for node in data.nodes}
    assert "account:Income" in node_ids
    assert "account:Expenses" in node_ids
    assert data.links
    assert all(
        number > 0 for link in data.links for number in link.value.values()
    )


def test_income_statement_sankey_converts_before_building(
    tmp_path: Path,
) -> None:
    """EUR and USD balances are combined after a one-to-one conversion."""
    ledger_path = tmp_path / "sankey-conversion.beancount"
    ledger_path.write_text(
        """
option "operating_currency" "USD"

2024-01-01 open Assets:Cash EUR,USD
2024-01-01 open Income:Salary EUR,USD
2024-01-01 open Expenses:Housing EUR,USD
2024-01-01 price EUR 1 USD

2024-01-02 * "EUR income"
  Assets:Cash       50 EUR
  Income:Salary    -50 EUR

2024-01-02 * "USD income"
  Assets:Cash      100 USD
  Income:Salary   -100 USD

2024-01-03 * "EUR expense"
  Assets:Cash         -80 EUR
  Expenses:Housing     80 EUR

2024-01-03 * "USD expense"
  Assets:Cash         -70 USD
  Expenses:Housing     70 USD
""".lstrip(),
        encoding="utf-8",
    )
    ledger = FavaLedger(str(ledger_path))
    assert not ledger.errors

    data = ledger.charts.income_statement_sankey(
        ledger.get_filtered(),
        "USD",
    )
    nodes = {node.id: node for node in data.nodes}
    links = {(link.source, link.target): link.value for link in data.links}

    assert nodes["account:Income:Salary"].balance == {"USD": Decimal(150)}
    assert nodes["account:Expenses:Housing"].balance == {"USD": Decimal(150)}
    assert "net-profit" not in nodes
    assert "net-loss" not in nodes
    assert links[("account:Income", "account:Expenses")] == {
        "USD": Decimal(150)
    }


def test_build_income_statement_sankey() -> None:
    """Depth two accumulates deeper accounts before making widths positive."""
    income_grandchild = SerialisedTreeNode(
        "Revenue:Salary:Work",
        SimpleCounterInventory({"EUR": Decimal(-50), "USD": Decimal(-100)}),
        SimpleCounterInventory({"EUR": Decimal(-50), "USD": Decimal(-100)}),
        (),
        has_txns=True,
    )
    income_child = SerialisedTreeNode(
        "Revenue:Salary",
        SimpleCounterInventory(),
        SimpleCounterInventory({"EUR": Decimal(-50), "USD": Decimal(-100)}),
        (income_grandchild,),
        has_txns=False,
    )
    income = SerialisedTreeNode(
        "Revenue",
        SimpleCounterInventory(),
        SimpleCounterInventory({"EUR": Decimal(-50), "USD": Decimal(-100)}),
        (income_child,),
        has_txns=False,
    )
    rent = SerialisedTreeNode(
        "Costs:Housing:Rent",
        SimpleCounterInventory({"EUR": Decimal(80), "USD": Decimal(70)}),
        SimpleCounterInventory({"EUR": Decimal(80), "USD": Decimal(70)}),
        (),
        has_txns=True,
    )
    housing = SerialisedTreeNode(
        "Costs:Housing",
        SimpleCounterInventory(),
        SimpleCounterInventory({"EUR": Decimal(80), "USD": Decimal(70)}),
        (rent,),
        has_txns=False,
    )
    expenses = SerialisedTreeNode(
        "Costs",
        SimpleCounterInventory(),
        SimpleCounterInventory({"EUR": Decimal(80), "USD": Decimal(70)}),
        (housing,),
        has_txns=False,
    )

    data = build_income_statement_sankey(income, expenses)
    nodes = {node.id: node for node in data.nodes}
    links = {(link.source, link.target): link.value for link in data.links}

    assert nodes["account:Revenue"].account == "Revenue"
    assert "account:Revenue:Salary:Work" not in nodes
    assert "account:Costs:Housing:Rent" not in nodes
    assert nodes["net-profit"].balance == {"USD": Decimal(30)}
    assert nodes["net-loss"].balance == {"EUR": Decimal(30)}
    assert links[("account:Revenue:Salary", "account:Revenue")] == {
        "EUR": Decimal(50),
        "USD": Decimal(100),
    }
    assert links[("account:Revenue", "account:Costs")] == {
        "EUR": Decimal(50),
        "USD": Decimal(70),
    }
    assert links[("account:Revenue", "net-profit")] == {"USD": Decimal(30)}
    assert links[("net-loss", "account:Costs")] == {"EUR": Decimal(30)}
    assert links[("account:Costs", "account:Costs:Housing")] == {
        "EUR": Decimal(80),
        "USD": Decimal(70),
    }

    deeper = build_income_statement_sankey(
        income,
        expenses,
        income_depth=3,
        expense_depth=3,
    )
    deeper_links = {
        (link.source, link.target): link.value for link in deeper.links
    }
    assert deeper_links[
        ("account:Revenue:Salary:Work", "account:Revenue:Salary")
    ] == {"EUR": Decimal(50), "USD": Decimal(100)}
    assert deeper_links[
        ("account:Costs:Housing", "account:Costs:Housing:Rent")
    ] == {"EUR": Decimal(80), "USD": Decimal(70)}


def test_build_income_statement_sankey_routes_balances_by_sign() -> None:
    """Normal and contra balances coexist in one signed Sankey graph."""
    salary = SerialisedTreeNode(
        "Revenue:Salary",
        SimpleCounterInventory({"USD": Decimal(-100)}),
        SimpleCounterInventory({"USD": Decimal(-100)}),
        (),
        has_txns=True,
    )
    reversal = SerialisedTreeNode(
        "Revenue:Reversal",
        SimpleCounterInventory({"USD": Decimal(20)}),
        SimpleCounterInventory({"USD": Decimal(20)}),
        (),
        has_txns=True,
    )
    income = SerialisedTreeNode(
        "Revenue",
        SimpleCounterInventory(),
        SimpleCounterInventory({"USD": Decimal(-80)}),
        (reversal, salary),
        has_txns=False,
    )
    housing = SerialisedTreeNode(
        "Costs:Housing",
        SimpleCounterInventory({"USD": Decimal(70)}),
        SimpleCounterInventory({"USD": Decimal(70)}),
        (),
        has_txns=True,
    )
    refund = SerialisedTreeNode(
        "Costs:Refund",
        SimpleCounterInventory({"USD": Decimal(-10)}),
        SimpleCounterInventory({"USD": Decimal(-10)}),
        (),
        has_txns=True,
    )
    expenses = SerialisedTreeNode(
        "Costs",
        SimpleCounterInventory(),
        SimpleCounterInventory({"USD": Decimal(60)}),
        (housing, refund),
        has_txns=False,
    )

    data = build_income_statement_sankey(income, expenses)
    nodes = {node.id: node for node in data.nodes}
    links = {(link.source, link.target): link.value for link in data.links}

    assert links[("account:Revenue:Salary", "account:Revenue")] == {
        "USD": Decimal(100)
    }
    assert links[("account:Revenue", "account:Revenue:Reversal")] == {
        "USD": Decimal(20)
    }
    assert links[("account:Costs", "account:Costs:Housing")] == {
        "USD": Decimal(70)
    }
    assert links[("account:Costs:Refund", "account:Costs")] == {
        "USD": Decimal(10)
    }
    assert links[("account:Revenue", "account:Costs")] == {"USD": Decimal(60)}
    assert links[("account:Revenue", "net-profit")] == {"USD": Decimal(20)}
    assert nodes["net-profit"].balance == {"USD": Decimal(20)}
    assert "net-loss" not in nodes
    assert nodes["account:Revenue"].kind == "account"
    assert nodes["account:Revenue"].role is None
    assert nodes["account:Revenue"].column == 1
    assert nodes["account:Revenue"].level == 0
    assert nodes["account:Revenue:Salary"].column == 0
    assert nodes["account:Revenue:Salary"].level == 1
    assert nodes["account:Costs"].column == 2
    assert nodes["account:Costs"].level == 0
    assert nodes["account:Costs:Housing"].column == 3
    assert nodes["account:Costs:Housing"].level == 1
    assert nodes["net-profit"].kind == "result"
    assert nodes["net-profit"].role == "net_profit"
    assert nodes["net-profit"].column == 2
    assert nodes["net-profit"].level is None
    assert all(
        number > 0 for link in data.links for number in link.value.values()
    )
    for node_id, expected in [
        ("account:Revenue", Decimal(100)),
        ("account:Costs", Decimal(70)),
    ]:
        incoming = sum(
            (
                link.value.get("USD", Decimal())
                for link in data.links
                if link.target == node_id
            ),
            start=Decimal(),
        )
        outgoing = sum(
            (
                link.value.get("USD", Decimal())
                for link in data.links
                if link.source == node_id
            ),
            start=Decimal(),
        )
        assert incoming == outgoing == expected


def test_build_empty_income_statement_sankey() -> None:
    """An empty income statement produces an empty graph."""
    empty_income = SerialisedTreeNode(
        "Revenue",
        SimpleCounterInventory(),
        SimpleCounterInventory(),
        (),
        has_txns=False,
    )
    empty_expenses = SerialisedTreeNode(
        "Costs",
        SimpleCounterInventory(),
        SimpleCounterInventory(),
        (),
        has_txns=False,
    )

    data = build_income_statement_sankey(empty_income, empty_expenses)

    assert not data.nodes
    assert not data.links


def test_interval_totals_sibling_with_shared_prefix(
    small_example_ledger: FavaLedger,
) -> None:
    """Accounts that merely share a name prefix are not children."""
    filtered = small_example_ledger.get_filtered()

    for interval in small_example_ledger.charts.interval_totals(
        filtered, Month, "Expenses:Other", "EUR"
    ):
        assert not interval.balance
        assert not interval.account_balances

    for interval in small_example_ledger.charts.interval_totals(
        filtered, Month, "Expenses:Others", "EUR"
    ):
        assert set(interval.account_balances) == {"Expenses:Others"}
