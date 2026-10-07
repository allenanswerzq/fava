"""Parsing and computing budgets."""

from __future__ import annotations

import datetime
from collections import Counter
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

import msgspec
from beancount.core.account import TYPE as ACCOUNT_TYPE
from beancount.core.amount import Amount

from fava.beans.account import account_tester
from fava.beans.account import parent as account_parent
from fava.beans.account import root as account_root
from fava.core.inventory import CounterInventory
from fava.core.inventory import SimpleCounterInventory
from fava.core.module_base import FavaModule
from fava.helpers import BeancountError
from fava.util.date import DateRange
from fava.util.date import days_in_daterange
from fava.util.date import get_interval
from fava.util.date import local_today

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping
    from collections.abc import Sequence

    from fava.beans.abc import Custom
    from fava.beans.abc import Directive
    from fava.beans.prices import FavaPriceMap
    from fava.core import FavaLedger
    from fava.core import FilteredLedger
    from fava.core.conversion import Conversion
    from fava.util.date import FiscalYearEnd
    from fava.util.date import Interval


@dataclass(frozen=True, slots=True)
class Budget:
    """A budget entry."""

    account: str
    date_start: datetime.date
    period: Interval
    number: Decimal
    currency: str


BudgetDict = dict[str, list[Budget]]
"""A map of account names to lists of budget entries."""


@dataclass(frozen=True, slots=True)
class BudgetPlan:
    """A finite budget plan, optionally nested below another plan."""

    plan_id: str
    account: str
    number: Decimal
    currency: str
    date_start: datetime.date
    date_end: datetime.date
    name: str
    parent_id: str | None = None


@dataclass(frozen=True, slots=True)
class BudgetAccountNode:
    """A node in the recurring account-budget report."""

    name: str
    account: str
    budget: SimpleCounterInventory
    budget_total: SimpleCounterInventory
    actual: SimpleCounterInventory
    actual_total: SimpleCounterInventory
    children: tuple[BudgetAccountNode, ...]


@dataclass(frozen=True, slots=True)
class BudgetPlanNode:
    """A finite budget plan prepared for presentation."""

    plan_id: str
    name: str
    account: str
    date_start: datetime.date
    date_end: datetime.date
    status: str
    progress: float
    budget: SimpleCounterInventory
    actual: SimpleCounterInventory
    actual_total: SimpleCounterInventory
    allocated: SimpleCounterInventory
    unallocated_actual: SimpleCounterInventory
    children: tuple[BudgetPlanNode, ...]


@dataclass(frozen=True, slots=True)
class _RawBudgetPlan:
    entry: Custom
    plan_id: str
    account: str
    number: Decimal
    currency: str
    name: str
    parent_id: str | None
    date_end: datetime.date | None


class BudgetError(BeancountError):
    """Error with a budget."""


class BudgetModule(FavaModule):
    """Parses budget entries."""

    def __init__(self, ledger: FavaLedger) -> None:
        super().__init__(ledger)
        self._budget_entries: BudgetDict = {}
        self.plans: Sequence[BudgetPlan] = []
        self.errors: Sequence[BudgetError] = []

    def load_file(self) -> None:  # noqa: D102
        self._budget_entries, budget_errors = parse_budgets(
            self.ledger.all_entries_by_type.Custom,
            self.ledger.fava_options.fiscal_year_end,
        )
        self.plans, plan_errors = parse_budget_plans(
            self.ledger.all_entries_by_type.Custom,
        )
        self.errors = [*budget_errors, *plan_errors]

    @property
    def accounts(self) -> Sequence[str]:
        """Accounts that have recurring budget directives."""
        return sorted(self._budget_entries)

    def calculate(
        self,
        account: str,
        begin_date: datetime.date,
        end_date: datetime.date,
    ) -> Mapping[str, Decimal]:
        """Calculate the budget for an account in an interval."""
        return calculate_budget(
            self._budget_entries, account, begin_date, end_date
        )

    def calculate_children(
        self,
        account: str,
        begin_date: datetime.date,
        end_date: datetime.date,
    ) -> Mapping[str, Decimal]:
        """Calculate the budget for an account including its children."""
        return calculate_budget_children(
            self._budget_entries, account, begin_date, end_date
        )

    def account_report(
        self,
        filtered: FilteredLedger,
        conversion: Conversion,
        date_range: DateRange,
    ) -> tuple[tuple[BudgetAccountNode, ...], BudgetAccountNode | None]:
        """Build recurring budget and unbudgeted-spending trees."""
        return build_account_budget_report(
            self,
            filtered,
            conversion,
            date_range,
        )

    def plan_report(
        self,
        conversion: Conversion,
    ) -> tuple[BudgetPlanNode, ...]:
        """Build all finite budget-plan trees."""
        return build_budget_plan_report(
            self.plans,
            self.ledger.all_entries,
            conversion,
            self.ledger.prices,
            self.ledger.options["name_income"],
        )


def _parse_budget(entry: Custom, fye: FiscalYearEnd) -> Budget:
    values = msgspec.convert(
        tuple(v.value for v in entry.values), tuple[str, str, Amount]
    )
    interval = get_interval(values[1], fye)
    if not interval:
        msg = "Invalid interval for budget entry"
        raise TypeError(msg)
    return Budget(
        values[0],
        entry.date,
        interval,
        values[2].number or Decimal(),
        values[2].currency,
    )


def parse_budgets(
    custom_entries: Sequence[Custom], fye: FiscalYearEnd
) -> tuple[BudgetDict, Sequence[BudgetError]]:
    """Parse budget directives from custom entries.

    Args:
        custom_entries: the Custom entries to parse budgets from.
        fye: The fiscal year end to use.

    Returns:
        A dict of accounts to lists of budgets.

    Example:
        2015-04-09 custom "budget" Expenses:Books "monthly" 20.00 EUR
    """
    budgets: BudgetDict = defaultdict(list)
    errors = []

    for entry in (entry for entry in custom_entries if entry.type == "budget"):
        try:
            budget = _parse_budget(entry, fye)
            budgets[budget.account].append(budget)
        except (TypeError, msgspec.ValidationError) as error:
            errors.append(
                BudgetError(
                    entry.meta,
                    f"Failed to parse budget entry: {error!s}",
                    entry,
                ),
            )

    return budgets, errors


def _metadata_string(entry: Custom, key: str) -> str | None:
    value = entry.meta.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        msg = f"Metadata `{key}` must be a non-empty string"
        raise TypeError(msg)
    return value.strip()


def _metadata_date(entry: Custom, key: str) -> datetime.date | None:
    value = entry.meta.get(key)
    if value is None:
        return None
    if not isinstance(value, datetime.date):
        msg = f"Metadata `{key}` must be a date"
        raise TypeError(msg)
    return value


def _parse_budget_plan(entry: Custom) -> _RawBudgetPlan:
    if len(entry.values) != 3:
        msg = "Budget plans require an ID, account, and amount"
        raise TypeError(msg)

    plan_id_value, account_value, amount_value = entry.values
    if not isinstance(plan_id_value.value, str):
        msg = "Budget plan ID must be a string"
        raise TypeError(msg)
    plan_id = plan_id_value.value.strip()
    if not plan_id:
        msg = "Budget plan ID must not be empty"
        raise ValueError(msg)

    if account_value.dtype != ACCOUNT_TYPE or not isinstance(
        account_value.value, str
    ):
        msg = "Budget plan account must be an account"
        raise TypeError(msg)
    if not isinstance(amount_value.value, Amount):
        msg = "Budget plan amount must be an amount"
        raise TypeError(msg)
    amount = amount_value.value
    if amount.number < 0:
        msg = "Budget plan amount must not be negative"
        raise ValueError(msg)

    account = account_value.value
    name = _metadata_string(entry, "name") or account.rsplit(":", 1)[-1]
    return _RawBudgetPlan(
        entry=entry,
        plan_id=plan_id,
        account=account,
        number=amount.number,
        currency=amount.currency,
        name=name,
        parent_id=_metadata_string(entry, "parent"),
        date_end=_metadata_date(entry, "end"),
    )


def _add_raw_budget_plan(
    entry: Custom,
    raw_plans: dict[str, _RawBudgetPlan],
) -> None:
    raw = _parse_budget_plan(entry)
    if raw.plan_id in raw_plans:
        msg = f"Duplicate budget plan ID: {raw.plan_id}"
        raise ValueError(msg)
    raw_plans[raw.plan_id] = raw


class _BudgetPlanResolver:
    """Resolve parent references and inherited dates for raw plans."""

    def __init__(
        self,
        raw_plans: Mapping[str, _RawBudgetPlan],
        errors: list[BudgetError],
    ) -> None:
        self.raw_plans = raw_plans
        self.errors = errors
        self.resolved: dict[str, BudgetPlan] = {}
        self.failed: set[str] = set()
        self.resolving: set[str] = set()

    def _parent(self, raw: _RawBudgetPlan) -> BudgetPlan | None:
        if raw.parent_id is None:
            return None
        if raw.parent_id not in self.raw_plans:
            msg = f"Unknown parent budget plan: {raw.parent_id}"
            raise ValueError(msg)
        parent = self.resolve(raw.parent_id)
        if parent is None:
            msg = f"Invalid parent budget plan: {raw.parent_id}"
            raise ValueError(msg)
        if not raw.account.startswith(parent.account + ":"):
            msg = "Child plan account must be below its parent account"
            raise ValueError(msg)
        return parent

    @staticmethod
    def _end_date(
        raw: _RawBudgetPlan,
        parent: BudgetPlan | None,
    ) -> datetime.date:
        date_end = raw.date_end or (parent.date_end if parent else None)
        if date_end is None:
            msg = "Root budget plans require `end` metadata"
            raise ValueError(msg)
        if date_end < raw.entry.date:
            msg = "Budget plan end date must not precede its start date"
            raise ValueError(msg)
        if parent is not None and date_end > parent.date_end:
            msg = "Child plan must not end after its parent"
            raise ValueError(msg)
        return date_end

    def _resolve_plan(self, raw: _RawBudgetPlan) -> BudgetPlan:
        if raw.plan_id in self.resolving:
            msg = f"Budget plan parent cycle involving `{raw.plan_id}`"
            raise ValueError(msg)
        self.resolving.add(raw.plan_id)
        parent = self._parent(raw)
        if parent is not None and raw.entry.date < parent.date_start:
            msg = "Child plan must not start before its parent"
            raise ValueError(msg)
        return BudgetPlan(
            plan_id=raw.plan_id,
            account=raw.account,
            number=raw.number,
            currency=raw.currency,
            date_start=raw.entry.date,
            date_end=self._end_date(raw, parent),
            name=raw.name,
            parent_id=raw.parent_id,
        )

    def resolve(self, plan_id: str) -> BudgetPlan | None:
        """Resolve one plan, reporting invalid parent chains once."""
        if plan_id in self.resolved:
            return self.resolved[plan_id]
        if plan_id in self.failed:
            return None
        raw = self.raw_plans[plan_id]
        try:
            plan = self._resolve_plan(raw)
        except ValueError as error:
            self.failed.add(plan_id)
            self.errors.append(
                BudgetError(
                    raw.entry.meta,
                    f"Failed to parse budget plan: {error!s}",
                    raw.entry,
                ),
            )
            return None
        finally:
            self.resolving.discard(plan_id)
        self.resolved[plan_id] = plan
        return plan


def parse_budget_plans(
    custom_entries: Sequence[Custom],
) -> tuple[list[BudgetPlan], Sequence[BudgetError]]:
    """Parse and validate ``custom "budget-plan"`` directives."""
    raw_plans: dict[str, _RawBudgetPlan] = {}
    errors: list[BudgetError] = []

    for entry in (
        entry for entry in custom_entries if entry.type == "budget-plan"
    ):
        try:
            _add_raw_budget_plan(entry, raw_plans)
        except (TypeError, ValueError) as error:
            errors.append(
                BudgetError(
                    entry.meta,
                    f"Failed to parse budget plan: {error!s}",
                    entry,
                ),
            )

    resolver = _BudgetPlanResolver(raw_plans, errors)
    for plan_id in raw_plans:
        resolver.resolve(plan_id)

    plans = sorted(
        resolver.resolved.values(),
        key=lambda plan: (plan.date_start, plan.name.casefold(), plan.plan_id),
    )
    return plans, errors


def _matching_budgets(
    budgets: Sequence[Budget],
    date_active: datetime.date,
) -> Mapping[str, Budget]:
    """Find matching budgets.

    Returns:
        The budget that is active on the specified date for the
        specified account.
    """
    last_seen_budgets = {}
    for budget in budgets:
        if budget.date_start <= date_active:
            last_seen_budgets[budget.currency] = budget
        else:
            break
    return last_seen_budgets


def calculate_budget(
    budgets: BudgetDict,
    account: str,
    date_from: datetime.date,
    date_to: datetime.date,
) -> Mapping[str, Decimal]:
    """Calculate budget for an account.

    Args:
        budgets: A list of :class:`Budget` entries.
        account: An account name.
        date_from: Starting date.
        date_to: End date (exclusive).

    Returns:
        A dictionary of currency to Decimal with the budget for the
        specified account and period.
    """
    budget_list = budgets.get(account, None)
    if budget_list is None:
        return {}

    currency_dict: dict[str, Decimal] = defaultdict(Decimal)

    for day in days_in_daterange(date_from, date_to):
        matches = _matching_budgets(budget_list, day)
        for budget in matches.values():
            days_in_period = budget.period.number_of_days(day)
            currency_dict[budget.currency] += budget.number / days_in_period
    return dict(currency_dict)


def calculate_budget_children(
    budgets: BudgetDict,
    account: str,
    date_from: datetime.date,
    date_to: datetime.date,
) -> Mapping[str, Decimal]:
    """Calculate budget for an account including budgets of its children.

    Args:
        budgets: A list of :class:`Budget` entries.
        account: An account name.
        date_from: Starting date.
        date_to: End date (exclusive).

    Returns:
        A dictionary of currency to Decimal with the budget for the
        specified account and period.
    """
    currency_dict: dict[str, Decimal] = Counter()  # type: ignore[assignment]  # ty:ignore[invalid-assignment]

    is_child_account = account_tester(account, with_children=True)
    for child in budgets:
        if is_child_account(child):
            currency_dict.update(
                calculate_budget(budgets, child, date_from, date_to),
            )
    return dict(currency_dict)


def _add_values(
    target: SimpleCounterInventory,
    values: Mapping[str, Decimal],
) -> None:
    for currency, number in values.items():
        target.add(currency, number)


def _subtract_values(
    left: Mapping[str, Decimal],
    right: Mapping[str, Decimal],
) -> SimpleCounterInventory:
    result = SimpleCounterInventory(left)
    for currency, number in right.items():
        result.add(currency, -number)
    return result


def _convert_values(
    values: Mapping[str, Decimal],
    conversion: Conversion,
    prices: FavaPriceMap,
    day: datetime.date,
) -> SimpleCounterInventory:
    inventory = CounterInventory(
        {(currency, None): number for currency, number in values.items()},
    )
    return conversion.apply(inventory, prices, day)


def _actual_inventories(
    entries: Sequence[Directive],
    date_range: DateRange,
) -> dict[str, CounterInventory]:
    actuals: dict[str, CounterInventory] = defaultdict(CounterInventory)
    for entry in entries:
        if not date_range.begin <= entry.date < date_range.end:
            continue
        for posting in getattr(entry, "postings", []):
            actuals[posting.account].add_position(posting)
    return actuals


def _inventory_for_account(
    actuals: Mapping[str, CounterInventory],
    account: str,
    *,
    with_children: bool,
) -> CounterInventory:
    inventory = CounterInventory()
    matches = account_tester(account, with_children=with_children)
    for actual_account, actual in actuals.items():
        if matches(actual_account):
            inventory.add_inventory(actual)
    return inventory


def _normalise_actual(
    values: SimpleCounterInventory,
    account: str,
    income_account: str,
) -> SimpleCounterInventory:
    return -values if account_root(account) == income_account else values


def _account_ancestors(account: str) -> list[str]:
    ancestors = []
    current: str | None = account
    while current:
        ancestors.append(current)
        current = account_parent(current)
    return list(reversed(ancestors))


def build_account_budget_report(
    module: BudgetModule,
    filtered: FilteredLedger,
    conversion: Conversion,
    date_range: DateRange,
) -> tuple[tuple[BudgetAccountNode, ...], BudgetAccountNode | None]:
    """Build the recurring budget tree and unbudgeted expense tree."""
    prices = module.ledger.prices
    price_date = date_range.end_inclusive
    income_account = module.ledger.options["name_income"]
    expense_account = module.ledger.options["name_expenses"]
    actuals = _actual_inventories(filtered.entries, date_range)

    budget_matchers = [
        account_tester(account, with_children=True)
        for account in module.accounts
    ]
    budgeted_actuals = {
        account: inventory
        for account, inventory in actuals.items()
        if any(matches(account) for matches in budget_matchers)
    }

    visible_accounts: set[str] = set()
    for account in module.accounts:
        visible_accounts.update(_account_ancestors(account))

    children_by_account: dict[str | None, list[str]] = defaultdict(list)
    for account in visible_accounts:
        parent = account_parent(account)
        visible_parent = parent if parent in visible_accounts else None
        children_by_account[visible_parent].append(account)

    def account_node(account: str) -> BudgetAccountNode:
        own_budget = _convert_values(
            module.calculate(account, date_range.begin, date_range.end),
            conversion,
            prices,
            price_date,
        )
        total_budget = _convert_values(
            module.calculate_children(
                account,
                date_range.begin,
                date_range.end,
            ),
            conversion,
            prices,
            price_date,
        )
        own_actual = _normalise_actual(
            conversion.apply(
                _inventory_for_account(
                    budgeted_actuals,
                    account,
                    with_children=False,
                ),
                prices,
                price_date,
            ),
            account,
            income_account,
        )
        total_actual = _normalise_actual(
            conversion.apply(
                _inventory_for_account(
                    budgeted_actuals,
                    account,
                    with_children=True,
                ),
                prices,
                price_date,
            ),
            account,
            income_account,
        )
        return BudgetAccountNode(
            name=account.rsplit(":", 1)[-1],
            account=account,
            budget=own_budget,
            budget_total=total_budget,
            actual=own_actual,
            actual_total=total_actual,
            children=tuple(
                account_node(child)
                for child in sorted(children_by_account[account])
            ),
        )

    roots = tuple(
        account_node(account) for account in sorted(children_by_account[None])
    )

    unbudgeted_accounts = {
        account
        for account, inventory in actuals.items()
        if account_tester(expense_account, with_children=True)(account)
        and inventory
        and not any(matches(account) for matches in budget_matchers)
    }
    if not unbudgeted_accounts:
        return roots, None

    unbudgeted_actuals = {
        account: inventory
        for account, inventory in actuals.items()
        if account in unbudgeted_accounts
    }

    unbudgeted_visible: set[str] = {expense_account}
    for account in unbudgeted_accounts:
        for ancestor in _account_ancestors(account):
            if account_tester(expense_account, with_children=True)(ancestor):
                unbudgeted_visible.add(ancestor)

    unbudgeted_children: dict[str, list[str]] = defaultdict(list)
    for account in unbudgeted_visible:
        if account == expense_account:
            continue
        parent = account_parent(account)
        if parent in unbudgeted_visible:
            unbudgeted_children[parent].append(account)

    def unbudgeted_node(account: str) -> BudgetAccountNode:
        own_actual = conversion.apply(
            actuals.get(account, CounterInventory()),
            prices,
            price_date,
        )
        total_actual = conversion.apply(
            _inventory_for_account(
                unbudgeted_actuals,
                account,
                with_children=True,
            ),
            prices,
            price_date,
        )
        return BudgetAccountNode(
            name=account.rsplit(":", 1)[-1],
            account=account,
            budget=SimpleCounterInventory(),
            budget_total=SimpleCounterInventory(),
            actual=own_actual,
            actual_total=total_actual,
            children=tuple(
                unbudgeted_node(child)
                for child in sorted(unbudgeted_children[account])
            ),
        )

    expense_node = unbudgeted_node(expense_account)
    unbudgeted = BudgetAccountNode(
        name="Unbudgeted spending",
        account=expense_account,
        budget=SimpleCounterInventory(),
        budget_total=SimpleCounterInventory(),
        actual=SimpleCounterInventory(),
        actual_total=expense_node.actual_total,
        children=expense_node.children,
    )
    return roots, unbudgeted


def _plan_status(plan: BudgetPlan, today: datetime.date) -> str:
    if today < plan.date_start:
        return "upcoming"
    if today > plan.date_end:
        return "ended"
    return "active"


def _plan_progress(plan: BudgetPlan, today: datetime.date) -> float:
    total_days = (plan.date_end - plan.date_start).days + 1
    elapsed_days = (today - plan.date_start).days + 1
    return min(1.0, max(0.0, elapsed_days / total_days))


def build_budget_plan_report(
    plans: Sequence[BudgetPlan],
    entries: Sequence[Directive],
    conversion: Conversion,
    prices: FavaPriceMap,
    income_account: str,
) -> tuple[BudgetPlanNode, ...]:
    """Build finite budget plan trees with automatically computed actuals."""
    today = local_today()
    plans_by_id = {plan.plan_id: plan for plan in plans}
    children_by_id: dict[str | None, list[str]] = defaultdict(list)
    for plan in plans:
        children_by_id[plan.parent_id].append(plan.plan_id)

    def plan_node(plan_id: str) -> BudgetPlanNode:
        plan = plans_by_id[plan_id]
        price_date = today
        budget = _convert_values(
            {plan.currency: plan.number},
            conversion,
            prices,
            price_date,
        )
        actual_end = min(today, plan.date_end) + datetime.timedelta(days=1)
        actuals = (
            _actual_inventories(
                entries,
                DateRange(plan.date_start, actual_end),
            )
            if actual_end > plan.date_start
            else {}
        )
        actual = _normalise_actual(
            conversion.apply(
                _inventory_for_account(
                    actuals,
                    plan.account,
                    with_children=False,
                ),
                prices,
                price_date,
            ),
            plan.account,
            income_account,
        )
        actual_total = _normalise_actual(
            conversion.apply(
                _inventory_for_account(
                    actuals,
                    plan.account,
                    with_children=True,
                ),
                prices,
                price_date,
            ),
            plan.account,
            income_account,
        )
        children = tuple(
            plan_node(child_id)
            for child_id in sorted(
                children_by_id[plan_id],
                key=lambda child_id: plans_by_id[child_id].name.casefold(),
            )
        )
        allocated = SimpleCounterInventory()
        child_actual = SimpleCounterInventory()
        for child in children:
            _add_values(allocated, child.budget)
            _add_values(child_actual, child.actual_total)
        return BudgetPlanNode(
            plan_id=plan.plan_id,
            name=plan.name,
            account=plan.account,
            date_start=plan.date_start,
            date_end=plan.date_end,
            status=_plan_status(plan, today),
            progress=_plan_progress(plan, today),
            budget=budget,
            actual=actual,
            actual_total=actual_total,
            allocated=allocated,
            unallocated_actual=_subtract_values(actual_total, child_actual),
            children=children,
        )

    return tuple(
        plan_node(plan_id)
        for plan_id in sorted(
            children_by_id[None],
            key=lambda plan_id: (
                plans_by_id[plan_id].date_start,
                plans_by_id[plan_id].name.casefold(),
            ),
        )
    )
