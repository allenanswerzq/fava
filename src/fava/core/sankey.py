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
    it runs opposite to the nodes' semantic column order.
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


def _account_tree_span(root: SerialisedTreeNode) -> int:
    """Return the deepest non-zero level relative to an account root."""
    root_depth = _account_depth(root.account)
    span = 0
    remaining = [root]
    while remaining:
        node = remaining.pop()
        if _sankey_balance(node.balance_children):
            span = max(span, _account_depth(node.account) - root_depth)
        remaining.extend(node.children)
    return span


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


def _add_account_tree(
    root: SerialisedTreeNode,
    *,
    root_column: int,
    column_step: Literal[-1, 1],
    nodes: dict[str, SankeyNode],
    links: dict[tuple[str, str], SimpleCounterInventory],
) -> Mapping[str, Decimal]:
    """Add an account hierarchy and return its signed root balance."""
    root_depth = _account_depth(root.account)

    def visit(node: SerialisedTreeNode) -> Mapping[str, Decimal]:
        child_values: list[
            tuple[SerialisedTreeNode, Mapping[str, Decimal]]
        ] = []
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
                    links,
                    source,
                    target,
                    currency,
                    abs(number),
                )
        return node.balance_children

    return visit(root)


def _connect_signed_balances(
    roots: Sequence[tuple[str, Mapping[str, Decimal]]],
    links: dict[tuple[str, str], SimpleCounterInventory],
    *,
    residual_source_id: str,
    residual_sink_id: str,
) -> tuple[SimpleCounterInventory, SimpleCounterInventory]:
    """Route signed root balances and return source and sink residuals."""
    residual_source = SimpleCounterInventory()
    residual_sink = SimpleCounterInventory()
    currencies = set().union(*(balance.keys() for _, balance in roots))
    for currency in sorted(currencies):
        signed_roots = tuple(
            (node_id, balance.get(currency, ZERO))
            for node_id, balance in roots
        )
        sources: list[tuple[str, Decimal]] = [
            (node_id, -number)
            for node_id, number in signed_roots
            if number < ZERO
        ]
        sinks: list[tuple[str, Decimal]] = [
            (node_id, number)
            for node_id, number in signed_roots
            if number > ZERO
        ]
        source_total = sum((value for _, value in sources), start=ZERO)
        sink_total = sum((value for _, value in sinks), start=ZERO)
        if source_total > sink_total:
            difference = source_total - sink_total
            residual_sink.add(currency, difference)
            sinks.append((residual_sink_id, difference))
        elif sink_total > source_total:
            difference = sink_total - source_total
            residual_source.add(currency, difference)
            sources.append((residual_source_id, difference))

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

    return residual_source, residual_sink


def _connect_root_balances(
    income_id: str,
    income: Mapping[str, Decimal],
    expense_id: str,
    expenses: Mapping[str, Decimal],
    links: dict[tuple[str, str], SimpleCounterInventory],
) -> tuple[SimpleCounterInventory, SimpleCounterInventory]:
    """Connect signed root balances and return profit and loss totals."""
    profit_id = "net-profit"
    loss_id = "net-loss"
    loss, profit = _connect_signed_balances(
        ((income_id, income), (expense_id, expenses)),
        links,
        residual_source_id=loss_id,
        residual_sink_id=profit_id,
    )
    return profit, loss


def build_income_statement_sankey(
    income: SerialisedTreeNode,
    expenses: SerialisedTreeNode,
) -> SankeyData:
    """Build an income-statement flow from two converted account trees.

    The complete non-zero hierarchy is preserved so the frontend can collapse
    dense branches adaptively and reveal them on demand. Values remain grouped
    by currency so the frontend can render one graph per currency.
    """
    nodes: dict[str, SankeyNode] = {}
    link_values: dict[tuple[str, str], SimpleCounterInventory] = {}

    income_root_column = _account_tree_span(income)
    expense_root_column = income_root_column + 1
    income_total = _add_account_tree(
        income,
        root_column=income_root_column,
        column_step=-1,
        nodes=nodes,
        links=link_values,
    )
    expense_total = _add_account_tree(
        expenses,
        root_column=expense_root_column,
        column_step=1,
        nodes=nodes,
        links=link_values,
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


def build_balance_sheet_sankey(
    assets: SerialisedTreeNode,
    liabilities: SerialisedTreeNode,
    equity: SerialisedTreeNode,
) -> SankeyData:
    """Build a balance-sheet flow from three converted account trees.

    Normal liability and equity balances fund the asset root from the left;
    the asset hierarchy then distributes that funding to the right. Contra
    balances retain their accounting direction and therefore draw backward.
    """
    nodes: dict[str, SankeyNode] = {}
    link_values: dict[tuple[str, str], SimpleCounterInventory] = {}

    liability_span = _account_tree_span(liabilities)
    equity_span = _account_tree_span(equity)
    funding_root_column = max(liability_span, equity_span)
    asset_root_column = funding_root_column + 1

    liability_total = _add_account_tree(
        liabilities,
        root_column=funding_root_column,
        column_step=-1,
        nodes=nodes,
        links=link_values,
    )
    equity_total = _add_account_tree(
        equity,
        root_column=funding_root_column,
        column_step=-1,
        nodes=nodes,
        links=link_values,
    )
    asset_total = _add_account_tree(
        assets,
        root_column=asset_root_column,
        column_step=1,
        nodes=nodes,
        links=link_values,
    )

    shortfall, surplus = _connect_signed_balances(
        (
            (_account_id(liabilities.account), liability_total),
            (_account_id(equity.account), equity_total),
            (_account_id(assets.account), asset_total),
        ),
        link_values,
        residual_source_id="balance-shortfall",
        residual_sink_id="balance-surplus",
    )
    if shortfall:
        nodes["balance-shortfall"] = SankeyNode(
            "balance-shortfall",
            None,
            "result",
            "balance_shortfall",
            funding_root_column,
            None,
            shortfall,
        )
    if surplus:
        nodes["balance-surplus"] = SankeyNode(
            "balance-surplus",
            None,
            "result",
            "balance_surplus",
            asset_root_column,
            None,
            surplus,
        )

    return SankeyData(
        tuple(sorted(nodes.values(), key=lambda node: node.id)),
        tuple(
            SankeyLink(source, target, value)
            for (source, target), value in sorted(link_values.items())
        ),
    )
