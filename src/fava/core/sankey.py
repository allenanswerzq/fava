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
    """A node with layout metadata independent of its links.

    ``column`` fixes the semantic horizontal position of a node. Link direction
    does not affect that position, so a renderer can draw backward links for
    contra balances while keeping accounts in their expected columns.

    For example, an income-statement builder with account depth two produces::

        column 0       column 1       column 2       column 3

        Salary ------> Revenue ------> Costs --------> Housing
        Reversal <---- Revenue        Costs <--------- Refund
                           `---------> Net profit

    The shared node model is not specific to an income statement. A different
    builder, such as one for a balance sheet, can assign its own columns and
    result roles.

    Attributes:
        id: Stable identifier referenced by Sankey links.
        account: Full account name, or ``None`` for a calculated result.
        kind: Generic node type: an account or a calculated result.
        role: Optional builder-specific meaning, such as ``net_profit``.
        column: Zero-based semantic layout column from left to right.
        level: Account depth relative to its tree root, or ``None`` for a
            calculated result.
        balance: Absolute net balance by currency for labels and tooltips.
    """

    id: str
    account: str | None
    kind: Literal["account", "result"]
    role: str | None
    column: int
    level: int | None
    balance: SimpleCounterInventory


class SankeyLink(Struct, frozen=True):
    """A directed link with positive widths grouped by currency.

    ``source`` and ``target`` preserve the real accounting direction even when
    it runs opposite to the nodes' semantic column order. The renderer should
    use an arrow or chevron to make that direction explicit.
    """

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


def _add_link(
    links: dict[tuple[str, str], SimpleCounterInventory],
    source: str,
    target: str,
    currency: str,
    value: Decimal,
) -> None:
    if value > ZERO:
        links.setdefault(
            (source, target),
            SimpleCounterInventory(),
        ).add(currency, value)


def _connect_root_balances(
    income_id: str,
    income: Mapping[str, Decimal],
    expense_id: str,
    expenses: Mapping[str, Decimal],
    links: dict[tuple[str, str], SimpleCounterInventory],
) -> tuple[SimpleCounterInventory, SimpleCounterInventory]:
    """Connect signed root balances and return profit and loss totals."""
    profit = SimpleCounterInventory()
    loss = SimpleCounterInventory()
    profit_id = "net-profit"
    loss_id = "net-loss"
    for currency in sorted(income.keys() | expenses.keys()):
        roots = (
            (income_id, income.get(currency, ZERO)),
            (expense_id, expenses.get(currency, ZERO)),
        )
        sources: list[tuple[str, Decimal]] = [
            (node_id, -number)
            for node_id, number in roots
            if number < ZERO
        ]
        sinks: list[tuple[str, Decimal]] = [
            (node_id, number)
            for node_id, number in roots
            if number > ZERO
        ]
        source_total = sum((value for _, value in sources), start=ZERO)
        sink_total = sum((value for _, value in sinks), start=ZERO)
        if source_total > sink_total:
            difference = source_total - sink_total
            profit.add(currency, difference)
            sinks.append((profit_id, difference))
        elif sink_total > source_total:
            difference = sink_total - source_total
            loss.add(currency, difference)
            sources.append((loss_id, difference))

        source_index = 0
        sink_index = 0
        while source_index < len(sources) and sink_index < len(sinks):
            source_id, source_value = sources[source_index]
            sink_id, sink_value = sinks[sink_index]
            value = min(source_value, sink_value)
            _add_link(links, source_id, sink_id, currency, value)
            sources[source_index] = (source_id, source_value - value)
            sinks[sink_index] = (sink_id, sink_value - value)
            if sources[source_index][1] == ZERO:
                source_index += 1
            if sinks[sink_index][1] == ZERO:
                sink_index += 1

    return profit, loss


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
    link_values: dict[tuple[str, str], SimpleCounterInventory] = {}

    def add_account_tree(
        root: SerialisedTreeNode,
        *,
        account_type: Literal["income", "expense"],
        max_depth: int,
        root_column: int,
        column_step: Literal[-1, 1],
    ) -> Mapping[str, Decimal]:
        root_depth = _account_depth(root.account)
        if max_depth < root_depth:
            msg = (
                f"Sankey {account_type} depth {max_depth} is above root "
                f"account `{root.account}` at depth {root_depth}."
            )
            raise ValueError(msg)

        def visit(node: SerialisedTreeNode) -> Mapping[str, Decimal]:
            child_values: list[
                tuple[SerialisedTreeNode, Mapping[str, Decimal]]
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
            if not node_balance and not child_values:
                return node.balance_children
            node_id = _account_id(node.account)
            nodes[node_id] = SankeyNode(
                node_id,
                node.account,
                "account",
                None,
                root_column
                + column_step * (_account_depth(node.account) - root_depth),
                _account_depth(node.account) - root_depth,
                node_balance,
            )
            for child, value in child_values:
                child_id = _account_id(child.account)
                for currency, number in value.items():
                    source, target = (
                        (child_id, node_id)
                        if number < ZERO
                        else (node_id, child_id)
                    )
                    _add_link(
                        link_values,
                        source,
                        target,
                        currency,
                        abs(number),
                    )
            return node.balance_children

        return visit(root)

    income_root_column = income_depth - _account_depth(income.account)
    expense_root_column = income_root_column + 1
    income_total = add_account_tree(
        income,
        account_type="income",
        max_depth=income_depth,
        root_column=income_root_column,
        column_step=-1,
    )
    expense_total = add_account_tree(
        expenses,
        account_type="expense",
        max_depth=expense_depth,
        root_column=expense_root_column,
        column_step=1,
    )

    income_id = _account_id(income.account)
    expense_id = _account_id(expenses.account)
    profit, loss = _connect_root_balances(
        income_id,
        income_total,
        expense_id,
        expense_total,
        link_values,
    )
    if profit:
        nodes["net-profit"] = SankeyNode(
            "net-profit",
            None,
            "result",
            "net_profit",
            expense_root_column,
            None,
            profit,
        )
    if loss:
        nodes["net-loss"] = SankeyNode(
            "net-loss",
            None,
            "result",
            "net_loss",
            income_root_column,
            None,
            loss,
        )

    return SankeyData(
        tuple(sorted(nodes.values(), key=lambda node: node.id)),
        tuple(
            SankeyLink(source, target, value)
            for (source, target), value in sorted(link_values.items())
        ),
    )
