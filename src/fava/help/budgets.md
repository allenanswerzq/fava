Budgets on a per-account basis can be added via `custom` directives in the
Beancount file:

```beancount
2012-01-01 custom "budget" Expenses:Coffee       "daily"         4.00 EUR
2013-01-01 custom "budget" Expenses:Books        "weekly"       20.00 EUR
2014-02-10 custom "budget" Expenses:Groceries    "monthly"      40.00 EUR
2015-05-01 custom "budget" Expenses:Electricity  "quarterly"    85.00 EUR
2016-06-01 custom "budget" Expenses:Holiday      "yearly"     2500.00 EUR
```

If budgets are specified, Fava's reports and charts will display remaining
budgets and related information.

The budget directives can be specified `daily`, `weekly`, `monthly`, `quarterly`
and `yearly`. The specified budget is valid until another budget directive for
the account is specified. The budget is broken down to a daily budget, and
summed up for a range of dates as needed.

This makes the budgets very flexible, allowing for a monthly budget, being taken
over by a weekly budget, and so on.

Fava displays budgets in both charts and reports. You can find a visualization
of the global budget in the `Net Profit` and `Expenses` charts for the Income
Statement report.

The Budget page compares these amounts with postings automatically calculated
for the selected time range. Refunds and other negative expense postings reduce
the actual amount. If multiple currencies remain after the selected conversion,
they are shown separately.

## Finite plans and projects

For a task with a fixed start, end, and total cap, use a `budget-plan`
directive. The directive date is the start date and a root plan requires `end`
metadata:

```beancount
2026-01-01 custom "budget-plan" "kitchen" Expenses:Projects:Kitchen 20000 USD
  name: "Kitchen remodel"
  end: 2026-06-30

2026-01-01 custom "budget-plan" "kitchen-cabinets" Expenses:Projects:Kitchen:Cabinets 8000 USD
  parent: "kitchen"
  name: "Cabinets"
```

Child plans must use an account below their parent's account. They inherit the
parent's end date unless they specify an earlier one. A parent's amount is the
cap for the complete project; child amounts are allocations within that cap and
are not added to it.

Actual spending is computed from postings to the plan account and its children.
The Plans view shows both unallocated budget and spending recorded directly
outside the declared child plans, so a project does not need to be fully broken
down before it can be tracked.
