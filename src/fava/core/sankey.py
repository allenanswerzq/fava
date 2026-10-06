"""Build typed data for Sankey charts."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from msgspec import Struct

from fava.core.inventory import SimpleCounterInventory

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping
    from collections.abc import Sequence
    from typing import Literal

    from fava.core.tree import SerialisedTreeNode


ZERO = Decimal()


class SankeyNode(Struct, frozen=True):
    """A node in a Sankey chart."""

    id: str
    account: str | None
    kind: Literal["account", "net_profit", "net_loss"]
    balance: SimpleCounterInventory


class SankeyLink(Struct, frozen=True):
    """A directed link in a Sankey chart."""

    source: str
    target: str
    value: SimpleCounterInventory


class SankeyData(Struct, frozen=True):
    """The nodes and links for a Sankey chart."""

    nodes: Sequence[SankeyNode]
    links: Sequence[SankeyLink]


def _account_id(account: str) -> str:
    return f"account:{account}"


def _sankey_balance(
    balance: Mapping[str, Decimal],
) -> SimpleCounterInventory:
    """Return the absolute values required for positive Sankey widths."""
    result = SimpleCounterInventory()
    for currency, number in balance.items():
        if number != ZERO:
            result[currency] = abs(number)
    return result


def _account_depth(account: str) -> int:
    return account.count(":") + 1


def _split_totals(
    income: Mapping[str, Decimal],
    expenses: Mapping[str, Decimal],
) -> tuple[
    SimpleCounterInventory,
    SimpleCounterInventory,
    SimpleCounterInventory,
]:
    """Split totals into spending, net profit, and net loss."""
    spending = SimpleCounterInventory()
    profit = SimpleCounterInventory()
    loss = SimpleCounterInventory()
    for currency in sorted(income.keys() | expenses.keys()):
        income_number = income.get(currency, ZERO)
        expense_number = expenses.get(currency, ZERO)
        shared = min(income_number, expense_number)
        if shared > ZERO:
            spending[currency] = shared
        if income_number > expense_number:
            profit[currency] = income_number - expense_number
        elif expense_number > income_number:
            loss[currency] = expense_number - income_number
    return spending, profit, loss


def build_income_statement_sankey(
    income: SerialisedTreeNode,
    expenses: SerialisedTreeNode,
    *,
    income_depth: int = 2,
    expense_depth: int = 2,
) -> SankeyData:
    """Build an income-statement flow from two converted account trees.

    Accounts are included down to the configured absolute account depth.
    Values remain grouped by currency so the frontend can render one graph per
    currency.
    """
    nodes: dict[str, SankeyNode] = {}
    links: dict[tuple[str, str], SankeyLink] = {}

    def add_account_tree(
        root: SerialisedTreeNode,
        *,
        account_type: Literal["income", "expense"],
        max_depth: int,
        towards_root: bool,
    ) -> SimpleCounterInventory:
        root_depth = _account_depth(root.account)
        if max_depth < root_depth:
            msg = (
                f"Sankey {account_type} depth {max_depth} is above root "
                f"account `{root.account}` at depth {root_depth}."
            )
            raise ValueError(msg)

        def visit(node: SerialisedTreeNode) -> SimpleCounterInventory:
            child_values: list[
                tuple[SerialisedTreeNode, SimpleCounterInventory]
            ] = []
            if _account_depth(node.account) < max_depth:
                for child in sorted(
                    node.children,
                    key=lambda item: item.account,
                ):
                    child_value = visit(child)
                    if child_value:
                        child_values.append((child, child_value))

            node_balance = _sankey_balance(node.balance_children)
            if not node_balance:
                return node_balance
            node_id = _account_id(node.account)
            nodes[node_id] = SankeyNode(
                node_id,
                node.account,
                "account",
                node_balance,
            )
            for child, value in child_values:
                child_id = _account_id(child.account)
                source, target = (
                    (child_id, node_id)
                    if towards_root
                    else (node_id, child_id)
                )
                links[(source, target)] = SankeyLink(
                    source,
                    target,
                    value,
                )
            return node_balance

        return visit(root)

    income_total = add_account_tree(
        income,
        account_type="income",
        max_depth=income_depth,
        towards_root=True,
    )
    expense_total = add_account_tree(
        expenses,
        account_type="expense",
        max_depth=expense_depth,
        towards_root=False,
    )

    spending, profit, loss = _split_totals(income_total, expense_total)
    income_id = _account_id(income.account)
    expense_id = _account_id(expenses.account)
    if spending:
        links[(income_id, expense_id)] = SankeyLink(
            income_id,
            expense_id,
            spending,
        )
    if profit:
        profit_id = "net-profit"
        nodes[profit_id] = SankeyNode(profit_id, None, "net_profit", profit)
        links[(income_id, profit_id)] = SankeyLink(
            income_id,
            profit_id,
            profit,
        )
    if loss:
        loss_id = "net-loss"
        nodes[loss_id] = SankeyNode(loss_id, None, "net_loss", loss)
        links[(loss_id, expense_id)] = SankeyLink(
            loss_id,
            expense_id,
            loss,
        )

    return SankeyData(
        tuple(sorted(nodes.values(), key=lambda node: node.id)),
        tuple(
            sorted(links.values(), key=lambda link: (link.source, link.target))
        ),
    )
