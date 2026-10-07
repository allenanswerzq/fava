import { equal, ok } from "node:assert/strict";
import { test } from "node:test";

import { mount, tick, unmount } from "svelte";

import type {
  BudgetAccountNode,
  BudgetPlanNode,
} from "../src/api/validators.ts";
import { budget_report_validator } from "../src/api/validators.ts";
import AccountBudgets from "../src/reports/budgets/AccountBudgets.svelte";
import BudgetPlans from "../src/reports/budgets/BudgetPlans.svelte";
import { setup_jsdom } from "./dom.ts";
import { initialise_ledger_data } from "./helpers.ts";

test.before(initialise_ledger_data);
test.beforeEach(setup_jsdom);

const account = (
  account_name: string,
  children: BudgetAccountNode[] = [],
): BudgetAccountNode => ({
  name: account_name.split(":").at(-1) ?? account_name,
  account: account_name,
  budget: {},
  budget_total: { USD: 500 },
  actual: {},
  actual_total: { USD: 125 },
  children,
});

const plan = (overrides: Partial<BudgetPlanNode> = {}): BudgetPlanNode => ({
  plan_id: "kitchen",
  name: "Kitchen remodel",
  account: "Expenses:Projects:Kitchen",
  date_start: new Date("2026-01-01"),
  date_end: new Date("2026-12-31"),
  status: "active",
  progress: 0.5,
  budget: { USD: 20000 },
  actual: {},
  actual_total: { USD: 5000 },
  allocated: { USD: 8000 },
  unallocated_actual: { USD: 500 },
  children: [],
  ...overrides,
});

test("validate budget report API data", () => {
  const report = budget_report_validator({
    date_range: { begin: "2026-01-01", end: "2026-02-01" },
    progress: 0.5,
    accounts: [
      {
        name: "Expenses",
        account: "Expenses",
        budget: {},
        budget_total: { USD: "500" },
        actual: {},
        actual_total: { USD: "125" },
        children: [],
      },
    ],
    unbudgeted: null,
    plans: [],
  }).unwrap();

  equal(report.accounts[0]?.budget_total.USD, 500);
  equal(report.date_range.begin.toISOString().slice(0, 10), "2026-01-01");
});

test("account budgets keep unbudgeted spending collapsed", async () => {
  const target = document.querySelector("article");
  ok(target);
  const component = mount(AccountBudgets, {
    target,
    props: {
      accounts: [account("Expenses", [account("Expenses:Food")])],
      unbudgeted: {
        ...account("Expenses", [account("Expenses:Books")]),
        name: "Unbudgeted spending",
      },
      progress: 0.4,
      date_range: {
        begin: new Date("2026-01-01"),
        end: new Date("2026-02-01"),
      },
    },
  });
  await tick();

  equal(target.querySelectorAll("[data-budget-row]").length, 3);
  equal(target.textContent.includes("Unbudgeted spending"), true);
  equal(target.textContent.includes("Books"), false);
  equal(
    target.querySelector(".head .budget-cell")?.textContent.trim(),
    "Budget (USD)",
  );
  equal(
    target.querySelector("[data-budget-row] .budget-cell")?.textContent.trim(),
    "500.00",
  );
  equal(
    target.querySelector(".period")?.textContent.replaceAll(/\s+/g, " ").trim(),
    "Budget period: 2026-01-01 – 2026-01-31",
  );

  const unbudgeted_row = [...target.querySelectorAll("[data-budget-row]")].find(
    (row) => row.textContent.includes("Unbudgeted spending"),
  );
  ok(unbudgeted_row);
  unbudgeted_row.querySelector("button")?.click();
  await tick();
  equal(target.textContent.includes("Books"), true);

  await unmount(component);
});

test("plans default to active with compact currency columns", async () => {
  const target = document.querySelector("article");
  ok(target);
  const component = mount(BudgetPlans, {
    target,
    props: {
      plans: [
        plan({
          children: [
            plan({
              plan_id: "cabinets",
              name: "Cabinets",
              account: "Expenses:Projects:Kitchen:Cabinets",
              budget: { USD: 8000 },
              allocated: {},
            }),
          ],
        }),
        plan({
          plan_id: "holiday",
          name: "Holiday",
          account: "Expenses:Projects:Holiday",
          status: "upcoming",
          budget: { EUR: 3000 },
          actual_total: { EUR: 500 },
          allocated: {},
        }),
      ],
    },
  });
  await tick();

  equal(target.querySelectorAll("[data-plan-card], [data-plan-row]").length, 2);
  equal(
    target.querySelector("[data-plan-card] .pace-cell")?.textContent.trim(),
    "On track",
  );
  equal(
    target.querySelector("[data-plan-card] .budget-cell")?.textContent.trim(),
    "20000.00",
  );
  equal(
    target.querySelector(".head .budget-cell")?.textContent.trim(),
    "Budget (USD)",
  );
  equal(
    target.querySelector("[data-plan-card] .plan-link")?.textContent.trim(),
    "Kitchen remodel",
  );
  equal(target.textContent.includes("Schedule and spending pace"), true);
  equal(target.textContent.includes("Holiday"), false);
  const account_link = target.querySelector<HTMLAnchorElement>(
    'a[href*="account/Expenses:Projects:Kitchen/"]',
  );
  ok(account_link);
  equal(
    new URL(account_link.href).searchParams.get("time"),
    "2026-01-01 - 2026-12-31",
  );

  const status = target.querySelector("select");
  ok(status);
  status.value = "all";
  status.dispatchEvent(new window.Event("change", { bubbles: true }));
  await tick();
  equal(target.querySelectorAll("[data-plan-card], [data-plan-row]").length, 3);
  equal(
    target.querySelector(".head .budget-cell")?.textContent.trim(),
    "Budget",
  );
  equal(
    target.querySelector("[data-plan-card] .budget-cell")?.textContent.trim(),
    "20000.00 USD",
  );

  await unmount(component);
});
