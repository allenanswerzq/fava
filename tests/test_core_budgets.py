"""Fava's budget syntax."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from fava.core.budgets import _plan_status
from fava.core.budgets import BudgetPlan
from fava.core.budgets import calculate_budget
from fava.core.budgets import calculate_budget_children
from fava.core.budgets import parse_budget_plans
from fava.core.budgets import parse_budgets
from fava.util.date import END_OF_YEAR

if TYPE_CHECKING:  # pragma: no cover
    from fava.beans.abc import Custom
    from fava.core.budgets import BudgetDict


def test_budgets(load_doc_custom_entries: list[Custom]) -> None:
    """
    2016-01-01 custom "budget" Expenses:Groceries "weekly" 100.00 CNY
    2016-06-01 custom "budget" Expenses:Groceries "weekly"  10.00 EUR
    2016-06-01 custom "budget" Expenses:Groceries "asdfasdf"  10.00 EUR
    2016-01-01 custom "budget" Expenses:Groceries "weekly"
    2016-06-01 custom "budget" Expenses:Groceries 10.00 EUR
    """
    budgets, errors = parse_budgets(load_doc_custom_entries, END_OF_YEAR)

    assert len(errors) == 3

    empty = calculate_budget(
        budgets,
        "Expenses",
        date(2016, 6, 1),
        date(2016, 6, 8),
    )
    assert not empty

    budgets_ = calculate_budget(
        budgets,
        "Expenses:Groceries",
        date(2016, 6, 1),
        date(2016, 6, 8),
    )

    assert budgets_["CNY"] == Decimal(100)
    assert budgets_["EUR"] == Decimal(10)


def test_budgets_daily(budgets_doc: BudgetDict) -> None:
    """
    2016-05-01 custom "budget" Expenses:Books "daily" 2.5 EUR"""

    assert "EUR" not in calculate_budget(
        budgets_doc,
        "Expenses:Books",
        date(2010, 2, 1),
        date(2010, 2, 2),
    )

    for start, end, num in [
        (date(2016, 5, 1), date(2016, 5, 2), Decimal("2.5")),
        (date(2016, 5, 1), date(2016, 5, 3), Decimal("5.0")),
        (date(2016, 9, 2), date(2016, 9, 3), Decimal("2.5")),
        (date(2018, 12, 31), date(2019, 1, 1), Decimal("2.5")),
    ]:
        budget = calculate_budget(budgets_doc, "Expenses:Books", start, end)
        assert budget["EUR"] == num


def test_budgets_weekly(budgets_doc: BudgetDict) -> None:
    """
    2016-05-01 custom "budget" Expenses:Books "weekly" 21 EUR"""

    for start, end, num in [
        (date(2016, 5, 1), date(2016, 5, 2), Decimal(21) / 7),
        (date(2016, 9, 1), date(2016, 9, 2), Decimal(21) / 7),
    ]:
        budget = calculate_budget(budgets_doc, "Expenses:Books", start, end)
        assert budget["EUR"] == num


def test_budgets_monthly(budgets_doc: BudgetDict) -> None:
    """
    2014-05-01 custom "budget" Expenses:Books "monthly" 100 EUR"""

    for start, end, num in [
        (date(2016, 5, 1), date(2016, 5, 2), Decimal(100) / 31),
        (date(2016, 2, 1), date(2016, 2, 2), Decimal(100) / 29),
        (date(2018, 3, 31), date(2018, 4, 1), Decimal(100) / 31),
    ]:
        budget = calculate_budget(budgets_doc, "Expenses:Books", start, end)
        assert budget["EUR"] == num


def test_budgets_doc_quarterly(budgets_doc: BudgetDict) -> None:
    """
    2014-05-01 custom "budget" Expenses:Books "quarterly" 123456.7 EUR"""

    for start, end, num in [
        (date(2016, 5, 1), date(2016, 5, 2), Decimal("123456.7") / 91),
        (date(2016, 8, 15), date(2016, 8, 16), Decimal("123456.7") / 92),
    ]:
        budget = calculate_budget(budgets_doc, "Expenses:Books", start, end)
        assert budget["EUR"] == num


def test_budgets_doc_yearly(budgets_doc: BudgetDict) -> None:
    """
    2010-01-01 custom "budget" Expenses:Books "yearly" 99999.87 EUR"""

    budget = calculate_budget(
        budgets_doc,
        "Expenses:Books",
        date(2011, 2, 1),
        date(2011, 2, 2),
    )
    assert budget["EUR"] == Decimal("99999.87") / 365


def test_budgets_children(budgets_doc: BudgetDict) -> None:
    """
    2017-01-01 custom "budget" Expenses:Books "daily" 10.00 USD
    2017-01-01 custom "budget" Expenses:Books:Notebooks "daily" 2.00 USD"""

    budget = calculate_budget_children(
        budgets_doc,
        "Expenses",
        date(2017, 1, 1),
        date(2017, 1, 2),
    )
    assert budget["USD"] == Decimal("12.00")

    budget = calculate_budget_children(
        budgets_doc,
        "Expenses:Books",
        date(2017, 1, 1),
        date(2017, 1, 2),
    )
    assert budget["USD"] == Decimal("12.00")

    budget = calculate_budget_children(
        budgets_doc,
        "Expenses:Books:Notebooks",
        date(2017, 1, 1),
        date(2017, 1, 2),
    )
    assert budget["USD"] == Decimal("2.00")


def test_budgets_children_sibling_with_shared_prefix(
    budgets_doc: BudgetDict,
) -> None:
    """
    2017-01-01 custom "budget" Expenses:Car "daily" 10.00 USD
    2017-01-01 custom "budget" Expenses:Car:Fuel "daily" 1.00 USD
    2017-01-01 custom "budget" Expenses:Carpet "daily" 100.00 USD"""

    budget = calculate_budget_children(
        budgets_doc,
        "Expenses:Car",
        date(2017, 1, 1),
        date(2017, 1, 2),
    )
    assert budget["USD"] == Decimal("11.00")

    budget = calculate_budget_children(
        budgets_doc,
        "Expenses:Carpet",
        date(2017, 1, 1),
        date(2017, 1, 2),
    )
    assert budget["USD"] == Decimal("100.00")


def test_budget_plans(load_doc_custom_entries: list[Custom]) -> None:
    """
    2026-01-01 custom "budget-plan" "k" Expenses:Kitchen 20000 USD
      name: "Kitchen remodel"
      end: 2026-06-30

    2026-02-01 custom "budget-plan" "c" Expenses:Kitchen:Cabinets 8000 USD
      parent: "k"
      name: "Cabinets"
    """
    plans, errors = parse_budget_plans(load_doc_custom_entries)

    assert not errors
    assert len(plans) == 2
    root, child = plans
    assert root.plan_id == "k"
    assert root.date_end == date(2026, 6, 30)
    assert child.parent_id == root.plan_id
    assert child.date_end == root.date_end


def test_budget_plan_validation(load_doc_custom_entries: list[Custom]) -> None:
    """
    2026-01-01 custom "budget-plan" "missing-end" Expenses:Projects 100 USD
    2026-01-01 custom "budget-plan" "orphan" Expenses:Projects:Other 50 USD
      parent: "unknown"
    """
    plans, errors = parse_budget_plans(load_doc_custom_entries)

    assert not plans
    assert len(errors) == 2
    assert "require `end`" in errors[0].message
    assert "Unknown parent" in errors[1].message


def test_budget_plan_input_validation(
    load_doc_custom_entries: list[Custom],
) -> None:
    """
    2026-01-01 custom "budget-plan" "bad-name" Expenses:Projects 1 USD
      name: 123
      end: 2026-12-31
    2026-01-01 custom "budget-plan" "bad-end" Expenses:Projects 1 USD
      end: "later"
    2026-01-01 custom "budget-plan" "too-few" Expenses:Projects
    2026-01-01 custom "budget-plan" 1 USD Expenses:Projects 1 USD
    2026-01-01 custom "budget-plan" " " Expenses:Projects 1 USD
    2026-01-01 custom "budget-plan" "bad-account" "Projects" 1 USD
    2026-01-01 custom "budget-plan" "bad-amount" Expenses:Projects "1 USD"
    2026-01-01 custom "budget-plan" "negative" Expenses:Projects -1 USD
    2026-01-01 custom "budget-plan" "duplicate" Expenses:Projects 1 USD
      end: 2026-12-31
    2026-01-02 custom "budget-plan" "duplicate" Expenses:Projects 1 USD
      end: 2026-12-31
    """
    plans, errors = parse_budget_plans(load_doc_custom_entries)

    assert [plan.plan_id for plan in plans] == ["duplicate"]
    messages = "\n".join(error.message for error in errors)
    assert "Metadata `name` must be a non-empty string" in messages
    assert "Metadata `end` must be a date" in messages
    assert "require an ID, account, and amount" in messages
    assert "ID must be a string" in messages
    assert "ID must not be empty" in messages
    assert "account must be an account" in messages
    assert "amount must be an amount" in messages
    assert "amount must not be negative" in messages
    assert "Duplicate budget plan ID" in messages


def test_budget_plan_relationship_validation(
    load_doc_custom_entries: list[Custom],
) -> None:
    """
    2026-01-01 custom "budget-plan" "failed" Expenses:Failed 1 USD
    2026-01-01 custom "budget-plan" "failed-child" Expenses:Failed:Child 1 USD
      parent: "failed"
    2026-01-01 custom "budget-plan" "parent" Expenses:Project 100 USD
      end: 2026-06-30
    2026-01-01 custom "budget-plan" "wrong-account" Expenses:Other 1 USD
      parent: "parent"
    2025-12-31 custom "budget-plan" "starts-early" Expenses:Project:Early 1 USD
      parent: "parent"
    2026-02-01 custom "budget-plan" "ends-late" Expenses:Project:Late 1 USD
      parent: "parent"
      end: 2026-07-01
    2026-02-01 custom "budget-plan" "ends-before-start" Expenses:Short 1 USD
      end: 2026-01-31
    2026-01-01 custom "budget-plan" "cycle-a" Expenses:Cycle:A 1 USD
      parent: "cycle-b"
      end: 2026-12-31
    2026-01-01 custom "budget-plan" "cycle-b" Expenses:Cycle:A:B 1 USD
      parent: "cycle-a"
      end: 2026-12-31
    """
    plans, errors = parse_budget_plans(load_doc_custom_entries)

    assert [plan.plan_id for plan in plans] == ["parent"]
    messages = "\n".join(error.message for error in errors)
    assert "Invalid parent budget plan" in messages
    assert "below its parent account" in messages
    assert "start before its parent" in messages
    assert "end after its parent" in messages
    assert "end date must not precede" in messages
    assert "parent cycle" in messages


def test_budget_plan_statuses() -> None:
    plan = BudgetPlan(
        plan_id="project",
        account="Expenses:Project",
        number=Decimal(1),
        currency="USD",
        date_start=date(2026, 2, 1),
        date_end=date(2026, 2, 28),
        name="Project",
    )

    assert _plan_status(plan, date(2026, 1, 31)) == "upcoming"
    assert _plan_status(plan, date(2026, 2, 1)) == "active"
    assert _plan_status(plan, date(2026, 3, 1)) == "ended"
