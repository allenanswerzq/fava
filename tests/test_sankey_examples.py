"""Focused end-to-end examples for Sankey chart data."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from fava.core import FavaLedger

if TYPE_CHECKING:
    from fava.core.inventory import SimpleCounterInventory
    from fava.core.sankey import SankeyData


EXAMPLES = Path(__file__).parent / "data" / "sankey"


def _ledger(name: str) -> FavaLedger:
    ledger = FavaLedger(str((EXAMPLES / name).resolve()))
    assert not ledger.errors
    return ledger


def _links(
    data: SankeyData,
) -> dict[tuple[str, str], SimpleCounterInventory]:
    return {(link.source, link.target): link.value for link in data.links}


def test_income_profit_example() -> None:
    ledger = _ledger("income-profit.beancount")
    data = ledger.charts.income_statement_sankey(
        ledger.get_filtered(),
        "USD",
    )
    nodes = {node.id: node for node in data.nodes}
    links = _links(data)

    assert nodes["net-profit"].balance == {"USD": Decimal(3000)}
    assert "net-loss" not in nodes
    assert "account:Income:Salary:Work" in nodes
    assert "account:Expenses:Food:Groceries" in nodes
    assert links[("account:Income", "account:Expenses")] == {
        "USD": Decimal(2500)
    }
    assert links[("account:Income", "net-profit")] == {"USD": Decimal(3000)}


def test_income_loss_and_contra_example() -> None:
    ledger = _ledger("income-loss-contra.beancount")
    data = ledger.charts.income_statement_sankey(
        ledger.get_filtered(),
        "USD",
    )
    nodes = {node.id: node for node in data.nodes}
    links = _links(data)

    assert nodes["net-loss"].balance == {"USD": Decimal(500)}
    assert "net-profit" not in nodes
    assert links[
        ("account:Income:Salary", "account:Income:Salary:Reversal")
    ] == {"USD": Decimal(300)}
    assert links[
        ("account:Expenses:Shopping:Refund", "account:Expenses:Shopping")
    ] == {"USD": Decimal(200)}
    assert links[("net-loss", "account:Expenses")] == {"USD": Decimal(500)}


def test_normal_balance_sheet_example() -> None:
    ledger = _ledger("balance-normal.beancount")
    data = ledger.charts.balance_sheet_sankey(
        ledger.get_filtered(),
        "USD",
    )
    nodes = {node.id: node for node in data.nodes}
    links = _links(data)

    assert "balance-shortfall" not in nodes
    assert "balance-surplus" not in nodes
    assert links[("account:Liabilities", "account:Assets")] == {
        "USD": Decimal(3000)
    }
    assert links[("account:Equity", "account:Assets")] == {
        "USD": Decimal(7000)
    }


def test_balance_sheet_contra_example() -> None:
    ledger = _ledger("balance-contra.beancount")
    data = ledger.charts.balance_sheet_sankey(
        ledger.get_filtered(),
        "USD",
    )
    links = _links(data)

    assert links[
        (
            "account:Assets:Receivables:Allowance",
            "account:Assets:Receivables",
        )
    ] == {"USD": Decimal(200)}
    assert links[("account:Liabilities", "account:Liabilities:Deposit")] == {
        "USD": Decimal(300)
    }
    assert all(
        value > 0 for link in data.links for value in link.value.values()
    )


def test_dense_income_example() -> None:
    ledger = _ledger("income-dense.beancount")
    data = ledger.charts.income_statement_sankey(
        ledger.get_filtered(),
        "USD",
    )

    living_children = [
        node
        for node in data.nodes
        if node.account is not None
        and node.account.startswith("Expenses:Living:Category")
    ]
    assert len(living_children) == 16
