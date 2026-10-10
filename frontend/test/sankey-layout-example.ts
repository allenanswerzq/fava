import type { SankeyGraph, SankeyGraphNode } from "../src/charts/sankey.ts";

function account(
  id: string,
  name: string,
  column: number,
  level: number,
  balance: number,
): SankeyGraphNode {
  return {
    id,
    account: name,
    kind: "account",
    role: null,
    column,
    level,
    balance,
  };
}

/**
 * A deliberately crowded income statement used to exercise Sankey selection
 * and layout. It has deep income ancestry, wide expense branches, a result
 * node, values that compete for column budgets, and negligible tail values.
 */
export const complex_sankey_graph: SankeyGraph = {
  currency: "USD",
  nodes: [
    account("employer-a", "Income:Salary:Main:EmployerA", 0, 3, 500),
    account("employer-b", "Income:Salary:Main:EmployerB", 0, 3, 200),
    account("main", "Income:Salary:Main", 1, 2, 700),
    account("bonus", "Income:Salary:Bonus", 1, 2, 195),
    account("rounding", "Income:Salary:Rounding", 1, 2, 5),
    account("dividends", "Income:Investments:Dividends", 1, 2, 210),
    account("interest", "Income:Investments:Interest", 1, 2, 70),
    account("salary", "Income:Salary", 2, 1, 900),
    account("investments", "Income:Investments", 2, 1, 280),
    account("misc-income", "Income:Misc", 2, 1, 20),
    account("income", "Income", 3, 0, 1200),
    account("expenses", "Expenses", 4, 0, 1000),
    {
      id: "net-profit",
      account: null,
      kind: "result",
      role: "net_profit",
      column: 4,
      level: null,
      balance: 200,
    },
    account("housing", "Expenses:Housing", 5, 1, 450),
    account("living", "Expenses:Living", 5, 1, 430),
    account("travel", "Expenses:Travel", 5, 1, 140),
    account("refund", "Expenses:Refund", 5, 1, 30),
    account("fees", "Expenses:Fees", 5, 1, 10),
    account("rent", "Expenses:Housing:Rent", 6, 2, 430),
    account("repairs", "Expenses:Housing:Repairs", 6, 2, 20),
    account("groceries", "Expenses:Living:Groceries", 6, 2, 220),
    account("dining", "Expenses:Living:Dining", 6, 2, 125),
    account("utilities", "Expenses:Living:Utilities", 6, 2, 80),
    account("coffee", "Expenses:Living:Coffee", 6, 2, 5),
    account("flights", "Expenses:Travel:Flights", 6, 2, 130),
    account("tips", "Expenses:Travel:Tips", 6, 2, 10),
  ],
  links: [
    { source: "employer-a", target: "main", value: 500 },
    { source: "employer-b", target: "main", value: 200 },
    { source: "main", target: "salary", value: 700 },
    { source: "bonus", target: "salary", value: 195 },
    { source: "rounding", target: "salary", value: 5 },
    { source: "salary", target: "income", value: 900 },
    { source: "dividends", target: "investments", value: 210 },
    { source: "interest", target: "investments", value: 70 },
    { source: "investments", target: "income", value: 280 },
    { source: "misc-income", target: "income", value: 20 },
    { source: "income", target: "expenses", value: 1000 },
    { source: "income", target: "net-profit", value: 200 },
    { source: "refund", target: "expenses", value: 30 },
    { source: "expenses", target: "housing", value: 450 },
    { source: "housing", target: "rent", value: 430 },
    { source: "housing", target: "repairs", value: 20 },
    { source: "expenses", target: "living", value: 430 },
    { source: "living", target: "groceries", value: 220 },
    { source: "living", target: "dining", value: 125 },
    { source: "living", target: "utilities", value: 80 },
    { source: "living", target: "coffee", value: 5 },
    { source: "expenses", target: "travel", value: 140 },
    { source: "travel", target: "flights", value: 130 },
    { source: "travel", target: "tips", value: 10 },
    { source: "expenses", target: "fees", value: 10 },
  ],
};
